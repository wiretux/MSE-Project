import os
from datasets import load_dataset
from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
from sentence_transformers.sentence_transformer import losses

# Load MS MARCO
ms_marco = load_dataset("sentence-transformers/msmarco-bm25", "triplet", streaming=True, split="train")
ms_marco = ms_marco.rename_columns({"query": "anchor"})
ms_marco = ms_marco.select_columns(["anchor", "positive", "negative"])

# Model and loss setup
model = SentenceTransformer("bert-base-uncased")
loss = losses.MultipleNegativesRankingLoss(model)

args = SentenceTransformerTrainingArguments(
    output_dir="./bert-dual-encoder-ms_marco-mse-search",
    per_device_train_batch_size=64,
    gradient_accumulation_steps=1,
    learning_rate=2e-5,
    max_steps=10000,
    fp16=True,
    logging_steps=100,
    warmup_ratio=0.1,
    gradient_checkpointing=True
)

# Stup trainer
trainer = SentenceTransformerTrainer(
    model=model,
    args=args,
    train_dataset=ms_marco,
    loss=loss,
)

trainer.train()
model.save("/data/output-bert-dual-encoder-ms_marco-mse-search")
print("Done. We got a trained model now :D")

# Do an hard exit because of streaming the download threads sometimes lock up
os._exit(0)
