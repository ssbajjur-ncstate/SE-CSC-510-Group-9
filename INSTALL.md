# Installation

## Requirements
- Python 3.10 or newer
- Git

## Setup

Clone the repository and enter its directory:

```bash
git clone https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9.git
cd SE-CSC-510-Group-9
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run tests and checks

```bash
python -m pytest -q
python -m ruff check .
python -m mypy
```

Run `testbudget --help` to see the available CLI options.
