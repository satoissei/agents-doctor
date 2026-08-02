"""Tests for the loader reproduction.

These are the tests that matter most: every rule trusts this module to model the
agent's behaviour, so each documented behaviour gets an explicit case.
"""

from __future__ import annotations

import sys

import pytest

import agents_doctor.discovery as discovery
from agents_doctor.config import Config, ConfigError
from agents_doctor.discovery import (
    build_load_plan,
    chain_directories,
    discover_instruction_files,
    find_project_root,
    instruction_file_in,
)


def test_project_root_is_nearest_ancestor_with_marker(make_repo):
    root = make_repo({"pkg/sub/AGENTS.md": "hi"})
    assert find_project_root(root / "pkg" / "sub") == root


def test_without_marker_only_the_working_directory_is_considered(make_repo):
    root = make_repo({"pkg/AGENTS.md": "hi"}, git=False)
    found = find_project_root(root / "pkg")
    assert found == root / "pkg"


def test_chain_runs_root_first(make_repo):
    root = make_repo({"a/b/AGENTS.md": "hi"})
    chain = chain_directories(root / "a" / "b", root)
    assert chain == [root, root / "a", root / "a" / "b"]


def test_override_wins_within_a_directory(make_repo):
    root = make_repo({"AGENTS.md": "plain", "AGENTS.override.md": "override"})
    found = instruction_file_in(root, root, Config())
    assert found is not None
    assert found.text == "override"


def test_fallback_filename_is_used_when_configured(make_repo):
    root = make_repo({"CLAUDE.md": "shared"})
    assert instruction_file_in(root, root, Config()) is None
    config = Config(fallback_filenames=["CLAUDE.md"])
    found = instruction_file_in(root, root, config)
    assert found is not None
    assert found.text == "shared"


def test_programmatic_path_like_fallback_is_rejected(make_repo):
    root = make_repo({"AGENTS.md": "shared"})
    with pytest.raises(ConfigError, match="not a path"):
        instruction_file_in(root, root, Config(fallback_filenames=["../private.md"]))


def test_symlinked_instruction_file_is_followed(make_repo):
    root = make_repo({"CLAUDE.md": "x" * 5000})
    link = root / "AGENTS.md"
    try:
        link.symlink_to(root / "CLAUDE.md")
    except OSError as exc:
        if sys.platform == "win32" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink creation requires Developer Mode or symlink privilege")
        raise
    found = instruction_file_in(root, root, Config())
    assert found is not None
    # Measuring the link instead of its target would report a handful of bytes.
    assert found.raw_size == 5000


def test_everything_fits_within_budget(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(100), "sub/AGENTS.md": filler(200)})
    plan = build_load_plan(root / "sub", root, Config(max_bytes=1000))
    assert not plan.over_budget
    assert [c.included_bytes for c in plan.chunks] == [100, 200]
    assert plan.headroom == 700


def test_deepest_file_is_cut_first(make_repo, filler):
    """The working directory's own instructions are concatenated last."""
    root = make_repo({"AGENTS.md": filler(900), "sub/AGENTS.md": filler(500)})
    plan = build_load_plan(root / "sub", root, Config(max_bytes=1000))
    root_chunk, sub_chunk = plan.chunks
    assert root_chunk.included_bytes == 900 and not root_chunk.truncated
    assert sub_chunk.truncated and sub_chunk.included_bytes == 100
    assert sub_chunk.lost_bytes == 400
    assert plan.lost_bytes == 400


def test_files_after_the_budget_is_spent_are_never_read(make_repo, filler):
    root = make_repo(
        {"AGENTS.md": filler(1000), "a/AGENTS.md": filler(50), "a/b/AGENTS.md": filler(50)}
    )
    plan = build_load_plan(root / "a" / "b", root, Config(max_bytes=1000))
    assert [c.dropped for c in plan.chunks] == [False, True, True]
    assert plan.loaded_bytes == 1000


def test_budget_exhaustion_does_not_read_later_instruction_contents(make_repo, filler, monkeypatch):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": "do not read me"})
    read_paths: list[str] = []
    original = discovery.read_instruction_file

    def record_read(path, project_root):
        read_paths.append(path.name)
        return original(path, project_root)

    monkeypatch.setattr(discovery, "read_instruction_file", record_read)
    plan = build_load_plan(root / "sub", root, Config(max_bytes=1000))

    assert read_paths == ["AGENTS.md"]
    assert plan.chunks[1].file.unread
    assert not plan.chunks[1].file.content_known
    assert plan.chunks[1].dropped


def test_zero_byte_file_after_budget_exhaustion_is_known_to_be_blank(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": ""})
    plan = build_load_plan(root / "sub", root, Config(max_bytes=1000))

    chunk = plan.chunks[1]
    assert chunk.file.unread
    assert chunk.file.content_known
    assert chunk.blank
    assert not chunk.dropped
    assert not plan.over_budget


def test_blank_file_does_not_consume_budget(make_repo, filler):
    root = make_repo({"AGENTS.md": "   \n\n  ", "sub/AGENTS.md": filler(300)})
    plan = build_load_plan(root / "sub", root, Config(max_bytes=1000))
    blank, real = plan.chunks
    assert blank.included_bytes == 0
    assert blank.blank and not blank.dropped
    assert real.included_bytes == 300 and not real.truncated
    # Nothing was in the blank file, so nothing was lost.
    assert plan.lost_bytes == 0 and not plan.over_budget


def test_blank_prefix_after_cut_does_not_consume_budget(make_repo, filler):
    root = make_repo({"AGENTS.md": " " * 10 + "root instructions", "sub/AGENTS.md": filler(5)})
    plan = build_load_plan(root / "sub", root, Config(max_bytes=10))
    prefix, child = plan.chunks
    assert prefix.skipped_after_cut
    assert not prefix.dropped
    assert child.included_bytes == 5
    assert plan.loaded_bytes == 5
    assert plan.lost_bytes == prefix.file.raw_size


def test_a_single_oversized_file_is_cut_at_the_budget(make_repo, filler):
    root = make_repo({"AGENTS.md": filler(5000)})
    plan = build_load_plan(root, root, Config(max_bytes=1000))
    assert plan.chunks[0].included_bytes == 1000
    assert plan.chunks[0].lost_bytes == 4000


def test_discovery_returns_one_file_per_directory(make_repo):
    root = make_repo({"AGENTS.md": "a", "AGENTS.override.md": "b", "sub/AGENTS.md": "c"})
    found = discover_instruction_files(root, Config())
    assert [f.rel for f in found] == ["AGENTS.override.md", "sub/AGENTS.md"]


def test_discovery_skips_excluded_directories(make_repo):
    root = make_repo({"AGENTS.md": "a", "node_modules/pkg/AGENTS.md": "b"})
    found = discover_instruction_files(root, Config())
    assert [f.rel for f in found] == ["AGENTS.md"]
