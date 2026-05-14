import sys
from pathlib import Path

# Ensure root is in path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from backend.ingest.ingest_all import main

if __name__ == "__main__":
    main()
