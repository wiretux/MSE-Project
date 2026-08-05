import array
import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from enum import IntEnum
from uuid import UUID, uuid7

from nltk.metrics import jaccard_distance
from rich.progress import Progress

from utils.hash import hamming_distance

SIM_DISTANCE = 0.02


class DocumentStatus(IntEnum):
    PENDING = (0,)
    QUEUED = (1,)
    CACHED = (2,)
    READY = (3,)
    SKIPPED = (254,)
    ERROR = 255


class Storage:
    def __init__(self):
        self._db = sqlite3.connect("mse.db", timeout=30.0, isolation_level="IMMEDIATE")
        self._db.execute("PRAGMA journal_mode=WAL;")
        self._db.create_function("HAMMING", 2, hamming_distance)
        self._cur = self._db.cursor()

    def init(self) -> None:
        """
        Initialize the databases and reset wrong state
        """
        self._cur.execute("""CREATE TABLE IF NOT EXISTS documents (
            id BLOB PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            length INTEGER,
            depth INTEGER NOT NULL,
            content_id BLOB,
            rank REAL NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 0
        ) STRICT, WITHOUT ROWID""")

        self._cur.execute("""CREATE TABLE IF NOT EXISTS content (
            id BLOB PRIMARY KEY,
            sim_hash BLOB NOT NULL,
            data TEXT NOT NULL,
            ai_score REAL
        )""")

        self._cur.execute("""CREATE TABLE IF NOT EXISTS links (
            source BLOB REFERENCES doc(id) NOT NULL,
            target BLOB REFERENCES doc(id) NOT NULL,
            PRIMARY KEY (source, target)
        ) STRICT, WITHOUT ROWID""")

        self._cur.execute("""CREATE TABLE IF NOT EXISTS terms (
            id BLOB PRIMARY KEY,
            term TEXT UNIQUE NOT NULL
        ) STRICT, WITHOUT ROWID""")

        self._cur.execute("""CREATE TABLE IF NOT EXISTS postings (
            term_id BLOB REFERENCES term(id) NOT NULL,
            doc_id BLOB REFERENCES doc(id) NOT NULL,
            tf INTEGER NOT NULL,
            PRIMARY KEY (term_id, doc_id)
        ) STRICT, WITHOUT ROWID""")

        self._cur.execute("""CREATE TABLE IF NOT EXISTS embeddings (
            doc_id BLOB PRIMARY KEY REFERENCES doc(id) NOT NULL,
            embedding BLOB NOT NULL
        ) STRICT, WITHOUT ROWID""")

        # Retry stale or broken documents
        self._cur.execute(f"""UPDATE documents
        SET status = {DocumentStatus.PENDING}
        WHERE status == {DocumentStatus.QUEUED} OR
        status == {DocumentStatus.ERROR}""")

        self._db.commit()

    def offer_frontier(
        self, link: tuple[str, int] | list[tuple[str, int]], doc_id: str | None = None
    ) -> None:
        """
        Add links to the frontier
        """
        if not isinstance(link, list):
            link = [link]

        # Avoid inserts for nonexistent links
        if len(link) < 1:
            return

        self._cur.executemany(
            "INSERT INTO documents (id, url, depth) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            [(uuid7().bytes, url, depth) for url, depth in link],
        )

        if doc_id:
            self._cur.execute(
                f"""WITH target_ids AS (
                    SELECT id FROM documents
                    WHERE url IN ({",".join(["?"] * len(link))})
                ) INSERT INTO links (source, target) 
                SELECT ?, id FROM target_ids
                WHERE 1
                ON CONFLICT DO NOTHING
                """,
                [url for url, _ in link] + [doc_id.bytes],
            )
        self._db.commit()

    def count_frontier(self, depth: int = 0) -> int:
        """
        Count the number of links left in frontier
        """
        self._cur.execute(
            f"SELECT count(*) FROM documents WHERE status = {DocumentStatus.PENDING} AND depth = ?",
            [depth],
        )
        res = self._cur.fetchone()
        return res[0] if res else 0

    def poll_frontier(
        self, max: int = 100, max_depth: int = 100
    ) -> list[tuple[UUID, str, int]]:
        """
        Extract links from frontier limited to {max}
        """
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

    def store_content(self, content: str, sim_hash: bytes) -> tuple[bytes, bool]:
        """
        Try to store the content in the database, if it does not yet exist.
        Retrun (prev_content_id, False) if the content is already stored
        Otherwise (content_id, True)
        """
        self._cur.execute(
            "SELECT id, data FROM content WHERE HAMMING(sim_hash, ?) < 5 LIMIT 10",
            [sim_hash],
        )

        # Check for similarity of content and return stored content
        # on find
        most_similar = min(
            [
                (id, jaccard_distance(set(content.split()), set(data.split())))
                for id, data in self._cur.fetchall()
            ],
            key=lambda x: x[1],
            default=None,
        )

        if most_similar and most_similar[1] < SIM_DISTANCE:
            return (most_similar[0], False)

        content_id = hashlib.sha256(content.encode("utf-8"))
        self._cur.execute(
            "INSERT INTO content (id, sim_hash, data) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            [content_id.digest(), sim_hash, content],
        )
        self._db.commit()
        return (content_id.digest(), True)

    def get_cache(self, max_depth: int = 0) -> list[tuple[UUID, str, int]]:
        """
        Extract cached documents from database for indexing
        """
        query = f"""SELECT id, url, depth
        FROM documents
        WHERE status = {DocumentStatus.CACHED} AND depth <= ?
        ORDER BY depth
        """

        results = self._cur.execute(query, [max_depth]).fetchall()
        return [(UUID(bytes=byte_id), url, depth) for byte_id, url, depth in results]

    def update_status(
        self, doc_id: UUID, status: DocumentStatus = DocumentStatus.READY
    ) -> None:
        """
        Update the status of a document in the corpus
        """
        self._cur.execute(
            "UPDATE documents SET status = ? WHERE id = ?", [status, doc_id.bytes]
        )
        self._db.commit()

    def update_document(
        self, doc_id: UUID, title: str | None, desc: str | None, content_id: bytes | None, doc_length: int
    ) -> None:
        """
        Update the metadata of a document in the corpus
        """
        self._cur.execute(
            "UPDATE documents SET title = ?, description = ?, content_id = ?, length = ? WHERE id = ?",
            [title, desc, content_id, doc_length, doc_id.bytes],
        )
        self._db.commit()

    def count_index(self) -> int:
        """
        Count number of sucessfully indexed docuemnts
        """
        self._cur.execute(
            f"SELECT count(*) FROM documents WHERE status = {DocumentStatus.READY}"
        )
        res = self._cur.fetchone()
        return res[0] if res else 0

    def poll_content_for(self, id: UUID | list[UUID]) -> list[tuple[bytes, str | None, str | None, str]]:
        """
        Try to extract content from database for ondemand embedding generation
        """
        if not isinstance(id, list):
            id = [id]

        if not id:
            return []

        query = f"""SELECT d.id, d.title, d.description, data
        FROM documents d
        JOIN content ON d.content_id = content.id
        WHERE d.id IN ({",".join(["?"] * len(id))})
        """

        self._cur.execute(query, [i.bytes for i in id])
        return [(UUID(bytes=id), title, description, data) for id, title, description, data in self._cur.fetchall()]

    def poll_content_ai(self, max: int = 50) -> list[tuple[bytes, str]]:
        """
        Extract content from databases that has not yet been scored for AI limited to {max}.
        """
        self._cur.execute(f"SELECT id, data FROM content WHERE ai_score is NULL LIMIT {max}")
        return [(id, data) for id, data in self._cur.fetchall()]

    def add_ai_score(self, content_id: bytes, score: float = 0.0) -> None:
        """
        Add ai_score label to content in database.
        """
        self._cur.execute("UPDATE content SET ai_score = ? WHERE id = ?", [score, content_id])
        self._db.commit()

    def count_missing_ai_score(self):
        """
        Count number of missing ai_score labels in database.
        """
        self._cur.execute("SELECT count(*) FROM content WHERE ai_score IS NULL")
        res = self._cur.fetchone()
        return res[0] if res else 0

    def poll_content(self, max: int = 50) -> list[tuple[UUID, str | None, str | None, str]]:
        """
        Extract content from databases that is missing embeddings.
        """
        query = f"""
        SELECT d.id, d.title, d.description, content.data
        FROM documents d
        JOIN content ON content.id = d.content_id
        WHERE NOT EXISTS(SELECT 1 FROM embeddings e WHERE d.id = e.doc_id)
        AND status = {DocumentStatus.READY}
        LIMIT {max}
        """

        self._cur.execute(query)
        return [(UUID(bytes=id), title, desc, data) for id, title, desc, data in self._cur.fetchall()]

    def add_embedding(self, doc_id: UUID, doc_embedding: list[float]) -> None:
        """
        Add embedding to database.
        """
        embedding_blob = array.array("f", doc_embedding).tobytes()
        self._cur.execute(
            "INSERT INTO embeddings (doc_id, embedding) VALUES (?, ?) ON CONFLICT DO NOTHING",
            [doc_id.bytes, embedding_blob],
        )
        self._db.commit()

    def count_embeddings(self):
        """
        Count number of embeddings exisitng in database
        """
        self._cur.execute("SELECT count(*) FROM embeddings")
        res = self._cur.fetchone()
        return res[0] if res else 0

    def rank_pages(self, iterations: int = 10, d_factor: float = 0.85, progress: Progress | None = None, task_id: int = None) -> None:
        """
        Calculate the page_rank inside the databases.
        """
        # Reset page rank
        self._cur.execute(f"""UPDATE documents
            SET rank = 1.0 / total
            FROM (SELECT count(*) AS total FROM documents WHERE status = {DocumentStatus.READY})
            WHERE status = {DocumentStatus.READY}
        """)
        self._db.commit()

        self._cur.execute(
            f"SELECT count(*) AS N FROM documents WHERE status = {DocumentStatus.READY}"
        )
        corpus_meta = self._cur.fetchone()

        # No valid documents in corpus, abort...
        if corpus_meta is None or corpus_meta[0] < 1:
            return

        N = corpus_meta[0]

        for i in range(iterations):
            self._cur.execute(f"""
                WITH ready_links AS (
                    SELECT links.* FROM links
                    JOIN documents ds
                        ON ds.id = links.source
                        AND ds.status = {DocumentStatus.READY}
                    JOIN documents dt
                        ON dt.id = links.target
                        AND dt.status = {DocumentStatus.READY}
                ), out_docs AS (
                    SELECT source AS id, count(*) AS count
                    FROM ready_links
                    GROUP BY source
                ), in_docs AS (
                    SELECT rl.target AS id,
                        sum(d.rank / od.count) AS sum_rank
                    FROM ready_links as rl
                    JOIN documents d ON rl.source = d.id
                    JOIN out_docs AS od ON rl.source = od.id
                    GROUP BY rl.target
                ) UPDATE documents
                    SET rank = {(1 - d_factor) / N} + {d_factor} * COALESCE(id.sum_rank, 0)
                FROM documents d
                LEFT JOIN in_docs id ON d.id = id.id
                WHERE documents.id = d.id AND documents.status = {DocumentStatus.READY}
            """)

            if progress and task_id:
                progress.advance(task_id, 1)
        self._db.commit()

    def get_embedding(self, doc_ids: UUID | list[UUID]) -> dict[UUID, list[float]]:
        """
        Extract the embeddings for documents from database.
        """
        if not doc_ids:
            return {}

        if not isinstance(doc_ids, list):
            doc_ids = [doc_ids]

        # Limit to 900 to stay below SQLites legacy 999 parameter limit.
        # Fetching more embeddings at once should not be done in the first place.
        if len(doc_ids) > 900:
            raise ValueError(
                f"Too many document embeddings requested: {len(doc_ids)}. Maximum allowed is 900"
            )

        byte_ids = [doc_id.bytes for doc_id in doc_ids]

        query = f"SELECT doc_id, embedding FROM embeddings WHERE doc_id IN ({','.join(['?'] * len(byte_ids))})"

        self._cur.execute(query, byte_ids)
        rows = self._cur.fetchall()

        return {
            UUID(bytes=byte_id): array.array("f", embedding_blob).tolist()
            for byte_id, embedding_blob in rows
        }

    def add_posting(self, doc_id: UUID, posting: tuple[str, int] | list[tuple[str, int]]):
        """
        Add postings to the database for a given document.
        """
        if not isinstance(posting, list):
            posting = [posting]

        if len(posting) < 1:
            return

        # Make sure all terms exist
        self._cur.execute(
            f"INSERT INTO terms (id, term) VALUES {', '.join(['(?, ?)'] * len(posting))} ON CONFLICT(term) DO UPDATE SET term = term RETURNING term, id",
            [item for term, _ in posting for item in (uuid7().bytes, term)],
        )

        term_mappings = dict(self._cur.fetchall())
        self._db.commit()

        # Make sure we delete all "old" postings first
        self._cur.execute("DELETE FROM postings WHERE doc_id = ?", [doc_id.bytes])
        self._cur.executemany(
            "INSERT INTO postings (term_id, doc_id, tf) VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET tf = excluded.tf",
            [(term_mappings[term], doc_id.bytes, tf) for term, tf in posting],
        )

        self._db.commit()

    def get_postings(
        self, terms: list[str], max: int = 2000
    ) -> tuple[dict, dict, float, int]:
        """
        Extract postings for a given set of terms.
        """
        query = f"""
        WITH corpus_meta AS (
            SELECT count(*) AS N,
                avg(length) AS avg_length
            FROM documents
            WHERE status = {DocumentStatus.READY}
        ),
        term_meta AS (
            SELECT id,
                corpus_meta.N / count(doc_id) AS idf,
                count(doc_id) AS doc_count
            FROM terms
            CROSS JOIN corpus_meta
            JOIN postings ON postings.term_id = id
            WHERE term IN ({",".join(["?"] * len(terms))})
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
            WHERE documents.status = {DocumentStatus.READY}
            GROUP BY doc_id
            ORDER BY estimated_score DESC
            LIMIT {max}
        )
        SELECT
            (SELECT json_group_object(lower(hex(id)), json_object('terms', terms, 'length', length)) FROM docs),
            (SELECT json_group_object(lower(hex(id)), doc_count) FROM term_meta),
            avg_length,
            N
        FROM corpus_meta
        """

        self._cur.execute(query, terms)
        postings, term_meta, avg_length, total = self._cur.fetchone()

        postings = {
            UUID(hex=doc_id): {
                "terms": {
                    UUID(hex=term_id): tf
                    for term_id, tf in json.loads(values["terms"]).items()
                },
                "length": values["length"],
            }
            for doc_id, values in json.loads(postings).items()
        }
        term_meta = {
            UUID(hex=term_id): idf for term_id, idf in json.loads(term_meta).items()
        }

        return postings, term_meta, avg_length, total

    def get_documents(self, doc_ids: UUID | list[UUID]) -> dict[UUID, dict]:
        """
        Extract documents and their metadata from database for ui presentation/batch processing.
        """
        if not doc_ids:
            return {}

        if not isinstance(doc_ids, list):
            doc_ids = [doc_ids]

        # Limit to 900 to stay below SQLites legacy 999 parameter limit.
        # Fetching more documents at once should not be done in the first place.
        if len(doc_ids) > 900:
            raise ValueError(
                f"Too many documents requested: {len(doc_ids)}. Maximum allowed is 900"
            )

        byte_ids = [doc_id.bytes for doc_id in doc_ids]

        query = f"""
        SELECT d.id, url, title, description, length, depth, rank, ai_score
        FROM documents d JOIN content ON content.id = d.content_id
        WHERE d.id IN ({",".join(["?"] * len(byte_ids))})
        """

        self._cur.execute(query, byte_ids)
        rows = self._cur.fetchall()

        return {
            UUID(bytes=doc_id): {
                "url": url,
                "title": title if title is not None else "[Untitled]",
                "description": description
                if description is not None
                else "[No description]",
                "length": length,
                "depth": depth,
                "rank": rank,
                "ai_score": ai_score if ai_score else 0.0
            }
            for doc_id, url, title, description, length, depth, rank, ai_score in rows
        }

    def close(self) -> None:
        self._cur.close()
        self._db.close()


@contextmanager
def access() -> Generator[Storage, None, None]:
    """
    Open a connection to databases and close it later.
    """
    storage = Storage()

    try:
        yield storage
    finally:
        storage.close()
        del storage
