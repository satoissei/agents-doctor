"""Regression checks for the repository's GitHub Actions supply-chain posture."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_USES = re.compile(r"^\s*-\s+uses:\s+[^@\s]+@([^\s#]+)", re.MULTILINE)


def test_executable_github_actions_are_pinned_to_full_commits() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = [root / "action.yml", *(root / ".github" / "workflows").glob("*.yml")]
    for source in sources:
        refs = _USES.findall(source.read_text(encoding="utf-8"))
        assert refs, f"{source} should declare at least one action"
        assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs), (
            f"{source} contains a mutable GitHub Action reference: {refs}"
        )


@pytest.mark.parametrize("workflow", ["ci.yml", "release.yml"])
def test_secret_scan_treats_tracked_paths_as_operands(workflow: str) -> None:
    source = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / workflow).read_text(
        encoding="utf-8"
    )
    assert '"scan", "--no-verify", "--", *paths' in source


@pytest.mark.parametrize("template", ["false_positive.yml", "simulation-divergence.yml"])
def test_sensitive_issue_templates_require_a_privacy_check(template: str) -> None:
    source = (
        Path(__file__).resolve().parents[1] / ".github" / "ISSUE_TEMPLATE" / template
    ).read_text(encoding="utf-8")
    assert "This issue is public." in source
    assert "id: privacy" in source
    assert "required: true" in source


def test_release_requires_a_tag_ref() -> None:
    source = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")
    assert "RELEASE_REF_TYPE: ${{ github.ref_type }}" in source
    assert 'if ref_type != "tag":' in source
