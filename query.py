import math

from utils import storage
from utils.bert_reranker import bert_reranker
from utils.bm25 import get_bm25

# Start off with 5 * limit
# Rerank pages with BERT to limit
# Sort pages based on BERT and pagerank


def retrieve(query: str, limit: int = 100, skew: float = 0.3) -> [(dict, float)]:
    first_results = get_bm25(query, 5 * limit)

    if not first_results:
        return []

    with storage.access() as store:
        embeddings = store.get_embedding([doc_id for doc_id, _ in first_results])
        reranked_results = bert_reranker(query, embeddings)[:limit]
        result_docs = store.get_documents([doc_id for doc_id, _ in reranked_results])

    combined_scores = dict(reranked_results)

    pr_norm = 1 / math.log(
        max(result_docs.values(), key=lambda x: x["rank"])["rank"] + 1
    )

    for doc_id, score in combined_scores.items():
        rank = math.log(result_docs[doc_id]["rank"] + 1)
        combined_scores[doc_id] = (1.0 - skew) * score + skew * rank * pr_norm

    return sorted(
        [
            (result_docs[doc_id], combined_scores[doc_id])
            for doc_id, _ in reranked_results
        ],
        key=lambda x: x[1],
        reverse=True,
    )
