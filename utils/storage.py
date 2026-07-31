import sqlite3
from contextlib import contextmanager
from collections.abc import Generator
from enum import IntEnum
from uuid import UUID, uuid7
import json
import array

class DocumentStatus(IntEnum):
    PENDING = 0,
    QUEUED = 1,
    INDEXED = 2,
    READY = 3,

    SKIPPED = 254,
    ERROR = 255

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

        self._cur.execute('''CREATE TABLE IF NOT EXISTS embeddings (
            doc_id BLOB PRIMARY KEY REFERENCES doc(id) NOT NULL,
            embedding BLOB NOT NULL
        ) STRICT, WITHOUT ROWID''')

        self._cur.execute(f'''UPDATE documents
        SET status = {DocumentStatus.PENDING}
        WHERE status < {DocumentStatus.READY}''')

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

    def count_frontier(self, depth: int = 0):
        self._cur.execute(f'SELECT count(*) FROM documents WHERE status = {DocumentStatus.PENDING} AND depth = ?', [depth])
        return self._cur.fetchone()[0]

    def poll_frontier(self, max: int = 100, max_depth: int = 100) -> list[(UUID, str, int)]:
        query = f"""WITH rows AS (
            SELECT id
            FROM documents
            WHERE status = {DocumentStatus.PENDING} AND depth <= ?
            ORDER BY depth
            LIMIT ?
        )
        UPDATE documents
        SET status = {DocumentStatus.QUEUED}
        WHERE id in rows
        RETURNING id, url, depth
        """

        results = self._cur.execute(query, [max_depth, max]).fetchall()
        self._db.commit()
        return [(UUID(bytes=byte_id), url, depth) for byte_id, url, depth in results]

    def update_status(self, doc_id: UUID, status: DocumentStatus = DocumentStatus.READY):
        self._cur.execute(f'UPDATE documents SET status = ? WHERE id = ?', [status, doc_id.bytes])
        self._db.commit()

    def update_length(self, doc_id: UUID, doc_length: int | None):
        self._cur.execute(f'UPDATE documents SET length = ? WHERE id = ?', [doc_length, doc_id.bytes])
        self._db.commit()

    def count_index(self):
        self._cur.execute(f'SELECT count(*) FROM documents WHERE status = {DocumentStatus.READY}')
        return self._cur.fetchone()[0]

    def add_embedding(self, doc_id: UUID, doc_embedding: list[float]):
        embedding_blob = array.array('f', doc_embedding).tobytes()
        self._cur.execute(
                    'INSERT INTO embeddings (doc_id, embedding) VALUES (?, ?) ON CONFLICT DO NOTHING',
                    [doc_id.bytes, embedding_blob]
                )
        self._db.commit()

    def get_embedding(self, doc_ids: UUID | list[UUID]) -> dict[UUID, list[float]]:
        if not doc_ids:
            return {}

        if not isinstance(doc_ids, list):
            doc_ids = [doc_ids]

        # Limit to 900 to stay below SQLites legacy 999 parameter limit.
        # Fetching more embeddings at once should not be done in the first place.
        if len(doc_ids) > 900:
            raise ValueError(f'Too many document embeddings requested: {len(doc_ids)}. Maximum allowed is 900')

        byte_ids = [doc_id.bytes for doc_id in doc_ids]

        query = f"SELECT doc_id, embedding FROM embeddings WHERE doc_id IN ({','.join(['?'] * len(byte_ids))})"

        self._cur.execute(query, byte_ids)
        rows = self._cur.fetchall()

        return {
            UUID(bytes=byte_id): array.array('f', embedding_blob).tolist()
            for byte_id, embedding_blob in rows
        }

    def add_posting(self, doc_id: UUID, posting: (str, int) | list[(str, int)]):
        if not isinstance(posting, list):
            posting = [posting]

        if len(posting) < 1:
            return

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

    def get_postings(self, terms: list[str], max: int = 2000) -> (dict, dict, float, int):
        # TODO: Maybe replace pre-score with term-/posting-level filter
        query = f"""
        WITH corpus_meta AS (
            SELECT count(*) AS N,
                avg(length) AS avg_length
            FROM documents
            WHERE status = 3
        ),
        term_meta AS (
            SELECT id,
                corpus_meta.N / count(doc_id) AS idf
            FROM terms
            CROSS JOIN corpus_meta
            JOIN postings ON postings.term_id = id
            WHERE term IN ({','.join(['?'] * len(terms))})
            GROUP BY id, N
        ),
        docs AS (
            SELECT doc_id AS id,
                length,
                json_group_object(lower(hex(term_id)), tf) AS terms,
                sum(idf * tf) AS estimated_score
            FROM postings
            JOIN term_meta ON term_id = term_meta.id
            JOIN documents ON doc_id = documents.id
            GROUP BY doc_id
            ORDER BY estimated_score DESC
            LIMIT {max}
        )
        SELECT
            (SELECT json_group_object(lower(hex(id)), json_object('terms', terms, 'length', length)) FROM docs),
            (SELECT json_group_object(lower(hex(id)), idf) FROM term_meta),
            avg_length,
            N
        FROM corpus_meta
        """

        self._cur.execute(query, terms)
        postings, term_meta, avg_length, total = self._cur.fetchone()

        postings = {
            UUID(hex=doc_id): {
                'terms': { UUID(hex=term_id): tf for term_id, tf in json.loads(values['terms']).items() },
                'length': values['length']
            }
            for doc_id, values in json.loads(postings).items()
        }
        term_meta = { UUID(hex=term_id): idf for term_id, idf in json.loads(term_meta).items() }

        # ({ doc_id: { terms: { term_id: term_frequency, ... }, length: length }, ... }, { term_id: idf, ... }, avg_document_length, total_document_count)
        return postings, term_meta, avg_length, total

    def get_documents(self, doc_ids: UUID | list[UUID]) -> dict[UUID, dict]:
        if not doc_ids:
            return {}

        if not isinstance(doc_ids, list):
            doc_ids = [doc_ids]

        # Limit to 900 to stay below SQLites legacy 999 parameter limit.
        # Fetching more documents at once should not be done in the first place.
        if len(doc_ids) > 900:
            raise ValueError(f'Too many documents requested: {len(doc_ids)}. Maximum allowed is 900')

        byte_ids = [doc_id.bytes for doc_id in doc_ids]

        # TODO Extract the data needed for the ui

        query = f"""
        SELECT id, url, title, description, length, depth
        FROM documents
        WHERE id IN ({','.join(['?'] * len(byte_ids))})
        """

        self._cur.execute(query, byte_ids)
        rows = self._cur.fetchall()

        return {
        UUID(bytes=doc_id): {
            "url": url,
            "title": title if title is not None else "[Untitled]",
            "description": description if description is not None else "[No description]",
            "length": length,
            "depth": depth
            }
            for doc_id, url, title, description, length, depth in rows
        }

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
