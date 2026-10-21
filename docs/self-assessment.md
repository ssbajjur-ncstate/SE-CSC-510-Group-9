# Self-assessment

Evidence for each rubric item, gathered with `gh` and `git` on 2026-10-21. Rows marked **TODO** have no evidence yet.

| Rubric item | Status | Evidence |
|---|---|---|
| Commits by every member | Done | `git shortlog -sn --no-merges`: Vedantt Koul 67, Namrata Joshi 54, Sakshi Shelar 28, ssbajjur-ncstate 25 (two spellings), saanvi 3. [Commit history](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/commits/main) |
| Issues opened by every member | Done | ved-ntt 14, nmjoshi2-ncstate 24, ssbajjur-ncstate 16, sakshishelarr 10. [All issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=is%3Aissue) |
| Issues closed | Done | 56 closed, 8 open. [Closed issues](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=is%3Aissue+is%3Aclosed) |
| Test-failure issues | Done | [#70](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues/70) (ruff I001 on main), [#82](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues/82) (pytest adapter hook). [Label](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/issues?q=label%3Atype%3Atest-failure) |
| Pull requests with review | Done | 41 merged PRs. [Merged PRs](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/pulls?q=is%3Apr+is%3Amerged) |
| Test suite | Done | 401 tests (`python -m pytest --collect-only`), one module per package module in [tests/](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/tests) |
| CI on every PR and main | Done | [ci.yml](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.github/workflows/ci.yml): pytest with coverage, ruff check, ruff format, mypy. [Green run on main](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/runs/39657653815) |
| Coverage report | TODO | Codecov upload is in ci.yml; needs the `CODECOV_TOKEN` secret before the badge shows a number |
| Documentation | Partial | [mkdocs.yml](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/mkdocs.yml), [docs/](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/tree/main/docs), [Docs workflow](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/actions/workflows/docs.yml). **TODO:** GitHub Pages is not enabled, so there is no public docs URL yet |
| README | Done | [README.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/README.md): what, why, how, quickstart |
| LICENSE | Done | [LICENSE](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/LICENSE) (MIT) |
| INSTALL | Done | [INSTALL.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/INSTALL.md) |
| CODE-OF-CONDUCT | Done | [CODE-OF-CONDUCT.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CODE-OF-CONDUCT.md) |
| CONTRIBUTING | Done | [CONTRIBUTING.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CONTRIBUTING.md) |
| Third-party libraries | Done | [THIRD_PARTY_LIBRARIES.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/THIRD_PARTY_LIBRARIES.md) |
| AI disclosure | Done | [docs/ai-disclosure.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/ai-disclosure.md) |
| Changelog | Done | [CHANGELOG.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CHANGELOG.md) |
| Badges | Done | CI, docs, Codecov, ruff, mypy, license in [README.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/README.md) |
| Citation | Done | [CITATION.cff](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/CITATION.cff), [.zenodo.json](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/.zenodo.json) |
| DOI | TODO | No Zenodo release yet; enable the Zenodo GitHub integration and publish a release |
| PyPI release | TODO | No PyPI link is recorded in the repository yet |
| M0 decision | Done | [docs/m0-decision.md](https://github.com/ssbajjur-ncstate/SE-CSC-510-Group-9/blob/main/docs/m0-decision.md) |
