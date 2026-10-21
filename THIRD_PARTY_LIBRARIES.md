# Third-party libraries

TestBudget has one runtime dependency, PyYAML, which reads `testbudget.yml`
(pinned tests). Every other third-party library below is used for building the
package or for development (tests, linting, type checking).

Versions are the constraints declared in `pyproject.toml`.

## Runtime

| Library | Version | Purpose | Licence |
|---|---|---|---|
| [PyYAML](https://pypi.org/project/PyYAML/) | `>=6` | Reads `testbudget.yml` (pinned tests) | [MIT](https://pypi.org/project/PyYAML/) |

## Build

| Library | Version | Purpose | Licence |
|---|---|---|---|
| [setuptools](https://pypi.org/project/setuptools/) | `>=64` | Build backend for `pip install` | [MIT](https://pypi.org/project/setuptools/) |

## Development (`dev` extra)

Installed with `pip install -e ".[dev]"`.

| Library | Version | Purpose | Licence |
|---|---|---|---|
| [pytest](https://pypi.org/project/pytest/) | `>=8.0` | Test runner | [MIT](https://pypi.org/project/pytest/) |
| [pytest-cov](https://pypi.org/project/pytest-cov/) | `>=5.0` | Coverage reporting for pytest | [MIT](https://pypi.org/project/pytest-cov/) |
| [hypothesis](https://pypi.org/project/hypothesis/) | `>=6.100` | Property-based tests for the ranker and rules | [MPL-2.0](https://pypi.org/project/hypothesis/) |
| [ruff](https://pypi.org/project/ruff/) | `>=0.6` | Linter and import sorter | [MIT](https://pypi.org/project/ruff/) |
| [mypy](https://pypi.org/project/mypy/) | `>=1.10` | Static type checker | [MIT](https://pypi.org/project/mypy/) |
| [types-PyYAML](https://pypi.org/project/types-PyYAML/) | any | Type stubs so `mypy testbudget` can check code that imports `yaml` | [Apache-2.0](https://pypi.org/project/types-PyYAML/) |
| [pre-commit](https://pypi.org/project/pre-commit/) | `>=3.5` | Runs the ruff and pytest hooks in `.pre-commit-config.yaml` before each commit | [MIT](https://pypi.org/project/pre-commit/) |

Hypothesis is the only copyleft (file-level, MPL-2.0) licence in the list. It is
used only in the test suite and is not distributed with the package.

## Adding a dependency

Add a row to the right table in the same PR that adds the dependency to
`pyproject.toml`, and give the reason in the PR description. A new runtime
dependency needs its own `## Runtime` table.
