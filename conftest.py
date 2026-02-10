"""Root conftest.py -- ensures `src` is importable from tests."""

import sys
from pathlib import Path

# Add the project root to sys.path so `from src.models import ...` works.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
