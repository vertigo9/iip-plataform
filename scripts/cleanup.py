#!/usr/bin/env python3
"""Cleanup script for IIP Platform."""

import shutil
from pathlib import Path


def cleanup():
    root = Path(".")
    patterns = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "htmlcov",
        "dist",
        "build",
        "*.egg-info",
    ]
    
    removed = 0
    for pattern in patterns:
        for item in root.rglob(pattern):
            try:
                if item.is_file():
                    item.unlink()
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    removed += 1
            except Exception:
                pass
    
    print(f"Cleaned {removed} items")

if __name__ == "__main__":
    cleanup()
