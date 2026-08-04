from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue, ShutDown
from threading import Thread, current_thread
from time import sleep
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, RequestException
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)

from indexer import index
from utils import storage

USER_AGENT = "MSE-Crawler"  # User Agent used when crawling
CRAWL_DEPTH = 1  # Maximum distance/depth crawler may deviate from seed urls
CRAWL_TIMEOUT = 5  # Timeout in seconds
CRAWLER_COUNT = 12
CRAWLER_DELAY = 0.05
CHUNK_SIZE = 16384  # 16KiB
MAX_DOCUMENT_SIZE = 2 * 1024 * 1024  # Document limit in bytes (2MiB)
CLEANUP_ON_INDEX = True
IGNORE_SSL = False

# Prevent the constant nagging about SSL verification
if IGNORE_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print(
        "Running without SSL verification - This can cause authenticity/security issues..."
    )


class DocumentTooLargeError(Exception):
    """
    Custom exception raised to indicate, that a document exceeds the defined
    upper document size.
    """


def __clean_url(url: str) -> str | None:
    """
    Remove query and fragment part of urls
    Only keeps urls which scheme is either http/https
    (Filters unwanted protocols like tel/mailto)
    """
    parsed = urlsplit(url)._replace(query="", fragment="")
    if parsed.scheme.lower() in ["http", "https"]:
        return urlunsplit(parsed).rstrip("/")
    return None


def __download_with_limit(
    site_url: str,
    file_path: str,
    cb0: Callable[[int], None] | None = None,
    cb1: Callable[[int], None] | None = None,
    limit: int = MAX_DOCUMENT_SIZE,
) -> None:
    res = requests.get(
        site_url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        stream=True,
        timeout=CRAWL_TIMEOUT,
        verify=not IGNORE_SSL,
    )
    res.raise_for_status()

    try:
        reported_total = int(res.headers.get("content-length", 0))
    # If the server sends something malformed default to 0
    except (ValueError, TypeError):
        reported_total = 0

    if reported_total > MAX_DOCUMENT_SIZE:
        raise DocumentTooLargeError(
            f"Document at {site_url} exceeds the limit of {MAX_DOCUMENT_SIZE} bytes."
        )

    if cb0:
        cb0(reported_total)

    total_bytes = 0
    with open(file_path, "wb") as f:
        for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                total_bytes += len(chunk)
                if cb1:
                    cb1(len(chunk))

                if total_bytes >= MAX_DOCUMENT_SIZE:
                    raise DocumentTooLargeError(
                        f"Document at {site_url} exceeds the limit of {MAX_DOCUMENT_SIZE} bytes."
                    )
                f.write(chunk)


