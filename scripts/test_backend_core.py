from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.lib import qdrant_store, settings


def test_core():
    client = qdrant_store.get_client()
    print("--- Qdrant collections ---")
    counts = qdrant_store.all_counts(client)
    for collection, count in counts.items():
        print(f"{collection:20} {count}")

    print("\n--- Search API smoke ---")
    for collection in settings.COLLECTIONS:
        try:
            hits = qdrant_store.dense_search(client, collection, [0.0] * 1024, limit=1)
            print(f"{collection:20} dense_search ok ({len(hits)} hit)")
        except Exception as exc:
            print(f"{collection:20} dense_search failed: {exc}")


if __name__ == "__main__":
    test_core()
