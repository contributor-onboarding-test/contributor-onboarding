# AGENTS.md

## Project Overview

`contributor-onboarding` automates the review of OpenWISP contributor applications submitted through a Google Form.

- `onboarding/` contains the checks (`checks.py`), the GitHub client (`github.py`), the Sheet access (`sheet.py`), and the workflow entry point (`validate.py`).
- `onboarding/settings.py` holds the Form column names, required repositories, and other rules.
- `.github/workflows/validate.yml` runs the daily validation.
- Tests are in `tests/`.

## Source of Truth

- Use `.github/workflows/ci.yml` for CI commands and supported Python versions.
- Use `README.rst` for the workflow's behavior, setup, secrets, and variables.
- Use the GitHub issue and pull request templates when creating GitHub content.

If instructions conflict, CI configuration wins first, then repository documentation, and this file is supplemental.

## Contributing Guidelines

- Before editing, inspect the affected code, its tests, documentation, and configuration. Follow existing patterns and do not invent behavior or requirements.
- Keep each contribution focused. Do not include unrelated refactors, formatting churn, or generated files unless explicitly required.
- Add or update focused tests for behavior changes. Use test-driven development for clear bug fixes and narrowly scoped changes.
- Run `./run-qa-checks` and `./runtests` after changes.
- When requirements, intended behavior, or an unexpected failure are unclear, stop and seek clarification instead of making speculative changes.
- Create issue branches from `master` using `issues/<issue-number>-<short-title>`.
- Use descriptive, past-tense commit messages. Issue commits must use an allowed OpenWISP prefix and end with `#<issue-number>`.
- Send new commits in response to review feedback instead of amending existing commits.

## Privacy and Security Rules

- Applications contain personal data. Never log, print, commit, or upload names, emails, usernames, links, or check results per applicant; logs may only show counts.
- Never store applicant data in the repository, workflow artifacts, or caches. It stays in the Google Sheet.
- Keep credentials in repository secrets. Never commit private keys or service account files.
- Workflows that use secrets must run only on `schedule` and `workflow_dispatch`, never on `pull_request_target`.
- Pin third-party actions to full commit SHAs and keep `permissions` minimal.