def __parse_robots(site_url: str) -> RobotFileParser:
    """
    Tries to read/get the robots.txt
    Defaults to allow everything, if parsing fails. (Not Found/Invalid Cert)
    """
    url_seg = urlsplit(site_url)
    robots_path = f".cache/robots/{Path(url_seg.netloc).name}"
    robots_file = Path(robots_path)
    rp = RobotFileParser()

    try:
        if not robots_file.is_file():
            __download_with_limit(
                urlunsplit(url_seg._replace(path="/robots.txt")), robots_path
            )

        with open(robots_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        rp.parse(lines)
    except (
        RequestException,
        ConnectionError,
        DocumentTooLargeError,
        UnicodeDecodeError,
    ):
        # Create an empty file to avoid unneeded requests
        if robots_file.is_file():
            robots_file.unlink()

        robots_file.touch()
        rp = RobotFileParser()
        rp.parse([])
    except (FileNotFoundError, PermissionError, OSError):
        print(f"Failed to create file at {robots_path}...")
        rp = RobotFileParser()
        rp.parse([])

    return rp


def __parse_document(cache_path: str, site_url: str) -> dict[str, str | list(str)] | None:
    """
    Extracts text content and links from a given document.
    """
    try:
        with open(cache_path, "r", encoding="utf-8") as document:
            soup = BeautifulSoup(document, "html.parser")
    except (FileNotFoundError, PermissionError, OSError):
        return None

    title = soup.title.extract().string if soup.title else None

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag["content"] if desc_tag and desc_tag.has_attr("content") else None

    # Extract links from document
    links = {
        link
        for element in soup.find_all("a", href=True)
        if (link := __clean_url(urljoin(site_url, element["href"])))
        # Maybe limit MAX PATH DEPTH?: if len(link.split('/')) > MAX_PATH_DEPTH + 2
    }

    # Remove non content elements (e.g. nav, header, footer, aside)
    # This should be relatively safe, since modern sites
    # use semantic tags like <main> for their content and
    # nav elements don't really contribute to the actual
    # content of a page.
    for tag in ["nav", "header", "footer", "aside"]:
        for element in soup.find_all(tag):
            element.decompose()

    # Replace images with their alt text
    for element in soup.find_all("img"):
        alt = element.get("alt")
        if alt and (" " in alt or alt.isalnum()):
            element.replace_with(alt)
        else:
            element.decompose()

    return {
        "title": title,
        "desc": desc,
        "content": soup.get_text(separator=" ", strip=True),
        "links": list(links),
    }


def __download_worker(
    frontier: Queue,
    index_queue: Queue,
    d_progress: Progress,
    d_task_id: int,
    i_task_id: int,
) -> None:
    with storage.access() as store:
        while True:
            try:
                doc_id, site_url, depth = frontier.get(timeout=120)
            except Empty:
                print(
                    "Worker timed out, either the indexing took too long or there might be an issue.",
                    "Try again and restart the crawler process to hopefully fix this issue.",
                )
                break
            except ShutDown:
                break

            try:
                with Progress(
                    DownloadColumn(),
                    BarColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    TimeRemainingColumn(),
                ) as progress:
                    task_info = [None]

                    def cb0(
                        total: int,
                        task_info: list = task_info,
                        site_url: str = site_url,
                    ):
                        task_info[0] = progress.add_task(site_url, total=total)

                    def cb1(chunk_size: int, task_info: list = task_info):
                        progress.advance(task_info[0], chunk_size)

                    __download_with_limit(site_url, f".cache/crawler/{doc_id}", cb0, cb1)
                    store.update_status(doc_id, storage.DocumentStatus.CACHED)
                    sleep(CRAWLER_DELAY)
            except (RequestException, ConnectionError, DocumentTooLargeError) as e:
                print(
                    f"[{current_thread().name}] Failed to download document from {site_url}:\n\t{e}"
                )

                # Cleanup partial files
                file = Path(f".cache/crawler/{doc_id}")
                if file.is_file():
                    file.unlink()
            except (FileNotFoundError, PermissionError, OSError) as e:
                print(
                    f"[{current_thread().name}] Failed to cache document - Exiting...\n\t{e}"
                )
                break
            finally:
                index_queue.put((doc_id, site_url, depth, i_task_id))
                d_progress.advance(d_task_id, 1)
                frontier.task_done()


def __index_worker(queue: Queue, progress: Progress) -> None:
    with storage.access() as store:
        while True:
            try:
                doc_id, site_url, depth, task_id = queue.get(timeout=120)
            except Empty:
                print(
                    "Indexer timed out, either the indexing took too long or there might be an issue.",
                    "Try again and restart the crawler process to hopefully fix this issue.",
                )
                break
            except ShutDown:
                break

            try:
                site = __parse_document(f".cache/crawler/{doc_id}", site_url)
                if site:
                    if site["content"] and index(doc_id, site):
                        store.update_status(doc_id, storage.DocumentStatus.READY)
                    else:
                        store.update_status(doc_id, storage.DocumentStatus.SKIPPED)

                    # Add links to frontier
                    if site["links"]:
                        netlocs = {
                            urlunsplit(urlsplit(link)._replace(path=""))
                            for link in site["links"]
                        }

                        with ThreadPoolExecutor(max_workers=CRAWLER_COUNT) as executor:
                            futures = {
                                netloc: executor.submit(__parse_robots, netloc)
                                for netloc in netlocs
                            }

                            robots = {
                                urlsplit(netloc).netloc: future.result()
                                for netloc, future in futures.items()
                            }

                        # Append filtered links to frontier
                        store.offer_frontier(
                            [
                                (link, depth + 1)
                                for link in site["links"]
                                if robots[urlsplit(link).netloc].can_fetch(
                                    USER_AGENT, link
                                )
                            ],
                            doc_id,
                        )

                else:
                    store.update_status(doc_id, storage.DocumentStatus.ERROR)
            except (
                FileNotFoundError,
                PermissionError,
                OSError,
                RequestException,
                ConnectionError,
                DocumentTooLargeError,
            ):
                store.update_status(doc_id, storage.DocumentStatus.ERROR)
            finally:
                try:
                    file_path = Path(f".cache/crawler/{doc_id}")
                    if CLEANUP_ON_INDEX and file_path.is_file():
                        file_path.unlink()
                except (FileNotFoundError, PermissionError, OSError):
                    pass

                progress.advance(task_id, 1)
                queue.task_done()


def crawl() -> None:
    # Ensure cache dirs are present
    for cache_dir in ["robots", "crawler"]:
        Path(f".cache/{cache_dir}").mkdir(parents=True, exist_ok=True)

    with storage.access() as store, Progress() as progress:
        index_queue = Queue(maxsize=1000)
        indexer = Thread(
            target=__index_worker,
            args=(
                index_queue,
                progress,
            ),
        )
        indexer.start()

        for depth in range(CRAWL_DEPTH + 1):
            total = store.count_frontier(depth)
            cached_docs = store.get_cache(depth)

            task_id = progress.add_task(f"[Download] {depth} - Depth", total=total)
            index_task_id = progress.add_task(
                f"[Index] {depth} - Depth", total=total + len(cached_docs)
            )
            if total > 0:
                frontier_queue = Queue(maxsize=CRAWLER_COUNT * 2)
                crawlers = []

                for i in range(CRAWLER_COUNT):
                    t = Thread(
                        target=__download_worker,
                        args=(
                            frontier_queue,
                            index_queue,
                            progress,
                            task_id,
                            index_task_id,
                        ),
                        name=f"Crawler-{i}",
                    )
                    crawlers.append(t)
                    t.start()

                while frontier := store.poll_frontier(50, depth):
                    for task in frontier:
                        frontier_queue.put(task)

                # Make sure we don't overlap depth, so we can
                # get the total amount of sites to crawl for
                # any given depth
                frontier_queue.join()
                frontier_queue.shutdown()
                for c in crawlers:
                    c.join()

            # Append cached docs to indexing Queue
            for cached_doc in cached_docs:
                doc_id, site_url, depth = cached_doc
                index_queue.put((doc_id, site_url, depth, index_task_id))

            index_queue.join()

    index_queue.shutdown()
    indexer.join()

    with storage.access() as store:
        store.rank_pages()
        print("Crawling/Indexing complete")
        print(f"Sites indexed: {store.count_index()}")


with storage.access() as store:
    store.init()
    # Add Seed URLS at depth 0
    store.offer_frontier([
            ("https://uni-tuebingen.de/en", 0),
            ("https://en.wikipedia.org/wiki/T%C3%BCbingen", 0),
            ("https://en.wikipedia.org/wiki/University_of_T%C3%BCbingen", 0),
    ])

crawl()
