import string
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import TweetTokenizer
from nltk.stem import WordNetLemmatizer

# Download/update the requiered files on initialization if needed
nltk.download('stopwords')
nltk.download('wordnet')

_stop_words = set(stopwords.words('english'))

_german_umlaute_mapping = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss"
})

tokenizer = TweetTokenizer(preserve_case=False)

lemmatizer = WordNetLemmatizer()

# Replaces german umlaute in a text
def convert_german_umlaute(text):
    return text.translate(_german_umlaute_mapping)

# Pre-process text and split it into tokens
def preprocess_text(text):
    # Splits the text into tokens and lowers it
    tokens = tokenizer.tokenize(text)

    # Remove all punctuation only tokens
    tokens = filter(lambda token: any(char.isalnum() for char in token), tokens)

    # Replace the german umlaute
    tokens = map(convert_german_umlaute, tokens)

    # Stop word removal
    tokens = filter(lambda token: token not in _stop_words, tokens)

    # Lemmatization
    tokens = map(lemmatizer.lemmatize, tokens)

    return list(tokens)
