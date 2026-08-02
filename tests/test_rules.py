"""Rule behaviour, including the cases that must *not* produce findings."""

from __future__ import annotations

import agents_doctor.discovery as discovery
from agents_doctor.config import Config
from agents_doctor.discovery import discover_instruction_files
from agents_doctor.models import Finding, Severity
from agents_doctor.rules import build_context, run_rules


def check(root, config: Config = None, **kwargs) -> list[Finding]:
    config = config or Config(**kwargs)
    files = discover_instruction_files(root, config)
    return run_rules(build_context(root, config, files))


def rules_of(findings: list[Finding]) -> list[str]:
    return sorted({f.rule for f in findings})


# --------------------------------------------------------------------------- #
# AD001
# --------------------------------------------------------------------------- #


def test_ad001_reports_a_dropped_file(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": filler(100)})
    findings = [f for f in check(root, max_bytes=1000) if f.rule == "AD001"]
    assert [f.path for f in findings] == ["sub/AGENTS.md"]
    assert findings[0].severity is Severity.ERROR
    assert findings[0].context["dropped"] is True


def test_ad001_reports_a_truncated_file(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(1500)})
    findings = [f for f in check(root, max_bytes=1000) if f.rule == "AD001"]
    assert len(findings) == 1
    assert findings[0].context["lost_bytes"] == 500
    assert findings[0].context["dropped"] is False


def test_ad001_reports_each_file_once_not_once_per_directory(make_repo, filler):
    """A monorepo must not produce one duplicate per working directory."""
    files = {"AGENTS.md": filler(1200)}
    for name in ("a", "b", "c", "d"):
        files[f"{name}/AGENTS.md"] = filler(50)
    root = make_repo(files)
    findings = [f for f in check(root, max_bytes=1000) if f.rule == "AD001"]
    # The root file is cut short in all five working directories, and each child
    # is dropped in its own -- five findings, not one per (file, directory) pair.
    assert len(findings) == 5
    root_finding = next(f for f in findings if f.path == "AGENTS.md")
    assert len(root_finding.context["affected_directories"]) == 5


def test_ad001_counts_descendant_working_directories_without_instruction_files(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(2000), "sub/nested/placeholder.txt": "x"})
    findings = [f for f in check(root, max_bytes=1000) if f.rule == "AD001"]
    assert len(findings) == 1
    assert findings[0].context["affected_directories"] == [".", "sub", "sub/nested"]


def test_ad001_does_not_blame_the_budget_for_a_blank_file(make_repo):
    """A whitespace-only file is AD004's business; claiming the budget ate it is a lie."""
    root = make_repo({"AGENTS.md": "   \n\n  \n"})
    findings = check(root)
    assert [f.rule for f in findings] == ["AD004"]


def test_ad001_does_not_blame_budget_for_blank_file_after_exhaustion(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": "   \n"})
    findings = check(root, max_bytes=1000)

    assert [f.rule for f in findings] == ["AD004"]


def test_ad001_is_silent_when_everything_fits(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(100), "sub/AGENTS.md": filler(100)})
    assert [f for f in check(root, max_bytes=10000) if f.rule == "AD001"] == []


def test_ad001_can_be_disabled(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(5000)})
    config = Config(max_bytes=1000, rules={"AD001": "off"})
    assert [f for f in check(root, config) if f.rule == "AD001"] == []


def test_build_context_does_not_reread_discovered_files(make_repo, filler, monkeypatch):
    root = make_repo(
        {
            "AGENTS.md": filler(1000),
            "a/AGENTS.md": filler(10),
            "a/b/file.py": "pass\n",
            "c/file.py": "pass\n",
        }
    )
    config = Config(max_bytes=1000)
    read_paths: list[str] = []
    original = discovery.read_instruction_file

    def record_read(path, project_root):
        read_paths.append(path.relative_to(project_root).as_posix())
        return original(path, project_root)

    monkeypatch.setattr(discovery, "read_instruction_file", record_read)
    files = discovery.discover_instruction_files(root, config)
    context = build_context(root, config, files)

    assert read_paths == ["AGENTS.md", "a/AGENTS.md"]
    assert set(context.plans) == {".", "a", "a/b", "c"}
    assert context.plans["a"].chunks[1].file.unread
    assert context.plans["a"].chunks[1].file.content_known
    assert context.plans["a/b"].chunks[1].file.content_known


# --------------------------------------------------------------------------- #
# AD002
# --------------------------------------------------------------------------- #


def test_ad002_reports_a_missing_path(make_repo):
    """The directory is there but the file is not -- a rename or deletion."""
    root = make_repo(
        {"AGENTS.md": "Run the tests in `tests/unit/`.\n", "tests/e2e/case.py": "pass\n"}
    )
    findings = [f for f in check(root) if f.rule == "AD002"]
    assert len(findings) == 1
    assert findings[0].context["reference"] == "tests/unit"
    assert findings[0].line == 1


def test_ad002_ignores_a_bare_filename_that_exists_somewhere(make_repo):
    """`see comms.py` is shorthand for a file elsewhere, not a claim about location."""
    root = make_repo(
        {
            "AGENTS.md": "Message shapes live in `comms.py`.\n",
            "src/deep/nested/comms.py": "pass\n",
        }
    )
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_reports_a_bare_filename_that_exists_nowhere(make_repo):
    """Shorthand still has to refer to something. Nothing named this exists."""
    root = make_repo({"AGENTS.md": "The entry point is `setup.py`.\n"})
    findings = [f for f in check(root) if f.rule == "AD002"]
    assert [f.context["reference"] for f in findings] == ["setup.py"]


