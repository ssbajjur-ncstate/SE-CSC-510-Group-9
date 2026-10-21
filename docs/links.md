# How to: link tests to source files

TestBudget decides what to run using *links*: which source files each test depends on. There are four sources: `import`, `route`, `cofail` and `pin`.

## Build import links for a Python project

```python
from pathlib import Path
from testbudget.links.imports import build_import_links
from testbudget.links.writer import write_links

links = build_import_links(Path("."))
write_links(links, "links.json")
```

Each test file is parsed with `ast`; imports that resolve to files inside the repository become links with `source: "import"`. A file that cannot be parsed is skipped with a warning instead of stopping the run.

## Add links from past failures

```python
from testbudget.links.cofail import build_cofail_links, read_jsonl
from testbudget.links.writer import merge_links, write_links

runs = read_jsonl("history/runs.jsonl")
results = read_jsonl("history/results.jsonl")
write_links(merge_links(links, build_cofail_links(runs, results)), "links.json")
```

Files changed on commits where a test failed become weighted links to that test, scaled so the strongest link has weight 1.0.

## Inspect the result

```bash
python -m testbudget.cli links --report --links links.json
```

```text
LINKS REPORT
--------------------------------
Tests: 4
  with links:    4
  without links: 0
Total links: 7
By source:
  import: 7
```

See the [API reference](api.md) for every function.
