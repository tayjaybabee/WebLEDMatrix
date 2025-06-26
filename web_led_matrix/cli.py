"""Command-line interface for the Web LED Matrix app."""
from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    """Launch the Streamlit application."""
    package_dir = Path(__file__).resolve().parent
    app_path = package_dir / "__init__.py"
    return subprocess.call(["streamlit", "run", str(app_path)])


if __name__ == "__main__":
    raise SystemExit(main())
