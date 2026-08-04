from collections import Counter
from uuid import UUID

from utils import storage
from utils.hash import sim_hash
from utils.text_preprocessor import is_mostly_english, preprocess_text


def is_relevant(text: str) -> bool:
    return is_mostly_english(text) and "tuebingen" in text

def index(doc_id: UUID, document: dict[str, str | list(str)]) -> bool:
    full_doc_content = document["content"]
    if desc := document["desc"]:
        full_doc_content = f"{desc}. {full_doc_content}"
    if title := document["title"]:
        full_doc_content = f"{title}. {full_doc_content}"

    tokens = preprocess_text(document["content"])
    tfs = list(Counter(tokens).items())

    if len(tfs) < 1 and not is_relevant(document["content"]):
        return False

    with storage.access() as store:
        content_id, unique = store.store_content(
            document["content"], sim_hash(tokens).to_bytes(8, "big")
        )

        if unique:
            store.add_posting(doc_id, tfs)

        store.update_document(doc_id, title, desc, content_id, len(tokens))
    return unique
