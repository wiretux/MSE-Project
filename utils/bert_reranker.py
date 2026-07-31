import torch
from transformers import AutoTokenizer, AutoModel, logging

# Hide debugging info
logging.set_verbosity_error()

# Load the bert model
tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
model = AutoModel.from_pretrained('bert-base-uncased')
model.eval()

def __get_mean_polled_embedding(bert_output, attention_mask):
    # Get the token vectors
    token_embedding = bert_output.last_hidden_state

    # Get attention_mask as floats
    attention_mask = attention_mask.unsqueeze(-1).float()

    # Count the feature values of the sentences
    sum_embeddings = torch.sum(token_embedding * attention_mask, dim=1)

    # Count the total sum of words in each sentence
    attention_mask_word_count = attention_mask.sum(dim=1)

    # Prevent the word count from ever beeing 0 to prevent a devision by 0
    attention_mask_word_count = torch.clamp(attention_mask_word_count, min=1.0)

    # Mean pooling
    mean_pooled = sum_embeddings / attention_mask_word_count

    return mean_pooled.squeeze(0).tolist()

def get_bert_embedding(text):

    inputs = tokenizer(
        text,
        truncation=True,
        return_tensors="pt"
    )

    with torch.no_grad():
        output = model(**inputs)

    return __get_mean_polled_embedding(output, inputs['attention_mask'])

def bert_reranker(query_text: str, doc_embeddings_dict: dict):

    if not query_text or not doc_embeddings_dict:
        return []

    # Get query_embedding and doc embeddings
    query_embedding = torch.tensor([get_bert_embedding(query_text)])
    doc_embeddings = torch.tensor(list(doc_embeddings_dict.values()))

    # Calculate the cosine similarity
    cosine_scores = torch.nn.functional.cosine_similarity(query_embedding, doc_embeddings, dim=1)

    # Attach the scores to the docs
    ranked_results = [
        (doc_id, score.item())
        for score, doc_id in zip(cosine_scores, doc_embeddings_dict.keys())
    ]

    # Sort the docs descending by score
    ranked_results.sort(key=lambda x: x[1], reverse=True)

    return [doc_id for doc_id, score in ranked_results]


# Example Documents
#example_docs = {
#        'id1': 'some words the doc1 contains',
#        'id2': 'some words the doc2 contains',
#        'id3': 'some words more the doc3 contains'
#    }

# The Indexer should tokenize every doc first and store it in the db
#example_embeddings_dict = {doc_id: get_bert_embedding(text) for doc_id, text in example_docs.items()}

# Example query and test
#example_query = "words contains"
#print(bert_reranker(example_query, example_embeddings_dict))
