# MSE-Project
![Deadline](https://img.shields.io/badge/Deadline-5.%20Aug%202026,%2023:55-brightgreen?style=for-the-badge&logo=calendar)
# About
This is a small search engine designed to search topics related to Tübingen.
It was created as part of an assignment for the course *Modern Search Engines* in 2026.
# Prerequisites & Installation
We recommend using [uv](https://github.com/astral-sh/uv). A modern, fast Python package manager.

Set up your virtual environment and install dependencies:
```bash
uv venv --python 3.14
source .venv/bin/activate
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements.txt
```
### Note for Windows users:
 Activate the environment using ``.venv\Scripts\activate``
# Crawler
Before searching, populate the dataset by running the crawler:
```bash
python crawler.py [-h] [--skip-crawling] [--skip-embedding] [--skip-ai-detection] [--ignore-ssl] [-c CRAWLERS] [-i INDEXERS] [-w WAIT] [-t TIMEOUT] [-d DEPTH] [-a ATTEMPTS]
```
Use `python crawler.py -h` for detailed information about argument usage.

# UI
Launch the Terminal User Interface (TUI) to search interactively:
```bash
python ui.py
```

# Batch queries
Run multiple queries simultaneously to benchmark performance.

Format your query file (one query per line):
```
index<tab>url
```
Example:
```
1   tübingen attractions
2   food and drinks
```
Then run the batch processor:
```bash
python batch.py [-o path/to/the/output-file] path/to/the/query-file 
```

The output will look similar to this:
```
1 1 https://www.tuebingen.de/en/3521.html 0.725
1 2 https://www.komoot.com/guide/355570/castles-in-tuebingen-district 0.671
1 3 https://www.unimuseum.uni-tuebingen.de/en/museum-at-hohentuebingen-castle 0.529
...
1 100 https://www.tuebingen.de/en/3536.html 0.178
2 1 https://www.tuebingen.de/en/3773.html 0.956
2 2 https://www.tuebingen.de/en/4456.html 0.797
```
