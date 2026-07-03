"""Script autonome pour GitHub Actions - exécute le traitement sans Flask."""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Import après config logging pour que app.py hérite du bon logger
sys.path.insert(0, str(Path(__file__).parent))
from app import process_cards  # noqa: E402

if __name__ == "__main__":
    results = process_cards()
    print(results)

    if results.get("errors"):
        sys.exit(1)
