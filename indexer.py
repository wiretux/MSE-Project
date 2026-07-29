import string
from collections import Counter
from pathlib import Path

import utils.storage as storage
from utils.porter2_stemmer import porter2_stemmer

class Indexer():
    def __init__(self):
        # Stopword setup
        STOP_WORD_PATH = Path('./stopwords.txt')
        self._stop_words = self.__get_stop_words(STOP_WORD_PATH)

    # Replaces german umlaute in a text
    @staticmethod
    def __convert_german_umlaute(text):
        mapping = str.maketrans({
            "ä": "ae", "ö": "oe", "ü": "ue",
            "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
            "ß": "ss"
        })

        return text.translate(mapping)

    # Returns all the stop words as a list if the stopword list exists
    @staticmethod
    def __get_stop_words(path):
        if not path.is_file():
                print(path.name + ' is missing')
                return []

        with open(path, 'r', encoding='utf-8') as f:
            next(f, None) # This is needed for the header line containing the source
            return set([line.strip().lower() for line in f if line.strip()])

    # Pre-process text and split it into tokens
    def __get_tokenized_text(self, text):
        # Lower the text
        text = text.lower()

        # Replace the german umlaute
        text = self.__convert_german_umlaute(text)

        # Remove all non alpha numeric symbols including punctuations
        text = "".join(char if char.isalnum() else " " for char in text)

        # Splits the text into tokens
        tokens = text.split()

        # Stop word removal
        tokens = filter(lambda token: token not in self._stop_words, tokens)

        # Porter Stemming Algo
        # We use the snowball stemmer algo here for better results
        tokens = map(porter2_stemmer, tokens)

        return list(tokens)

    def index(self, doc_id, document) -> bool:
        tokens = self.__get_tokenized_text(document['content'])

        terms = set(tokens)
        tfs = list(Counter(tokens).items())

        if len(tfs) < 1:
            return False

        with storage.access() as store:
            store.add_posting(doc_id, tfs)
            store.update_length(doc_id, len(tokens))

        return True

indexer = Indexer()
