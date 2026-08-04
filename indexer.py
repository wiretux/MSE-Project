from collections import Counter
from uuid import UUID

from utils import storage
from utils.hash import sim_hash
from utils.text_preprocessor import is_mostly_english, preprocess_text

from rich.progress import Progress


def is_relevant(text: str, tokens: list[str]) -> bool:
    return is_mostly_english(text) and (
        "tuebingen" in tokens
        or {"university", "eberhard", "karls"}.issubset(set(tokens))
    )

def index(doc_id: UUID, document: dict[str, str | list(str)]) -> bool:
    full_doc_content = document["content"]
    if desc := document["desc"]:
        full_doc_content = f"{desc}. {full_doc_content}"
    if title := document["title"]:
        full_doc_content = f"{title}. {full_doc_content}"

    tokens = preprocess_text(document["content"])
    tfs = list(Counter(tokens).items())

    if len(tfs) < 1 or not is_relevant(full_doc_content, tokens):
        return False

    with storage.access() as store:
        content_id, unique = store.store_content(
            document["content"], sim_hash(tokens).to_bytes(8, "big")
        )

        if unique:
            store.add_posting(doc_id, tfs)

        store.update_document(doc_id, title, desc, content_id, len(tokens))
    return unique

def precalc_embeddings(progress: Progress, task_id: int):
    # Lazy import bert_reranker
    from utils import bert_reranker

    with storage.access() as store:
        while queue := store.poll_content():
            for id, title, desc, content in queue:
                if desc:
                    content = f"{desc}. {content}"
                if title:
                    content = f"{title}. {content}"

                embedding = bert_reranker.get_bert_embedding(content)
                store.add_embedding(id, embedding)
                progress.advance(task_id, 1)

