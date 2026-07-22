from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.request import Request, urlopen, urlretrieve
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

USER_AGENT = "MSE-Crawler"

def _clean_url(url: string) -> string | None:
    """
    Remove query and fragment part of urls
    Only keeps urls which scheme is either http/https
    (Filters unwanted protocols like tel/mailto)
    """
    parsed = urlsplit(url)._replace(query='', fragment='')
    if parsed.scheme.lower() in ['http', 'https']:
        return urlunsplit(parsed)
    return None

def _parse_robots(site_url: string) -> RobotFileParser:
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

def _fetch_document(site_url: string) -> string | None:
    """
    Fetches document from the specified site_url
    """
    try:
        with urlopen(Request(site_url, headers={ 'User-Agent': USER_AGENT })) as res:
            return res.read().decode('utf-8')
    except Exception as e:
        print(f'Unable to fetch page: {e}')
        return None

# TODO: Filter non english pages / unrelated to Tuebingen
def parse_document(document: string, site_url: string) -> (string, list[string]):
    """
    Extracts text content and links from a given document.
    """
    soup = BeautifulSoup(document, 'html.parser')
    

    # Extract links from document
    links = set([
        link
        for element in soup.find_all('a', href=True)
        if (link := _clean_url(urljoin(site_url, element['href'])))
    ])

    # Remove non content elements (e.g. nav, header, footer, aside)
    # This should be relatively safe, since modern sites
    # use semantic tags like <main> for their content and
    # nav elements don't really contribute to the actual
    # content of a page.
    # Some sites use the <header> tag for headings in articles,
    # this might cause issues.
    for tag in ['nav', 'header', 'footer', 'aside']:
        for element in soup.find_all(tag):
            element.decompose()

    # Replace images with their alt text
    # Maybe do the same for audio/video?
    for element in soup.find_all('img'):
        if element.get('alt'):
            element.replace_with(element['alt'])
        else:
            element.decompose()

    return soup.get_text(separator=' ', strip=True), links

def crawl(site_url: string):
    # TODO: implement loop

    site_url = _clean_url(site_url)
    site_netloc = urlsplit(site_url).netloc

    rp = _parse_robots(site_url)
    delay = rp.crawl_delay(USER_AGENT)
    can_fetch = rp.can_fetch(USER_AGENT, site_url)

    if can_fetch:
        # TODO: Add content to index
        content, links = parse_document(_fetch_document(site_url), site_url)
        insite_links, outsite_links = [], []

        print(content)

        # TODO: Add links to frontier
        for link in links:
            if urlsplit(link).netloc == site_netloc:
                insite_links.append(link)
            else:
                outsite_links.append(link)

# E.g. Crawl Uni-Tuebingen site
crawl("https://uni-tuebingen.de")
