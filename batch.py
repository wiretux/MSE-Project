import argparse
from pathlib import Path

from query import retrieve


def read_queries(file_path):
    lines = file_path.read_text().splitlines()
    return [
        (int(parts[0]), parts[1])
        for line in lines
        if line.strip()
        for parts in [line.split("\t")]
        if len(parts) == 2 and parts[0].isdigit()
    ]


def batch(results, output_path):
    with open(output_path, "w") as f:
        for query_idx, query_results in results:
            for result_idx, (result, score) in enumerate(query_results):
                print(
                    query_idx,
                    result_idx + 1,
                    result["url"],
                    format(score, ".3f"),
                    sep="\t",
                    file=f,
                )


def evaluate(query_file_path, output_file_path):
    # Read in the queries as a list
    queries = read_queries(query_file_path)
    # Get the results
    results = [(idx, retrieve(query)) for idx, query in queries]
    # Print in the file
    batch(results, output_file_path)


# Get query file path
arg_parser = argparse.ArgumentParser(
    description="Process query files and write output."
)

arg_parser.add_argument("query_file_path", type=Path, help="Path to the query file")

arg_parser.add_argument(
    "-o",
    "--output",
    type=Path,
    default=Path("output_results.txt"),
    help="Path to the output file (default: output_results.txt)",
)

args = arg_parser.parse_args()
query_file_path: Path = args.query_file_path
output_file_path: Path = args.output

if not query_file_path.exists():
    raise FileNotFoundError(f'Error: The query file "{query_file_path}" does not exist')

if output_file_path.exists():
    user_choice = (
        input(
            f'Output file "{output_file_path}" already exists. Overwrite/delete it? [y/n]: '
        )
        .strip()
        .lower()
    )
    if user_choice in ["y", "yes"]:
        output_file_path.unlink()
        evaluate(query_file_path, output_file_path)
    else:
        print("Operation cancelled by user.")
else:
    evaluate(query_file_path, output_file_path)
