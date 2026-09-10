import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

loader = unittest.TestLoader()
suite = loader.discover(str(TESTS), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)

raise SystemExit(0 if result.wasSuccessful() else 1)
