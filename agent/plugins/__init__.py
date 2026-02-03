"""Plugin loader for agent commands."""
from pathlib import Path
import importlib
import logging

logger = logging.getLogger(__name__)


def discover_plugins(path: Path) -> list[str]:
    plugins = []
    for f in path.glob("*.py"):
        if f.name.startswith("_"):
            continue
        plugins.append(f.stem)
    return plugins


def load_plugin(module_name: str):
    try:
        mod = importlib.import_module(module_name)
        return mod
    except Exception as e:
        logger.exception(f"Failed to load plugin {module_name}: {e}")
        return None
