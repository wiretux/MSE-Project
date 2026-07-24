from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.request import Request, urlopen, urlretrieve
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import storage

USER_AGENT = 'MSE-Crawler' # User Agent used when crawling
CRAWL_DEPTH = 3    # Maximum distance/depth crawler diverts from seed urls
CRAWL_TIMEOUT = 2  # Timeout in seconds
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
            chunk = res.read(1024)
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

def __crawl_site(site_url: string, depth: int = 0):
    if depth > CRAWL_DEPTH:
        return None, None

    site_url = __clean_url(site_url)
    site_netloc = urlsplit(site_url).netloc

    rp = __parse_robots(site_url)
    delay = rp.crawl_delay(USER_AGENT)
    can_fetch = rp.can_fetch(USER_AGENT, site_url)

    if can_fetch:
        content, links = __parse_document(__fetch_document(site_url), site_url)

        # Don't add new links past CRAWL_DEPTH
        if depth >= CRAWL_DEPTH:
            return content, None

        # TODO: Limit execessive link usage
        #insite_links, outsite_links = [], []
        #for link in links:
        #    if urlsplit(link).netloc == site_netloc and len(insite_links) < 200:
        #        insite_links.append(link)
        #    else:
        #        outsite_links.append(link)
        
        return content, links

    return None, None

def crawl():
    with storage.access() as store:
        frontier = store.poll_frontier()

        while len(frontier) > 0:
            site_url = frontier.pop()
            try:
                content, links = __crawl_site(site_url, 0)

                # TODO: Append metadata like depth, etc.
                # store.offer_frontier(links)

                # TODO: Add to index
                # index(doc_id, content)

                print(f'{site_url} | Crawled')
            except Exception as e:
                print(f'{site_url} | {e}')

            # If frontier is empty try to get next
            if len(frontier) == 0:
                frontier = store.poll_frontier()

crawl()