"""
BM25 Search Engine
==================

Usage:
    python bm25.py "search query"

Example:
    python bm25.py "Digital, Transformation Lab?!!!"

The program returns the top 10 most relevant documents ranked by BM25 score and stores them in mse.db as:
search_results table (query, rank, url, score)

Requirements:
    - mse.db must be in the same directory as this file
    - Database must contain:
        * documents table (id, length, url)
        * terms table (id, term)
        * postings table (term_id, doc_id, tf)
        *
"""

import sqlite3
import re
import math
import sys

LIMIT = 10
# BM25 constants
K1 = 1.2
B = 0.75


# DB setup
conn = sqlite3.connect("mse.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_results (
        query TEXT,
        rank INTEGER,
        url TEXT,
        score REAL
    )
    """)

conn.commit()

# Get statistics
number_of_documents = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
average_document_length = cursor.execute(
    "SELECT AVG(length) FROM documents"
).fetchone()[0]


def search(query, limit=LIMIT):
    # Remove any punctioation
    query_terms = re.findall(r"\w+", query.lower())
    scores = {}
    document_urls = {}

    for term in query_terms:
        result = cursor.execute(
            "SELECT id FROM terms WHERE term = ?", (term,)
        ).fetchone()

        # Skip term doesn't exist in the corpus
        if result is None:
            continue

        term_id = result["id"]

        document_frequency = cursor.execute(
            "SELECT COUNT(*) FROM postings WHERE term_id = ?", (term_id,)
        ).fetchone()[0]

        if document_frequency == 0:
            continue

        # Calculate IDF
        idf = math.log(
            (number_of_documents - document_frequency + 0.5)
            / (document_frequency + 0.5)
            + 1
        )

        # Get every document containing term
        postings = cursor.execute(
            """
            SELECT
                p.doc_id,
                p.tf,
                d.length,
                d.url
            FROM postings p
            JOIN documents d
                ON p.doc_id = d.id
            WHERE p.term_id = ?
            """,
            (term_id,),
        )

        # Calculate BM25
        for posting in postings:
            document_id = posting["doc_id"]
            document_urls[document_id] = posting["url"]
            term_frequency = posting["tf"]
            document_length = posting["length"]
            length_factor = 1 - B + B * document_length / average_document_length
            denominator = term_frequency + K1 * length_factor
            bm25_score = idf * term_frequency * (K1 + 1) / denominator

            if document_id not in scores:
                scores[document_id] = 0
            scores[document_id] += bm25_score

    # Sort
    ranked_documents = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    results = []
    for document_id, score in ranked_documents[:limit]:
        url = document_urls[document_id]
        results.append((url, score))

    return results


def save_results(query, results):

    # Remove previous results for same query
    cursor.execute("DELETE FROM search_results WHERE query = ?", (query,))

    # Store results
    for rank, (url, score) in enumerate(results, start=1):
        cursor.execute(
            """
            INSERT INTO search_results
            (query, rank, url, score)
            VALUES (?, ?, ?, ?)
            """,
            (query, rank, url, score),
        )
    conn.commit()


if len(sys.argv) < 2:
    print("Please provide a search query")
    exit()

query = " ".join(sys.argv[1:])

results = search(query, 10)

for url, score in results:
    print(url, score)


for url, score in results:
    print(url, score)
save_results(query, results)
