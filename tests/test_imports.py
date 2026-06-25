"""Guard: modules inside the ``scripts`` package import siblings relatively.

The package is relocatable, so its internal dependencies must use relative
imports (``from .model import X``). Absolute self-imports (``from scripts.model
import X``) are reserved for external consumers (``cli.py``, tests). Neither
ruff nor pyright can require relative imports, so this test enforces it.
"""

import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _absolute_self_imports(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, module) for every absolute ``scripts.*`` import in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and (node.module or "").startswith("scripts"):
                found.append((node.lineno, node.module or ""))
        elif isinstance(node, ast.Import):
            found.extend(
                (node.lineno, alias.name)
                for alias in node.names
                if alias.name == "scripts" or alias.name.startswith("scripts.")
            )
    return found


def test_scripts_use_relative_self_imports() -> None:
    """Every scripts/*.py imports siblings relatively, never ``from scripts...``.

    Guards the relocatable-package rule: an absolute self-import inside the
    package couples it to its top-level name. Reserve absolute ``scripts.x``
    imports for external consumers like cli.py. Fails if one is reintroduced.
    """
    offenders = {
        path.name: hits
        for path in sorted(SCRIPTS.glob("*.py"))
        if (hits := _absolute_self_imports(path))
    }
    assert not offenders, f"absolute self-imports inside scripts/: {offenders}"
