import nltk
from nltk.corpus import stopwords, words
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import TweetTokenizer

# Download/update the requiered files on initialization if needed
nltk.download("stopwords")
nltk.download("wordnet")
nltk.download("words")

_stop_words = set(stopwords.words("english"))

_german_umlaute_mapping = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)

_english_vocab = {w.lower() for w in words.words("en")}

tokenizer = TweetTokenizer(preserve_case=False)

lemmatizer = WordNetLemmatizer()


# Replaces german umlaute in a text
def convert_german_umlaute(text: str) -> str:
    return text.translate(_german_umlaute_mapping)

# Splits the text into tokens and lowers it
def tokenize(text: str) -> list[str]:
    return tokenizer.tokenize(text)


# Check if a text is mostly english
def is_mostly_english(text: str, threshold: float=0.5) -> bool:
    tokens = tokenize(text)

    # Only keep alphabetic tokens (e.g. remove numbers, etc.)
    tokens = [
        lemmatizer.lemmatize(convert_german_umlaute(t)) for t in tokens if t.isalpha()
    ]
    if not tokens:
        return False

    ratio = sum(1 for t in tokens if t in _english_vocab) / len(tokens)
    return ratio >= threshold


# Pre-process text and split it into tokens
def preprocess_text(text: str) -> list[str]:
    # Splits the text into tokens and lowers it
    tokens = tokenize(text)

    # Remove all punctuation only tokens
    tokens = filter(lambda token: any(char.isalnum() for char in token), tokens)

    # Replace the german umlaute
    tokens = map(convert_german_umlaute, tokens)

    # Stop word removal
    tokens = filter(lambda token: token not in _stop_words, tokens)

    # Lemmatization
    tokens = map(lemmatizer.lemmatize, tokens)

    return list(tokens)
