# Installation

## Requirements
- Python 3.10 or newer
- Git

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project and development dependencies with `python -m pip install -e ".[dev]"`.

Run tests with python -m pytest -q and lint with python -m ruff check ..
