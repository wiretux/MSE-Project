from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Use CUDA/ROCm/MPS
device_str = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
device = torch.device(device_str)

print(f"[AI-Detection] Using device: {device}")

# Load the model
model_name = "AICodexLab/answerdotai-ModernBERT-base-ai-detector"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
model.to(device)
model.eval()

def get_ai_probabitlity(test: str) -> float:
    inputs = tokenizer(text, truncation=True, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    return probabilities[0][1].item()