"""Absolute, isolated entrypoint; never import Python modules from a document folder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convertix.worker import main

raise SystemExit(main())
