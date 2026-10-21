# Release and Archiving Guide

## Preparing a release
1. Ensure the intended changes are merged into `main`.
2. Run the test suite and lint checks.
3. Review the changelog and update version information in `pyproject.toml`.
4. Create a version tag using the project's agreed version, such as `v0.1.0`.
5. Publish a GitHub Release with notes describing the changes.

## Archiving with Zenodo
1. Enable the repository integration in Zenodo using an authorized maintainer account.
2. Verify that the repository is connected and that new GitHub Releases trigger archiving.
3. Check that the archived record and DOI are available after the first release.

## Notes
Release versions and publication should be agreed upon by project maintainers. Do not publish a release or claim a DOI exists until the process has been verified.
