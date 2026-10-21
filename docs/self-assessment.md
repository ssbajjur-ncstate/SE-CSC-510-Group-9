# TestBudget repo rubric self-assessment

Self-assessed repo rubric for TestBudget (CSC 510, Group 9), repo [SE-CSC-510-Group-9](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9). Scores reflect what was merged on main when this was written. Each row links to its evidence.

## Teamwork, visible in GitHub

| Item | Evidence | Score 0-3 |
| --- | --- | --- |
| Many commits | [Contributors graph](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/graphs/contributors) | 3 |
| Commits come from different people | [Contributors graph](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/graphs/contributors) | 3 |
| Workload is spread over the whole team | [Contributors graph](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/graphs/contributors) | 3 |
| Team members work across many parts of the code | [Merged pull requests](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/pulls?q=is%3Apr+is%3Amerged) | 2 |
| Short release cycles: small commits, merged promptly | [Merged pull requests](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/pulls?q=is%3Apr+is%3Amerged) | 2 |
| Whole team uses the same tools | [pyproject.toml](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/pyproject.toml), [pre-commit config](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.pre-commit-config.yaml), [workflows](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/.github/workflows) | 3 |
| Whole team can run the system | Live demo | 3 |

## Issues and discussion

| Item | Evidence | Score 0-3 |
| --- | --- | --- |
| Issue reports: there are many | [All issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=is%3Aissue) | 3 |
| Issues are being closed | [Closed issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=is%3Aissue+is%3Aclosed) | 3 |
| Issues are discussed before they are closed | [Closed issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=is%3Aissue+is%3Aclosed) | 2 |
| A large share of issues relate to failing cases | [test-failure label: 2 of 68 issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=label%3Atype%3Atest-failure) | 1 |
| Chat channel exists and is active | Discord channel (add link or screenshots) | 2 |

## Tests

| Item | Evidence | Score 0-3 |
| --- | --- | --- |
| Tests exist, expected and failure cases | [tests folder](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/tests), 374 tests passing at the last local run | 3 |
| Tests are a serious share of the code base | [tests folder](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/tests), well over 30 percent of the Python lines | 3 |
| Tests run automatically on every commit | [CI workflow](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/ci.yml), runs on pull requests and pushes to main | 2 |
| Coverage is measured; the badge shows the number | [CI workflow](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/ci.yml), 91% measured with pytest-cov, no badge yet | 1 |

## Docs

| Item | Evidence | Score 0-3 |
| --- | --- | --- |
| Docs are generated, and the format is not ugly | [mkdocs.yml](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/mkdocs.yml), [docs folder](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/docs) | 2 |
| The WHAT: each class and function described | [API reference](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/api.md) | 2 |
| The HOW: mini-tutorials with worked examples | [links tutorial](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/links.md), [pytest adapter](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/pytest-adapter.md), [Playwright adapter](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/playwright-adapter.md) | 2 |
| The WHY: the docs tell a story | [docs index](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/index.md) | 2 |
| Teaser video at the top of the README | none yet | 3 |
| Feature walk-through video linked in the README | none yet | 3 |

## Standard files and bling

| Item | Evidence | Score 0-3 |
| --- | --- | --- |
| README with all badges, all working when clicked | [README](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/README.md), four workflow badges, no coverage or DOI badge yet | 2 |
| .gitignore | [.gitignore](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.gitignore) | 2 |
| INSTALL.md | [INSTALL.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/INSTALL.md) | 2 |
| LICENSE | [LICENSE](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/LICENSE), MIT | 3 |
| CODE-OF-CONDUCT.md | [CODE-OF-CONDUCT.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CODE-OF-CONDUCT.md) | 3 |
| CONTRIBUTING.md | [CONTRIBUTING.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CONTRIBUTING.md) | 3 |
| Style checker, formatter, syntax checker | [pyproject.toml](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/pyproject.toml), [lint](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/lint.yml), [format](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/format.yml), [types](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/types.yml) | 2 |
| DOI badge from Zenodo | none yet | 2 |
| THIRD_PARTY_LIBRARIES.md | [THIRD_PARTY_LIBRARIES.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/THIRD_PARTY_LIBRARIES.md) | 3 |
| AI use is visible and disclosed | [AI disclosure](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/ai-disclosure.md) | 2 |

## Sum

77 out of 96
