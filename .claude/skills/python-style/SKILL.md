# Python Code Generation — Style Rules

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
with the project-specific preferences below.

## Types over dicts

Prefer `NamedTuple` or `@dataclass` over plain dicts for structured data.
Use dicts only for genuinely dynamic key-value mappings (e.g. JSON payloads
you're passing through without inspecting).

```python
# Yes
from typing import NamedTuple

class Chunk(NamedTuple):
    id: str
    arabic: str
    english: str

# Yes
from dataclasses import dataclass

@dataclass
class Chunk:
    id: str
    arabic: str
    english: str

# No
chunk = {"id": "abc", "arabic": "...", "english": "..."}
```

Choose `NamedTuple` when the object is immutable and read-only.
Choose `@dataclass` when you need mutability or custom methods.

## Naming

- Modules/packages: `lower_with_under`
- Classes: `CapWords`
- Functions/methods: `lower_with_under()`
- Constants: `CAPS_WITH_UNDER`
- Internal/private: prefix with single `_`
- Never use double underscore `__` for name mangling
- Be descriptive — avoid abbreviations except well-known ones (`id`, `url`, `db`)

## Imports

- `import x` for packages/modules; `from x import y` for specific symbols
- Never use relative imports
- Group in order: stdlib, third-party, local — sorted lexicographically within groups
- Separate groups with a blank line

## Type annotations

- Annotate all public function signatures
- Use `X | None` not `Optional[X]`
- Use built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, ...]`
- Use `collections.abc` for abstract types: `Sequence`, `Mapping`, `Iterable`
- Don't annotate `self`, `cls`, or `__init__` return
- Default values with annotations: `arg: str = "default"`

## Docstrings

Google-style docstrings with `"""triple double quotes"""`.

```python
def load_chunks(path: Path) -> list[Chunk]:
    """Load chunks from a CSV file.

    Args:
        path: Path to the chunks CSV file.

    Returns:
        List of Chunk objects, one per CSV row.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
```

- First line: imperative summary ending with a period, under 80 chars.
- `Args:`, `Returns:`, `Raises:` sections with hanging indent.
- Omit docstring on trivially obvious private helpers.

## Functions

- Keep functions under ~40 lines. Break up longer ones.
- Never use mutable default arguments. Use `None` then initialise inside.
- Use `operator` module over trivial lambdas.
- Lambda only for one-liners under ~60 chars.

## Error handling

- Use built-in exceptions: `ValueError`, `TypeError`, `FileNotFoundError`, etc.
- Never bare `except:`. Never catch generic `Exception` unless re-raising.
- Minimise code in `try` blocks.
- Use `with` statements for files, sockets, and any resource that needs cleanup.

## Strings

- Use f-strings for formatting.
- Consistent quote style within a file (prefer `"double quotes"`).
- For logging: use `%`-style placeholders, not f-strings.

## Line length

80 characters max. Exceptions: long imports, URLs.

## Comprehensions

- Use for simple cases only.
- No chained `for` clauses — use a regular loop instead.

## Main guard

Every script must have:

```python
if __name__ == "__main__":
    main()
```

No top-level execution besides imports and definitions.

## Project-specific

- Always use the project venv: `.venv/bin/python`, `.venv/bin/pip`.
- Type-check with pyright (strict mode).
- All code must pass `pyright` with zero errors before committing.
