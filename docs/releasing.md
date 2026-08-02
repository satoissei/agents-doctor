# Releasing agents-doctor

## Before creating a tag

1. Start from a clean, reviewed `main` branch.
2. Update `CHANGELOG.md` and confirm the version in `pyproject.toml` and
   `src/agents_doctor/__init__.py` match.
3. Run the local quality gate:

   ```console
   pytest --cov=agents_doctor
   ruff check .
   ruff format --check .
   mypy
   agents-doctor check --format github
   python -m build
   twine check dist/*
   pip-audit --requirement requirements/runtime.txt
   ```

4. Confirm the privacy and compatibility documentation still describes the release.
5. Create and push the matching annotated tag, for example `v0.2.3`.

## What automation verifies

The release workflow repeats tests, linting, formatting, type checking, package
building, and `twine check`. It rejects a tag that does not equal `v` plus the
package version, uploads the distribution artifacts, and creates a GitHub Release.
PyPI publishing is intentionally opt-in and requires the repository variable
`PUBLISH_TO_PYPI=true` plus a configured trusted publisher.

## After release

Verify that the GitHub Release contains both the wheel and source archive, install
the wheel in a clean environment, and check the release notes and action tag. If a
release must be superseded, publish a corrective release with clear notes; do not
rewrite an existing public tag.