def test_ad002_ignores_references_into_directories_that_do_not_exist(make_repo):
    """An API route or another project's layout is not a path in this repository."""
    root = make_repo({"AGENTS.md": "Call `app/list` and see `other-project/src/main.rs`.\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_ignores_filename_templates(make_repo):
    root = make_repo(
        {
            "AGENTS.md": "Add a migration as `versions/vYYYY_MM_DD.py`.\n",
            "versions/v2026_01_01.py": "pass\n",
        }
    )
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_accepts_an_existing_path(make_repo):
    root = make_repo({"AGENTS.md": "See `src/app.py`.\n", "src/app.py": "pass\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_resolves_relative_to_the_files_own_directory(make_repo):
    root = make_repo({"pkg/AGENTS.md": "See `main.py`.\n", "pkg/main.py": "pass\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_ignores_fenced_code_blocks(make_repo):
    """Commands and sample output name paths that need not exist."""
    body = "Setup:\n\n```bash\ncp config/example.toml config/local.toml\n```\n"
    root = make_repo({"AGENTS.md": body})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_ignores_things_that_are_not_repository_paths(make_repo):
    body = (
        "Use `npm run build` and `--verbose`.\n"
        "Read <https://example.com/docs>, `$HOME/.config`, `/usr/bin/env`.\n"
        "Install `@scope/package` version `2`.\n"
        "Glob `src/**/*.ts` is fine too.\n"
    )
    root = make_repo({"AGENTS.md": body})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_honours_ignore_paths(make_repo):
    root = make_repo({"AGENTS.md": "Artifacts land in `out/bundle.js`.\n", "out/.keep": ""})
    assert [f for f in check(root) if f.rule == "AD002"]
    config = Config(ignore_paths=["out/*"])
    assert [f for f in check(root, config) if f.rule == "AD002"] == []


def test_ad002_ignores_references_into_excluded_directories(make_repo):
    """Build output is absent from a clean checkout; naming it is not a mistake."""
    root = make_repo({"AGENTS.md": "Compiled crates land in `target/`, ignore `node_modules/`.\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_checks_markdown_links(make_repo):
    root = make_repo({"AGENTS.md": "See [the guide](docs/guide.md).\n", "docs/index.md": "#\n"})
    findings = [f for f in check(root) if f.rule == "AD002"]
    assert [f.context["reference"] for f in findings] == ["docs/guide.md"]


def test_ad002_accepts_inline_code_paths_with_anchors(make_repo):
    root = make_repo({"AGENTS.md": "See `docs/guide.md#install`.\n", "docs/guide.md": "#"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_ignores_references_that_escape_the_repository(make_repo):
    root = make_repo({"AGENTS.md": "Do not inspect `../outside.txt`.\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


def test_ad002_accepts_parent_references_that_remain_inside_the_repository(make_repo):
    root = make_repo({"pkg/AGENTS.md": "See `../shared.py`.\n", "shared.py": "pass\n"})
    assert [f for f in check(root) if f.rule == "AD002"] == []


# --------------------------------------------------------------------------- #
# AD004
# --------------------------------------------------------------------------- #


def test_ad004_reports_an_empty_file(make_repo):
    root = make_repo({"AGENTS.md": "\n\n   \n"})
    findings = [f for f in check(root) if f.rule == "AD004"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_ad004_reports_headings_only(make_repo):
    root = make_repo({"AGENTS.md": "# Project\n\n## Setup\n"})
    assert [f.rule for f in check(root) if f.rule == "AD004"] == ["AD004"]


def test_ad004_reports_placeholder_text(make_repo):
    root = make_repo({"AGENTS.md": "# Guide\n\nTODO\n"})
    assert [f.rule for f in check(root) if f.rule == "AD004"] == ["AD004"]


def test_ad004_accepts_real_content(make_repo):
    root = make_repo({"AGENTS.md": "# Guide\n\nAlways run the linter first.\n"})
    assert [f for f in check(root) if f.rule == "AD004"] == []


# --------------------------------------------------------------------------- #
# whole-suite behaviour
# --------------------------------------------------------------------------- #


def test_a_healthy_repository_produces_no_findings(make_repo):
    """The most important test: no false positives on a well-formed repository."""
    root = make_repo(
        {
            "AGENTS.md": (
                "# Project\n\n"
                "Source lives in `src/`. Run `npm test` before pushing.\n"
                "See [the contributor guide](CONTRIBUTING.md).\n"
            ),
            "CONTRIBUTING.md": "# Contributing\n",
            "src/index.ts": "export {};\n",
            "src/AGENTS.md": "# Source\n\nKeep modules small.\n",
        }
    )
    assert check(root) == []


def test_findings_are_ordered_most_severe_first(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(2000), "sub/AGENTS.md": "# Only a heading\n"})
    findings = check(root, max_bytes=1000)
    assert rules_of(findings) == ["AD001", "AD004"]
    assert findings[0].severity is Severity.ERROR
