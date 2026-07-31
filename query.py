from utils import storage
from utils.bert_reranker import bert_reranker
from utils.bm25 import get_bm25


def retrieve(query: str) -> [(dict, float)]:
    first_results = get_bm25(query)
    with storage.access() as store:
        embeddings = store.get_embedding([doc_id for doc_id, _ in first_results])
        reranked_results = bert_reranker(query, embeddings)
        result_docs = store.get_documents([doc_id for doc_id, _ in reranked_results])

    combined_scores = dict(reranked_results)

    bm25_max = max(first_results, key=lambda x: x[1])[1]
    bm25_norm = 1 / (bm25_max if bm25_max and bm25_max > 0 else 1)

    for doc_id, score in first_results:
        combined_scores[doc_id] *= score * bm25_norm

    return sorted(
        [
            (result_docs[doc_id], combined_scores[doc_id])
            for doc_id, _ in reranked_results
        ],
        key=lambda x: x[1],
        reverse=True,
    )