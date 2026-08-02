# agents-doctor

**See what a coding agent actually loads from your `AGENTS.md` files — including the parts it silently throws away.**

[![CI](https://github.com/satoissei/agents-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/satoissei/agents-doctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agents-doctor)](https://pypi.org/project/agents-doctor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.13-blue)](pyproject.toml)

> **Status:** beta. The project is release-tested and intended for real repositories,
> but its Codex compatibility is explicitly versioned and should be verified when
> upstream loader behaviour changes.

Agents concatenate `AGENTS.md` files from the repository root down to your working
directory, then cut the result off at a byte budget. The cut is not announced in the
UI. Because root-level instructions are concatenated *first*, the instructions closest
to the code you are editing — the specific ones — are the first to disappear.

`agents-doctor` reproduces that loader and tells you exactly what survives.

---

## Why this matters

The failure mode is structural: a large root-level instruction file can spend the
entire budget before the agent reaches the instructions closest to the code being
changed. This is hard to spot by reading files individually, especially in a
monorepo.

Run `agents-doctor explain path/to/package` in the repository you maintain to see
the exact load order, retained bytes, and any instructions that never reach the
agent. The report is intentionally based on the checked-out files rather than on
fixed claims about third-party repositories, so it remains reproducible as those
repositories evolve.

## Install

Install the published package from PyPI with an isolated application environment:

```console
pipx install agents-doctor       # or: uv tool install agents-doctor

# Development checkout
git clone https://github.com/satoissei/agents-doctor.git
cd agents-doctor
pipx install .                  # or: uv tool install .
```

### Try without installing

Run the latest PyPI release in a temporary pipx environment from the repository you
want to check:

```console
pipx run agents-doctor check
```

## Use

```console
agents-doctor check      # report problems, exit 1 if any        (for CI)
agents-doctor explain    # what gets loaded in this directory     (for humans)
agents-doctor budget     # budget pressure across the repository  (for monorepos)
agents-doctor explain --format json  # machine-readable load plan
agents-doctor --codex-config ~/.codex/config.toml explain  # use Codex's loader settings
agents-doctor check --format sarif > agents-doctor.sarif  # GitHub Code Scanning
```

### In CI

For a local checkout of this repository, use the composite action directly:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
- uses: ./
```

Other repositories should use the published release tag rather than a development branch:

```yaml
- uses: satoissei/agents-doctor@v0.2.2
```

### As a pre-commit hook

Use the published release tag as `rev`:

```yaml
repos:
  - repo: https://github.com/satoissei/agents-doctor
    rev: v0.2.2
    hooks:
      - id: agents-doctor
```

Using or evaluating the project in a real repository? Please submit a short
[public adoption report](https://github.com/satoissei/agents-doctor/issues/new?template=adoption_report.yml),
including failed or incomplete evaluations. The project collects no telemetry and
counts only verifiable, voluntarily shared evidence; see
[docs/adoption.md](docs/adoption.md).

## If you write instructions in Japanese, Chinese or Korean

The budget is counted in **bytes**, not characters, and CJK text is three bytes per
character in UTF-8. The same 32 KiB that holds roughly 30,000 characters of English
holds only about 10,000 of Japanese — you hit the ceiling three times sooner.

Worse, the cut happens at a byte offset and the result is then decoded leniently, so a
cut landing mid-character replaces it with `U+FFFD`. `agents-doctor` reports character
counts alongside byte counts, tells you how many characters your budget actually
holds, and flags cuts that corrupt a character.

## Rules

| ID | Name | Default | Detects |
|----|------|---------|---------|
| `AD001` | `lost-instructions` | error | Instructions cut short or never loaded because the budget ran out |
| `AD002` | `broken-path-reference` | error | A reference to a file or directory that no longer exists — a rename or deletion the instructions never caught up with |
| `AD004` | `empty-instructions` | warning | A file that looks like guidance but provides none |

More rules are planned — see [ROADMAP.md](ROADMAP.md). Rule numbering is stable and
reserved, so gaps are intentional.

## Configuration

Everything is optional. Put settings in `.agents-doctor.toml` or under
`[tool.agents-doctor]` in `pyproject.toml`:

```toml
max_bytes = 32768          # match your agent's project_doc_max_bytes
exclude = ["node_modules"] # directories to skip while discovering files
ignore_paths = ["dist/*"]  # references that are allowed not to exist
fallback_filenames = []    # extra per-directory filenames your agent reads

[rules]
AD002 = "warning"          # or "off"
```

Use `--root-marker NAME` when your agent's project root is identified by a marker
other than `.git`. Repeat the option to provide more than one marker:

```console
agents-doctor --root-marker .hg explain path/to/package
```

`max_bytes = 0` is accepted and models a Codex configuration that disables project
instructions entirely.

To avoid copying Codex settings into a second configuration file, pass the Codex
`config.toml` directly with `--codex-config`. The tool reads
`project_doc_max_bytes`, `project_doc_fallback_filenames`, and
`project_root_markers`; unrelated Codex settings are ignored. Command-line options
such as `--max-bytes` and `--root-marker` take precedence.

For uploading SARIF to GitHub Code Scanning, see
[docs/github-code-scanning.md](docs/github-code-scanning.md).

## Privacy and safety

The CLI runs locally: it makes no network requests, sends no telemetry, and does
not execute instructions it reads. Its reports contain repository-relative paths,
file sizes, and path references, so review output before sharing it publicly. The
loader model follows symlinks; do not run it against an untrusted checkout because
an instruction-file symlink can point outside that repository.

See [PRIVACY.md](PRIVACY.md) for the data-handling boundary and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## What it mirrors

The simulation is a behavioural reimplementation of `codex-rs/core/src/agents_md.rs`
from [openai/codex](https://github.com/openai/codex), verified against commit
`2b5bdcf`:

1. The project root is the nearest ancestor holding `.git`.
2. Directories are visited root-first, down to the working directory.
3. Each directory contributes one file: `AGENTS.override.md`, then `AGENTS.md`, then
   any configured fallbacks.
4. Files are appended until `project_doc_max_bytes` (default 32,768) is spent. A file
   that does not fit is cut at a byte offset; once nothing remains, later files are
   never read.
5. A file that is blank after cutting is skipped without consuming budget.

Symlinks are followed, because the loader follows them. This matters: several
well-known repositories ship `AGENTS.md` as a symlink, where measuring the link
reports a dozen bytes instead of the kilobytes actually loaded.

**Scope of verification:** these behaviours were read from source, not observed by
instrumenting a running agent. Byte sizes quoted above are measured; load outcomes are
computed from the algorithm. If you find a divergence from real behaviour, please
[open an issue](https://github.com/satoissei/agents-doctor/issues) — that is the most
valuable bug report this project can receive.

The supported behaviour, its upstream reference, and the update process are recorded
in [docs/codex-compatibility.md](docs/codex-compatibility.md).

## Project operations

See [CONTRIBUTING.md](CONTRIBUTING.md) for development, [SUPPORT.md](SUPPORT.md) for
safe help requests, [GOVERNANCE.md](GOVERNANCE.md) for maintainer decisions, and
[docs/maintainer-playbook.md](docs/maintainer-playbook.md) for the operating cadence.
Bug reports that show a real repository where the simulation is wrong are especially
welcome.

日本語の概要は [README.ja.md](README.ja.md) にあります。

## License

[MIT](LICENSE). See [NOTICE](NOTICE) for upstream compatibility attribution.
