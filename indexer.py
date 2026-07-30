from collections import Counter

from utils.text_preprocessser import preprocess_text
import utils.storage as storage
import utils.bert_reranker as bert_reranker

def index(doc_id, document) -> bool:
    # TODO Use the title when it gets implemented
    #full_doc_content = f"{document['titel']}. {document['content']}"
    full_doc_content = document['content']
    doc_embedding = bert_reranker.get_bert_embedding(full_doc_content)

    tokens = preprocess_text(document['content'])

    tfs = list(Counter(tokens).items())

    if len(tfs) < 1:
        return False

    print(tokens)

    with storage.access() as store:
        store.add_posting(doc_id, tfs)
        store.add_embedding(doc_id, doc_embedding)
        store.update_length(doc_id, len(tokens))
    return True
