"""Load an MCP server's main.py under a unique module name.

Every server's entrypoint is called main.py, so a plain `import main` makes the
first one imported win for the whole test session.
"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "mcp_servers"


def load_server(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_main", _ROOT / name / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
