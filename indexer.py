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

    # Remove punctuations of a text
    @staticmethod
    def __remove_punctuations(text):
        punctuations = string.punctuation
        return text.translate(str.maketrans("", "", string.punctuation))

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
        # Remove punctuations, lower the text and split it into tokens
        tokens = self.__remove_punctuations(text).lower().split()

        # Stop word removal
        tokens = filter(lambda token: token not in self._stop_words, tokens)

        # Porter Stemming Algo
        # We use the snowball stemmer algo here for better results
        tokens = map(porter2_stemmer, tokens)

        return list(tokens)

    def index(self, doc_id, doc_content):
        tokens = self.__get_tokenized_text(doc_content)

        terms = set(tokens)
        tfs = list(Counter(tokens).items())

        with storage.access() as store:
            store.add_posting(doc_id, tfs)
            store.update_document(doc_id, len(tokens))

indexer = Indexer()
indexer.index(1, 'the dog jumped ! over the lazy fox and dog')
