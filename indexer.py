import string
from collections import Counter
from pathlib import Path

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import TweetTokenizer
from nltk.stem import WordNetLemmatizer

import utils.storage as storage
import utils.bert_reranker as bert_reranker

class Indexer():
    def __init__(self):

        # Download/update the requiered files on initialization if needed
        nltk.download('stopwords')
        nltk.download('wordnet')


        self._stop_words = set(stopwords.words('english'))

        self._german_umlaute_mapping = str.maketrans({
            "ä": "ae", "ö": "oe", "ü": "ue",
            "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
            "ß": "ss"
        })

        self.tokenizer = TweetTokenizer(preserve_case=False)

        self.lemmatizer = WordNetLemmatizer()

    # Replaces german umlaute in a text
    def convert_german_umlaute(self, text):
        return text.translate(self._german_umlaute_mapping)

    # Pre-process text and split it into tokens
    def preprocess_text(self, text):
        # Splits the text into tokens and lowers it
        tokens = self.tokenizer.tokenize(text)

        # Remove all punctuation only tokens
        tokens = filter(lambda token: any(char.isalnum() for char in token), tokens)

        # Replace the german umlaute
        tokens = map(self.convert_german_umlaute, tokens)

        # Stop word removal
        tokens = filter(lambda token: token not in self._stop_words, tokens)

        # Lemmatization
        tokens = map(self.lemmatizer.lemmatize, tokens)

        return list(tokens)

    def index(self, doc_id, document) -> bool:
        # TODO Use the title when it gets implemented
        #full_doc_content = f"{document['titel']}. {document['content']}"
        full_doc_content = document['content']
        doc_embedding = bert_reranker.get_bert_embedding(full_doc_content)

        tokens = self.preprocess_text(document['content'])

        tfs = list(Counter(tokens).items())

        if len(tfs) < 1:
            return False

        with storage.access() as store:
            store.add_posting(doc_id, tfs)
            store.add_embedding(doc_id, doc_embedding)
            store.update_length(doc_id, len(tokens))

        return True

indexer = Indexer()
