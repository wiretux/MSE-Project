import math
from uuid import UUID

from utils import storage
from utils.text_preprocessor import preprocess_text


def get_idf(doc_count: int, N: int) -> float:
    return math.log((N - doc_count + 0.5) / (doc_count + 0.5) + 1)


def get_bm25(
    query: str, limit: int = 100, k1: float = 1.5, b: float = 0.75
) -> list[(UUID, float)]:
    # Preprocess the text to tokens
    query_tokens = preprocess_text(query)

    with storage.access() as store:
        # Get the bm25 relevant data from the db
        postings, term_meta, avg_length, total_docs = store.get_postings(
            query_tokens, max=200
        )

        # If there is no average length no ranking is possible
        if not avg_length:
            return []

        results = []

        # Loop over every relevant document
        for doc_id, doc_data in postings.items():
            # Extract the length and terms from the document
            doc_length = doc_data["length"]
            doc_terms = doc_data["terms"]

            # Pre calculate the length normalization
            length_norm = 1 - b + b * (doc_length / avg_length)

            score = 0
            # Loop over every term to calculate the bm25 score for the document
            for term_id, tf in doc_terms.items():
                idf = get_idf(term_meta.get(term_id, 0), total_docs)
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * length_norm
                score += idf * numerator / denominator
                print(term_meta)

            # Store the doc_id its score in the result list
            results.append((doc_id, score))

        # Sort the results
        ranked_docs = sorted(results, key=lambda doc: doc[1], reverse=True)

        # Return the sorted documents
        return [(doc_id, score) for doc_id, score in ranked_docs[:limit]]
