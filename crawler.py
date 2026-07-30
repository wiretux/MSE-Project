# Fetch related
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.request import Request, urlopen, urlretrieve
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

# Optimization related
from threading import Thread
from queue import Queue, ShutDown
from time import sleep

# UI related
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn

# Our libraries
import utils.storage as storage
from indexer import index

USER_AGENT = 'MSE-Crawler' # User Agent used when crawling
CRAWL_DEPTH = 1    # Maximum distance/depth crawler may deviate from seed urls
CRAWL_TIMEOUT = 5  # Timeout in seconds
CRAWLER_COUNT = 2
CRAWLER_DELAY = 0.01
MAX_DOCUMENT_SIZE = 2 * 1024 * 1024 # Document limit in bytes (2MiB)
# MAX_PATH_DEPTH = 8 Maybe?

def __clean_url(url: string) -> string | None:
    """
    Remove query and fragment part of urls
    Only keeps urls which scheme is either http/https
    (Filters unwanted protocols like tel/mailto)
    """
    parsed = urlsplit(url)._replace(query='', fragment='')
    if parsed.scheme.lower() in ['http', 'https']:
        return urlunsplit(parsed)
    return None

def __parse_robots(site_url: string) -> RobotFileParser:
    """
    Tries to read/get the robots.txt
    Defaults to allow everything, if parsing fails. (Not Found/Invalid Cert)
    """
    rp = RobotFileParser(urlunsplit(urlsplit(site_url)._replace(path='/robots.txt')))

    try:
        rp.read()
    except:
        rp.parse([])

    return rp

def __fetch_document(site_url: string) -> string | None:
    """
    Fetches document from the specified site_url
    """
    req = Request(site_url, headers={ 'User-Agent': USER_AGENT })
    with urlopen(req, timeout=CRAWL_TIMEOUT) as res:
        content_length = res.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_DOCUMENT_SIZE:
            raise ValueError('Document exceeds size limit')

        chunks = []
        total_bytes = 0
        while total_bytes < MAX_DOCUMENT_SIZE:
            chunk = res.read(8192)
            if not chunk: # EOF
                break

            total_bytes += len(chunk)

            # TODO: Should we raise an error or try to parse the first 2MiB
            if total_bytes >= MAX_DOCUMENT_SIZE:
                raise ValueError('Document exceeds size limit')

            chunks.append(chunk)
        return b''.join(chunks).decode('utf-8', errors='replace')

# TODO: Filter non english pages / unrelated to Tuebingen
def __parse_document(document: string, site_url: string) -> (string, list[string]):
    """
    Extracts text content and links from a given document.
    """
    soup = BeautifulSoup(document, 'html.parser')
    

    # Extract links from document
    links = set([
        link
        for element in soup.find_all('a', href=True)
        if (link := __clean_url(urljoin(site_url, element['href'])))
        # Maybe limit MAX PATH DEPTH?: if len(link.split('/')) > MAX_PATH_DEPTH + 2
    ])

    # Remove non content elements (e.g. nav, header, footer, aside)
    # This should be relatively safe, since modern sites
    # use semantic tags like <main> for their content and
    # nav elements don't really contribute to the actual
    # content of a page.
    for tag in ['nav', 'header', 'footer', 'aside']:
        for element in soup.find_all(tag):
            element.decompose()

    # Replace images with their alt text
    for element in soup.find_all('img'):
        alt = element.get('alt')
        if alt and (' ' in alt or alt.isalnum()):
            element.replace_with(alt)
        else:
            element.decompose()

    return soup.get_text(separator=' ', strip=True), links

def __crawl_site(site_url: string, depth: int = 0) -> { 'title': str, 'description': str, 'content': str, 'links': list[str] } | None:
    if depth > CRAWL_DEPTH:
        return None

    site_url = __clean_url(site_url)
    site_netloc = urlsplit(site_url).netloc

    rp = __parse_robots(site_url)

    # TODO: Try to delay crawling of certain page
    #delay = rp.crawl_delay(USER_AGENT)
    can_fetch = rp.can_fetch(USER_AGENT, site_url)

    if can_fetch:
        content, links = __parse_document(__fetch_document(site_url), site_url)

        # TODO: Limit execessive link usage
        #insite_links, outsite_links = [], []
        #for link in links:
        #    if urlsplit(link).netloc == site_netloc and len(insite_links) < 200:
        #        insite_links.append(link)
        #    else:
        #        outsite_links.append(link)

        return {
            'title': None, # TODO: Get title from document
            'description': None, # TODO: Get description from document
            'content': content,
        
            # Don't add new links past CRAWL_DEPTH
            'links': links
        }

    return None

def crawler(queue: Queue, outqueue: Queue):
    try:
        while (item := queue.get()) is not None:
            doc_id, url, depth = item
            try:
                site = __crawl_site(url, depth)
                outqueue.put((
                    doc_id, # doc_id
                    site, # site
                    depth, # depth
                    None # error
                ))
            except Exception as e:
                outqueue.put((
                    doc_id, # doc_id
                    None, # site
                    depth, # depth
                    e # error
                ))
            queue.task_done()
    except ShutDown:
        pass

def index_consumer(queue: Queue):
    try:
        with Progress() as progress:
            task_map = {}

            with storage.access() as store:
                while (item := queue.get()) is not None:
                    doc_id, site, depth, e = item

                    if depth not in task_map:
                        task_map[depth] = progress.add_task(f'{depth} - Depth', total=store.count_frontier(depth))

                    # If there is error store error status in DB
                    if e is None:
                        # If there is content index else status skipped
                        if site and site['content'] and index(doc_id, site):
                            store.update_status(doc_id, storage.DocumentStatus.READY)
                        else:
                            store.update_status(doc_id, storage.DocumentStatus.SKIPPED)
                        
                        # Add links to frontier
                        if site and site['links']:
                            store.offer_frontier([(link, depth + 1) for link in site['links']])
                    else:
                        store.update_status(doc_id, storage.DocumentStatus.ERROR)

                    progress.advance(task_map[depth], 1)
                    queue.task_done()
    except ShutDown:
        pass

def crawl():
    frontier_queue = Queue(maxsize=24)
    index_queue = Queue(maxsize=24)

    crawlers = []
    consumer = Thread(target=index_consumer, args=(index_queue,))
    consumer.start()

    for _ in range(CRAWLER_COUNT):
        crawlers.append(Thread(target=crawler, args=(frontier_queue,index_queue,)))
        crawlers[-1].start()
    
    with storage.access() as store:
        for depth in range(CRAWL_DEPTH + 1):
            while frontier := store.poll_frontier(50, depth):
                for task in frontier:
                    frontier_queue.put(task)

            # Make sure we don't overlap depth, so we can
            # get the total amount of sites to crawl for
            # any given depth
            frontier_queue.join()
            index_queue.join()

    frontier_queue.shutdown()
    index_queue.shutdown()

    for c in crawlers:
        c.join()
    consumer.join()

    with storage.access() as store:
        print('Crawling/Indexing complete')
        print(f'Sites indexed: {store.count_index()}')

# TODO: Move this to the main file later
with storage.access() as store:
    store.init()
    # Add Seed URLS at depth 0
    store.offer_frontier(('https://uni-tuebingen.de/en', 0))

crawl()
