import sqlite3
from contextlib import contextmanager
from collections.abc import Generator
from enum import IntEnum
from uuid import UUID, uuid7
import json

class DocumentStatus(IntEnum):
    PENDING = 0,
    QUEUED = 1,
    INDEXED = 2,
    READY = 3

# TODO: Replace mock with DB
class Storage:

    def __init__(self):
        self._db = sqlite3.connect('mse.db', timeout=5.0)
        self._cur = self._db.cursor()

    def init(self):
        self._cur.execute('''CREATE TABLE IF NOT EXISTS documents (
            id BLOB PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            length INTEGER,
            depth INTEGER NOT NULL,
            status INTEGER NOT NULL DEFAULT 0
        ) STRICT, WITHOUT ROWID''')
        
        self._cur.execute('''CREATE TABLE IF NOT EXISTS terms (
            id BLOB PRIMARY KEY,
            term TEXT UNIQUE NOT NULL
        ) STRICT, WITHOUT ROWID''')

        self._cur.execute('''CREATE TABLE IF NOT EXISTS postings (
            term_id BLOB REFERENCES term(id) NOT NULL,
            doc_id BLOB REFERENCES doc(id) NOT NULL,
            tf INTEGER NOT NULL,
            PRIMARY KEY (term_id, doc_id)
        ) STRICT, WITHOUT ROWID''')

        self._cur.execute(f'''UPDATE documents
        SET status = {DocumentStatus.PENDING}
        WHERE status != {DocumentStatus.READY}''')

        self._db.commit()

    # TODO: Store metadata for domains to prevent spider linking
    def add_netloc(self, netloc: str):
        pass

    def offer_frontier(self, link: (str, int) | list[(str, int)]):
        if not isinstance(link, list):
            link = [link]

        self._cur.executemany(
            'INSERT INTO documents (id, url, depth) VALUES (?, ?, ?) ON CONFLICT DO NOTHING',
            [(uuid7().bytes, url, depth) for url, depth in link]
        )
        self._db.commit()

    def poll_frontier(self, max: int = 100) -> list[(UUID, str, int)]:
        query = f"""WITH rows AS (
            SELECT id
            FROM documents
            WHERE status = {DocumentStatus.PENDING}
            ORDER BY depth
            LIMIT ?
        )
        UPDATE documents
        SET status = {DocumentStatus.QUEUED}
        WHERE id in rows
        RETURNING id, url, depth
        """

        results = self._cur.execute(query, [max]).fetchall()
        self._db.commit()
        return [(UUID(bytes=byte_id), url, depth) for byte_id, url, depth in results]

    def update_document(self, doc_id: UUID, doc_length: int | None):
        self._cur.execute(f'UPDATE documents SET length = ?, status = {DocumentStatus.READY} WHERE id = ?', [doc_length, doc_id.bytes])
        self._db.commit()

    def add_posting(self, doc_id: UUID, posting: (str, int) | list[(str, int)]):
        if not isinstance(posting, list):
            posting = [posting]

        # Make sure all terms exist
        self._cur.execute(
            f'INSERT INTO terms (id, term) VALUES {', '.join(["(?, ?)"] * len(posting))} ON CONFLICT(term) DO UPDATE SET term = term RETURNING term, id',
            [item for term, _ in posting for item in (uuid7().bytes, term)]
        )

        term_mappings = dict(self._cur.fetchall())
        self._db.commit()

        # Make sure we delete all "old" postings first
        self._cur.execute('DELETE FROM postings WHERE doc_id = ?', [doc_id.bytes])
        self._cur.executemany(
            'INSERT INTO postings (term_id, doc_id, tf) VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET tf = excluded.tf',
            [(term_mappings[term], doc_id.bytes, tf) for term, tf in posting]
        )

        self._db.commit()

    def get_postings(self, terms: list[str]) -> (dict, dict, float, int):
        query = f"""WITH rows AS (
            SELECT term_id, doc_id, tf
            FROM postings
            WHERE term_id IN (SELECT id FROM terms WHERE term IN ({','.join(['?'] * len(terms))}))
        ),
        term_postings AS (
            SELECT
                term_id,
                json_group_object(lower(hex(doc_id)), tf) AS docs
            FROM rows
            GROUP BY term_id
        ),
        agg_postings AS (
            SELECT json_group_object(lower(hex(term_id)), docs) AS postings
            FROM term_postings
        ),
        doc_meta AS (
            SELECT
                json_group_object(lower(hex(id)), length) FILTER (WHERE EXISTS (SELECT 1 FROM rows WHERE doc_id = id)) AS lengths,
                avg(length) AS avg_length,
                count(*) AS total
            FROM documents
        )
        SELECT
            postings,
            lengths,
            avg_length,
            total
        FROM agg_postings
        CROSS JOIN doc_meta"""

        self._cur.execute(query, terms)
        postings, lengths, avg_length, total = self._cur.fetchone()

        postings = {
            UUID(hex=term_id): {
                UUID(hex=term_id): tf
                for doc_id, tf in json.loads(docs).items()
            } for term_id, docs in json.loads(postings).items()
        }
        lengths = { UUID(hex=doc_id): length for doc_id, length in json.loads(lengths).items() }

        # ({ term_id: { doc_id: term_frequency, ... }, ... }, { doc_id: doc_length, ... }, avg_document_length, total_document_count)
        return postings, lengths, avg_length, total

    def close(self):
        self._cur.close()
        self._db.close()

@contextmanager
def access() -> Generator[Storage, None, None]:
    storage = Storage()

    try:
        yield storage
    finally:
        storage.close()
        del storage
