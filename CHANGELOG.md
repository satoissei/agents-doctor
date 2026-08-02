# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.3] - 2026-08-03

### Security

- Prevent tracked filenames from being interpreted as `detect-secrets` options in
  pull-request CI and release checks.
- Render control characters visibly in human-readable reports so crafted POSIX
  filenames cannot forge log lines or manipulate terminals.
- Require privacy confirmation before users submit repository details through the
  false-positive and loader-divergence issue forms.

### Fixed

- Reject manually dispatched releases unless the selected Git reference is a tag.

## [0.2.2] - 2026-08-03

### Added

- Add a no-install trial command, public adoption-report form, and evidence policy
  for collecting real usage without telemetry or inflated metrics.
- Publish the package on PyPI and the composite action on GitHub Marketplace, and
  make the package-index install path the primary setup route.

## [0.2.1] - 2026-08-02

### Fixed

- Reuse instruction contents discovered by repository checks instead of rereading
  ancestor files for every working directory.
- Keep the real loader's unread-file state while avoiding false `AD001` reports for
  blank files whose contents are already known to the repository scan.
- Exclude size-only unread files from character-density calculations and mark their
  lost-character count as unknown in JSON output.

### Documentation

- Record a candid Codex for Open Source eligibility assessment and update the
  application kit to the current official form and program terms.

## [0.2.0] - 2026-08-02

### Fixed

- Stop reading instruction-file contents after the simulated loader's byte budget
  is exhausted.
- Treat anchors in inline-code path references correctly and ignore references
  that resolve outside the checked repository.
- Report malformed or non-UTF-8 configuration as a normal CLI usage error.
- Count all descendant working directories affected by lost instructions.

### Security

- Reject path-like fallback filenames and root markers.
- Pin executable GitHub Actions to reviewed commit SHAs.
- Run dependency, static-analysis, and tracked-file secret checks in CI and before
  release.

[Unreleased]: https://github.com/satoissei/agents-doctor/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/satoissei/agents-doctor/releases/tag/v0.2.3
[0.2.2]: https://github.com/satoissei/agents-doctor/releases/tag/v0.2.2
[0.2.1]: https://github.com/satoissei/agents-doctor/releases/tag/v0.2.1
[0.2.0]: https://github.com/satoissei/agents-doctor/releases/tag/v0.2.0
