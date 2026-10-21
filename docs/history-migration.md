# Migrating prototype history

TestBudget's first prototype stored historical test executions in a local
SQLite database.

The current format uses committed JSONL history:

- `history/runs.jsonl`
- `history/results.jsonl`

The migration utility converts prototype databases into the current format.

## Run the migration

From the repository root:

```bash
python -m testbudget.migrate \
  --db testbudget.db \
  --history-dir history