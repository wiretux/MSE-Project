from collections import Counter
from uuid import UUID

from utils import bert_reranker, storage
from utils.text_preprocessor import is_mostly_english, preprocess_text


def is_relevant(text: str, tokens: list[str]) -> bool:
    return is_mostly_english(text) and (
        "tuebingen" in tokens
        or {"university", "eberhard", "karls"}.issubset(set(tokens))
    )


def index(doc_id: UUID, document: dict) -> bool:
    # TODO Use the title when it gets implemented
    # full_doc_content = f"{document['titel']}. {document['content']}"
    full_doc_content = document["content"]
    doc_embedding = bert_reranker.get_bert_embedding(full_doc_content)

    tokens = preprocess_text(document["content"])

    tfs = list(Counter(tokens).items())

    if len(tfs) < 1 or not is_relevant(full_doc_content, tokens):
        return False

    with storage.access() as store:
        store.add_posting(doc_id, tfs)
        store.add_embedding(doc_id, doc_embedding)
        store.update_length(doc_id, len(tokens))
    return True
