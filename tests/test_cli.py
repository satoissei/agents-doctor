"""Command line behaviour, especially the exit codes CI depends on."""

from __future__ import annotations

import json

import pytest

from agents_doctor.cli import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, main


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_clean_repository_exits_zero(make_repo, capsys):
    root = make_repo({"AGENTS.md": "# Guide\n\nRun the linter.\n"})
    code, out, _ = run(capsys, "check", str(root))
    assert code == EXIT_OK
    assert "No problems found" in out


def test_findings_exit_one(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(5000)})
    code, out, _ = run(capsys, "--max-bytes", "1000", "check", str(root))
    assert code == EXIT_FINDINGS
    assert "AD001" in out


def test_exit_zero_flag_suppresses_the_failure(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(5000)})
    code, _, _ = run(capsys, "--max-bytes", "1000", "check", str(root), "--exit-zero")
    assert code == EXIT_OK


def test_missing_path_is_a_usage_error(capsys, tmp_path):
    code, _, err = run(capsys, "check", str(tmp_path / "nope"))
    assert code == EXIT_ERROR
    assert "does not exist" in err


def test_unknown_rule_is_a_usage_error(make_repo, capsys):
    root = make_repo({"AGENTS.md": "content\n"})
    code, _, err = run(capsys, "check", str(root), "--rule", "AD999")
    assert code == EXIT_ERROR
    assert "AD999" in err


def test_json_output_is_valid_and_complete(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(5000)})
    code, out, _ = run(capsys, "--max-bytes", "1000", "check", str(root), "--format", "json")
    assert code == EXIT_FINDINGS
    payload = json.loads(out)
    assert payload["files_checked"] == 1
    assert payload["summary"]["error"] == 1
    assert payload["findings"][0]["rule"] == "AD001"


def test_github_format_emits_workflow_commands(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(5000)})
    _, out, _ = run(capsys, "--max-bytes", "1000", "check", str(root), "--format", "github")
    assert out.startswith("::error file=AGENTS.md::")
    # Workflow commands are newline-delimited, so a finding must stay on one line.
    assert len(out.strip().splitlines()) == 1


def test_sarif_output_is_valid_for_code_scanning(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(5000)})
    code, out, _ = run(capsys, "--max-bytes", "1000", "check", str(root), "--format", "sarif")
    assert code == EXIT_FINDINGS
    payload = json.loads(out)
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["tool"]["driver"]["name"] == "agents-doctor"
    result = payload["runs"][0]["results"][0]
    assert result["ruleId"] == "AD001"
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "AGENTS.md"
    assert "uriBaseId" not in result["locations"][0]["physicalLocation"]["artifactLocation"]
    assert payload["runs"][0]["automationDetails"]["id"] == "agents-doctor"


def test_explain_names_what_is_lost(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": filler(500)})
    code, out, _ = run(capsys, "--max-bytes", "1000", "explain", str(root / "sub"))
    assert code == EXIT_OK
    assert "NEVER LOADED" in out
    assert "sub/AGENTS.md" in out


def test_explain_reports_headroom_when_healthy(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(100)})
    _, out, _ = run(capsys, "--max-bytes", "1000", "explain", str(root))
    assert "All instructions fit" in out
    assert "900 bytes of headroom" in out


def test_explain_json_is_machine_readable(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(100), "sub/AGENTS.md": filler(500)})
    code, out, _ = run(capsys, "explain", str(root / "sub"), "--format", "json")
    assert code == EXIT_OK
    payload = json.loads(out)
    assert payload["schema_version"] == 1
    assert payload["target"] == "sub"
    assert payload["requested_bytes"] == 600
    assert [chunk["status"] for chunk in payload["chunks"]] == ["loaded", "loaded"]


def test_explain_marks_unread_character_count_as_unknown(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": filler(500)})
    code, out, _ = run(
        capsys,
        "--max-bytes",
        "1000",
        "explain",
        str(root / "sub"),
        "--format",
        "json",
    )

    assert code == EXIT_OK
    chunk = json.loads(out)["chunks"][1]
    assert chunk["status"] == "never_loaded"
    assert chunk["lost_characters"] == 0
    assert chunk["lost_characters_known"] is False
    assert chunk["content_read"] is False


def test_explain_density_excludes_unread_size_only_files(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(1000), "sub/AGENTS.md": filler(1000)})
    code, out, _ = run(capsys, "--max-bytes", "1000", "explain", str(root / "sub"))

    assert code == EXIT_OK
    assert "character count unknown" in out
    assert "bytes per character" not in out


