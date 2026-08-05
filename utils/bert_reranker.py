from uuid import UUID

import torch
from transformers import AutoModel, AutoTokenizer, logging

# Hide debugging info
logging.set_verbosity_error()

# Use CUDA/ROCm/MPS
device_str = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
device = torch.device(device_str)

print(f"[BERT] Using device: {device}")

# Load the bert model
tokenizer = AutoTokenizer.from_pretrained("bert-large-uncased")
model = AutoModel.from_pretrained("bert-large-uncased")
model.to(device)
model.eval()


def __get_mean_polled_embedding(bert_output: torch.BaseModelOutput, attention_mask: torch.Tensor) -> list[float]:
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


def get_bert_embedding(text: str) -> list[float]:
    inputs = tokenizer(text, truncation=True, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model(**inputs)

    return __get_mean_polled_embedding(output, inputs["attention_mask"])


def bert_reranker(query_text: str, doc_embeddings_dict: dict[UUID, list[float]]) -> list[tuple[UUID, float]]:
    if not query_text or not doc_embeddings_dict:
        return []

    # Get query_embedding and doc embeddings
    query_embedding = torch.tensor([get_bert_embedding(query_text)])
    doc_embeddings = torch.tensor(list(doc_embeddings_dict.values()))

    # Calculate the cosine similarity
    cosine_scores = torch.nn.functional.cosine_similarity(
        query_embedding, doc_embeddings, dim=1
    )

    # Attach the scores to the docs
    ranked_results = [
        (doc_id, score.item())
        for score, doc_id in zip(cosine_scores, doc_embeddings_dict.keys())
    ]

    # Sort the docs descending by score
    ranked_results.sort(key=lambda x: x[1], reverse=True)

    return [(doc_id, score) for doc_id, score in ranked_results]
