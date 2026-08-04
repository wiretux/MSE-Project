from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import JoinableQueue, Process, Queue as MPQueue
from pathlib import Path
from queue import Empty, Queue, ShutDown
from threading import Thread, current_thread
from time import sleep
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, RequestException, HTTPError
from rich.progress import Progress

from indexer import index, precalc_embeddings
from utils import storage

USER_AGENT = "MSE-Crawler"  # User Agent used when crawling
CRAWL_DEPTH = 1  # Maximum distance/depth crawler may deviate from seed urls
CRAWL_TIMEOUT = 10  # Timeout in seconds
CRAWLER_COUNT = 12
CRAWLER_DELAY = 0.1
CHUNK_SIZE = 16384  # 16KiB
MAX_DOCUMENT_SIZE = 2 * 1024 * 1024  # Document limit in bytes (2MiB)
CLEANUP_ON_INDEX = True
IGNORE_SSL = False
MAX_INDEXERS = 12
PAGE_RANK_N = 10

# In-memory dictionary to store compiled RobotFileParser instances per worker process
_ROBOTS_RAM_CACHE: dict[str, RobotFileParser] = {}

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
    type: str = "text/html"
) -> None:
    res = requests.get(
        site_url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        stream=True,
        timeout=CRAWL_TIMEOUT,
        verify=not IGNORE_SSL,
    )
    res.raise_for_status()

    # Avoid downloading ""
    if type not in res.headers.get("Content-Type", "").lower():
        raise TypeError("Content-Type differs from supplied type")

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
    domain = url_seg.netloc

    # Check in-memory RAM cache first
    if domain in _ROBOTS_RAM_CACHE:
        return _ROBOTS_RAM_CACHE[domain]

    robots_path = f".cache/robots/{Path(domain).name}"
    robots_file = Path(robots_path)
    rp = RobotFileParser()

    try:
        if not robots_file.is_file():
            __download_with_limit(
                urlunsplit(url_seg._replace(path="/robots.txt")), robots_path, type="text/plain"
            )

        with open(robots_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        rp.parse(lines)
    except (
        RequestException,
        ConnectionError,
        DocumentTooLargeError,
        UnicodeDecodeError,
        TypeError,
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

    # Store compiled parser in RAM cache before returning
    _ROBOTS_RAM_CACHE[domain] = rp
    return rp


def __parse_document(cache_path: str, site_url: str) -> dict[str, str | list[str]] | None:
    """
    Extracts text content and links from a given document.
    """
    try:
        with open(cache_path, "r", encoding="utf-8") as document:
            soup = BeautifulSoup(document, "lxml")


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
    except Exception:
        return None


def __download_worker(
    frontier: Queue,
    index_queue: JoinableQueue,
    d_progress: Progress,
    d_task_id: int,
    i_task_id: int,
) -> None:
    with storage.access() as store:
        while True:
            try:
                doc_id, site_url, depth = frontier.get(timeout=120)
                valid = None
            except Empty:
                print(
                    "Worker timed out, either the indexing took too long or there might be an issue.",
                    "Try again and restart the crawler process to hopefully fix this issue.",
                )
                break
            except ShutDown:
                break

            try:
                __download_with_limit(site_url, f".cache/crawler/{doc_id}")
                store.update_status(doc_id, storage.DocumentStatus.CACHED)
                valid = True
                sleep(CRAWLER_DELAY)
            # Skip non-html documents
            except TypeError:
                store.update_status(doc_id, storage.DocumentStatus.SKIPPED)
                valid = False
            # Skip non-html documents
            except HTTPError as e:
                print(
                    f"[{current_thread().name}] Failed to download document from {site_url}:\n\t{e}"
                )

                if e.response.status_code in [401, 403, 404]:
                    store.update_status(doc_id, storage.DocumentStatus.SKIPPED)
                    valid = False
            except (RequestException, ConnectionError, DocumentTooLargeError) as e:
                print(
                    f"[{current_thread().name}] Failed to download document from {site_url}:\n\t{e}"
                )

                # Cleanup partial files
                file = Path(f".cache/crawler/{doc_id}")
                if file.is_file():
                    file.unlink()

                store.update_status(doc_id, storage.DocumentStatus.ERROR)
            except (FileNotFoundError, PermissionError, OSError) as e:
                print(
                    f"[{current_thread().name}] Failed to cache document - Exiting...\n\t{e}"
                )
                break
            finally:
                index_queue.put((doc_id, site_url, depth, i_task_id, valid))
                d_progress.advance(d_task_id, 1)
                frontier.task_done()


def __index_worker(in_queue: JoinableQueue, progress_queue: MPQueue) -> None:
    with storage.access() as store:
        while True:
            try:
                item = in_queue.get(timeout=120)
                if item is None:
                    in_queue.task_done()
                    break
                doc_id, site_url, depth, task_id, valid = item
            except Empty:
                print(
                    "Indexer timed out, either the indexing took too long or there might be an issue.",
                    "Try again and restart the crawler process to hopefully fix this issue.",
                )
                break
            except ShutDown:
                break

            try:
                # If not valid try not to index
                if not valid:
                    continue

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

                progress_queue.put(task_id)
                in_queue.task_done()


def crawl() -> None:
    # Ensure cache dirs are present
    for cache_dir in ["robots", "crawler"]:
        Path(f".cache/{cache_dir}").mkdir(parents=True, exist_ok=True)

    with storage.access() as store, Progress() as progress:
        index_queue = JoinableQueue(maxsize=1000)
        progress_queue = MPQueue()

        indexers = []
        for i in range(MAX_INDEXERS):
            p = Process(
                target=__index_worker,
                args=(index_queue, progress_queue),
                name=f"Indexer-{i}"
            )
            p.start()
            indexers.append(p)

        def progress_updater():
            while True:
                task_id = progress_queue.get()
                if task_id is None:
                    break
                progress.advance(task_id, 1)

        updater_thread = Thread(target=progress_updater, daemon=True)
        updater_thread.start()

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
                index_queue.put((doc_id, site_url, depth, index_task_id, True))

            index_queue.join()

        for _ in range(MAX_INDEXERS):
            index_queue.put(None)
        for p in indexers:
            p.join()

        progress_queue.put(None)
        updater_thread.join()

        index_count = store.count_index()
        embedding_count = store.count_embeddings()

        if index_count - embedding_count > 0:
            task_id = progress.add_task("[Embeddings]", total=index_count-embedding_count)
            precalc_embeddings(progress, task_id)
        
        task_id = progress.add_task("[PageRank]", total=PAGE_RANK_N)
        store.rank_pages(PAGE_RANK_N, progress=progress, task_id=task_id)

    print(f"[Completed] Websites indexed: {index_count}")

if __name__ == "__main__":
    with storage.access() as store:
        store.init()
        # Add Seed URLS at depth 0
        store.offer_frontier([
                ("https://uni-tuebingen.de/en", 0)
                #("https://en.wikipedia.org/wiki/T%C3%BCbingen", 0),
                #("https://en.wikipedia.org/wiki/University_of_T%C3%BCbingen", 0),
        ])

    crawl()
