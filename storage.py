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

    def get_postings(self, terms: list[str]) -> dict:
        query = """WITH rows AS (
            SELECT term_id, doc_id, term_frequency 
            FROM postings 
            WHERE term IN (?)
        ), 
        term_postings AS (
            SELECT 
                term_id, 
                json_group_array(json_object('doc', doc_id, 'tf', term_frequency)) AS docs 
            FROM rows 
            GROUP BY term_id
        ),
        aggregated_postings AS (
            SELECT json_group_array(json_object('term', term_id, 'docs', docs)) AS postings 
            FROM term_postings
        ),
        doc_meta AS (
            SELECT 
                json_group_array(json_object('doc', id, 'length', length)) AS lengths,
                avg(length) AS avg_length,
                count(*) AS total
            FROM documents
            WHERE EXISTS (SELECT 1 FROM rows WHERE doc_id = id)
        )
        SELECT 
            postings,
            lengths,
            avg_length,
            total
        FROM aggregated_postings
        CROSS JOIN doc_meta;"""

        # Mock Data:
        return {
            'postings': [
                { 'term': 1, 'docs': [{ 'id': 1, 'tf': 1 }, { 'id': 2, 'tf': 3 }, { 'id': 3, 'tf': 1 }] },
                { 'term': 2, 'docs': [{ 'id': 1, 'tf': 3 }] }
            ],
            'lengths': [{ 'doc': 1, 'length': 5 }, { 'doc': 2, 'length': 10 }, { 'doc': 3, 'length': 15 }],
            'avg_length': 10.0,
            'total': 3
        }

        # Alternatively we could use this format:
        # {
        #     'postings': {
        #         {
        #            '1': { '1': 1, '2': 3, '3': 1 },
        #            '2': { '1': 3 }
        #         }
        #     },
        #     'lengths': { '1': 5 '2': 10, '3': 15 },
        #     'avg_length': 10.0,
        #     'total': 3
        # }

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