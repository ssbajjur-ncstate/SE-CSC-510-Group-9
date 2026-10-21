# Installing TestBudget

Requires Python 3.10 or newer.

```bash
git clone https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9.git
cd SE-CSC-510-Group-9
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q              # all tests should pass
```

## First run

```bash
testbudget init
testbudget ingest fixtures/sample_junit.xml --changed-file src/checkout.py
testbudget plan --changed src/checkout.py --budget 10 --links fixtures/test_links.json
```

`plan` prints the ranked tests, which ones fit the budget, and which are skipped.

## Checks

```bash
ruff check .
mypy testbudget
```

## Troubleshooting

- `testbudget: command not found`: the virtual environment is not active.
- On Windows PowerShell, if activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.
