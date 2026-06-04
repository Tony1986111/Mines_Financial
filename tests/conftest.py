from pathlib import Path
import sys


# Pytest can execute test modules with a working import path that does not
# include the repository root, especially in non-packaged projects
# (`[tool.uv] package = false`). The application code in this repository uses
# root-level packages such as `nodes`, `tools`, and `utils`, so tests need the
# project root on `sys.path`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
