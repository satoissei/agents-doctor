# Maintainer playbook

This document records operating targets for a volunteer-maintained project. They are
transparent expectations, not guaranteed response times.

## Weekly

- Triage new issues and pull requests for reproduction quality, scope, and privacy.
- Review Dependabot updates and run the full quality gate before merging them.
- Check unresolved security advisories and GitHub Actions failures.

## For every change

- Keep the change narrow and preserve stable rule IDs and output schemas.
- Require focused tests for both a finding and a non-finding where a rule changes.
- Run `pytest`, Ruff, mypy, the self-check, package build, and dependency audit.
- Review documentation, changelog, compatibility impact, and privacy impact.

## Release cadence

Release when a user-visible fix, compatibility update, or coherent set of improvements
is ready—not on a calendar for its own sake. Follow [releasing.md](releasing.md), use
semantic versioning, and publish concise release notes.

## Security and privacy

Aim to acknowledge private vulnerability reports within seven calendar days. Keep
reporter identity, reproduction data, and remediation discussion private until a
coordinated disclosure is agreed. Treat any accidental inclusion of private paths or
secrets as a security incident: restrict exposure, rotate affected credentials where
applicable, and publish only a sanitized explanation.

## Health signals

Track reproducible mismatch reports, issue response time, release notes, CI health,
and verified adoption evidence. Never inflate stars, downloads, user counts, or
security claims in documentation or funding applications.

Record adoption only under [adoption.md](adoption.md): keep the source and observation
date, exclude identifiable maintainer verification traffic, and obtain explicit
consent before naming an adopter. Failed evaluations are product feedback, not metrics
to hide.
