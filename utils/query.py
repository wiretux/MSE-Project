import math

from utils import storage
from utils.bert_reranker import bert_reranker, get_bert_embedding
from utils.bm25 import get_bm25

from uuid import UUID


def ondemand_embedding_gen(missing_embeddings: set[UUID], embeddings: dict[UUID, list[float]]):
    """
    Calculate the missing embeddings ondemand.
    This can be super expensive and should be used with caution.
    Think about calculating the embeddings offline.
    """
    from rich.progress import Progress

    with storage.access() as store, Progress() as progress:
        task_id = progress.add_task("[OnDemand Embeddings]", total=len(missing_embeddings))

        for id, title, desc, content in store.poll_content_for(list(missing_embeddings)):
            if desc:
                content = f"{desc}. {content}"
            if title:
                content = f"{title}. {content}"
            embedding = get_bert_embedding(content)
            store.add_embedding(id, embedding)
            embeddings[id] = embedding
            progress.advance(task_id, 1)

def retrieve(query: str, limit: int = 100, skew: float = 0.3) -> list[tuple[dict, float]]:
    """
    Do the actual retrieval of documents using BM25, BERT and PageRank.
    """

    # Calculate BM25 with limit of 5 * {limit}
    first_results = get_bm25(query, 5 * limit)

    if not first_results:
        return []

    # Rerank pages with bert and limit to {limit}
    with storage.access() as store:
        embeddings = store.get_embedding([doc_id for doc_id, _ in first_results])

        missing_embeddings = { doc_id for doc_id, _ in first_results } - embeddings.keys()
        if missing_embeddings:
            ondemand_embedding_gen(missing_embeddings, embeddings)

        reranked_results = bert_reranker(query, embeddings)[:limit]
        result_docs = store.get_documents([doc_id for doc_id, _ in reranked_results])

    if not result_docs:
        return []

    # Calculate score as combination of PageRank and BERT
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
