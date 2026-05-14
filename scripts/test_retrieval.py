from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.lib import retriever


def test_retrieval(query: str):
    print(f"\n--- Retrieval trace for: {query!r} ---")
    trace = retriever.retrieve_with_trace(query)
    print(f"Rewritten: {trace['query']['rewritten']}")
    print(f"Router: {trace['router']}")
    print(f"Context blocks: {len(trace['context_blocks'])}")
    for block in trace["context_blocks"]:
        print(f"[{block['id']}] {block['collection']} | {block['source']}")
        print((block["text"] or "")[:240].replace("\n", " "))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_retrieval(" ".join(sys.argv[1:]))
    else:
        test_retrieval("login test cases for safari")
