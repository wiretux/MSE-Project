import sqlite3
from contextlib import contextmanager
from collections.abc import Generator

# TODO: Replace mock with DB
class Storage:

    def __init__(self):
        #self._db = sqlite3.connect('mse.db', timeout=5.0)
        self.frontier = ['https://uni-tuebingen.de', 'https://uni-tuebingen.de/en']

    def add_netloc(self, netloc: str):
        pass

    def remove_netloc(self, netloc: str):
        pass

    def offer_frontier(self, links: str | list[str]):
        self.frontier.extend(links)

    def poll_frontier(self, max: int = 100) -> list[str]:
        if len(self.frontier) < 1:
            return []
        return [self.frontier.pop()]

    def add_posting(self):
        pass

    def remove_posting(self):
        pass

    def get_postings(self, terms: list[str]):
        pass

    def close(self):
        #self._db.close()
        pass
    

@contextmanager
def access() -> Generator[Storage, None, None]:
    storage = Storage()

    try:
        yield storage
    finally:
        storage.close()
        del storage