def test_explain_accepts_custom_root_marker(make_repo, filler, capsys):
    root = make_repo(
        {"workspace.marker": "", "AGENTS.md": filler(100), "sub/AGENTS.md": filler(50)}, git=False
    )
    code, out, _ = run(
        capsys,
        "explain",
        str(root / "sub"),
        "--root-marker",
        "workspace.marker",
    )
    assert code == EXIT_OK
    assert "sub/AGENTS.md" in out


def test_path_like_root_marker_is_a_usage_error(make_repo, capsys):
    root = make_repo({"AGENTS.md": "content\n"})
    code, _, err = run(capsys, "explain", str(root), "--root-marker", "../outside")
    assert code == EXIT_ERROR
    assert "not a path" in err


def test_invalid_utf8_configuration_is_a_usage_error(make_repo, capsys):
    root = make_repo({"AGENTS.md": "content\n"})
    (root / ".agents-doctor.toml").write_bytes(b"\xff")
    code, _, err = run(capsys, "check", str(root))
    assert code == EXIT_ERROR
    assert "valid UTF-8" in err


def test_non_table_pyproject_tool_is_a_usage_error(make_repo, capsys):
    root = make_repo({"AGENTS.md": "content\n", "pyproject.toml": 'tool = "broken"\n'})
    code, _, err = run(capsys, "check", str(root))
    assert code == EXIT_ERROR
    assert "tool must be a table" in err


def test_explain_reads_codex_loader_settings(make_repo, filler, capsys):
    root = make_repo(
        {
            "workspace.marker": "",
            "codex.toml": (
                "project_doc_max_bytes = 100\n"
                'project_root_markers = ["workspace.marker"]\n'
                'project_doc_fallback_filenames = ["CLAUDE.md"]\n'
            ),
            "CLAUDE.md": filler(10),
            "sub/AGENTS.md": filler(20),
        },
        git=False,
    )
    code, out, _ = run(
        capsys,
        "explain",
        str(root / "sub"),
        "--codex-config",
        str(root / "codex.toml"),
        "--format",
        "json",
    )
    assert code == EXIT_OK
    payload = json.loads(out)
    assert payload["max_bytes"] == 100
    assert [chunk["path"] for chunk in payload["chunks"]] == ["CLAUDE.md", "sub/AGENTS.md"]


def test_budget_lists_the_worst_directory_first(make_repo, filler, capsys):
    root = make_repo({"AGENTS.md": filler(100), "big/AGENTS.md": filler(900)})
    _, out, _ = run(capsys, "--max-bytes", "1000", "budget", str(root))
    rows = [line for line in out.splitlines() if line.startswith(("big/", "."))]
    assert rows[0].startswith("big/")


def test_budget_handles_a_repository_with_no_instructions(make_repo, capsys):
    root = make_repo({"README.md": "hi\n"})
    code, out, _ = run(capsys, "budget", str(root))
    assert code == EXIT_OK
    assert "No AGENTS.md files found" in out


def test_rules_command_lists_every_rule(capsys):
    code, out, _ = run(capsys, "rules")
    assert code == EXIT_OK
    assert "AD001" in out and "AD002" in out and "AD004" in out


def test_no_command_prints_help(capsys):
    code, out, _ = run(capsys)
    assert code == EXIT_ERROR
    assert "usage:" in out


def test_max_bytes_must_be_non_negative(make_repo, capsys):
    root = make_repo({"AGENTS.md": "content\n"})
    code, _, err = run(capsys, "--max-bytes", "-1", "check", str(root))
    assert code == EXIT_ERROR
    assert "non-negative" in err


@pytest.mark.parametrize("command", ["check", "explain", "budget"])
def test_commands_accept_a_file_path_and_use_its_directory(make_repo, capsys, command):
    root = make_repo({"AGENTS.md": "# Guide\n\nReal content.\n"})
    code, _, _ = run(capsys, command, str(root / "AGENTS.md"))
    assert code == EXIT_OK
