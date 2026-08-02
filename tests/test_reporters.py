"""Reporter interoperability and escaping guarantees."""

from __future__ import annotations

import json

from agents_doctor.models import Finding, Severity
from agents_doctor.reporters import format_github, format_sarif, format_text


def _finding(*, path: str = "AGENTS.md", severity: Severity = Severity.ERROR) -> Finding:
    return Finding(
        rule="AD001",
        name="lost-instructions",
        severity=severity,
        path=path,
        line=0,
        message="Example finding",
    )


def test_github_annotations_escape_property_delimiters() -> None:
    output = format_github([_finding(path="AGENTS,unsafe:example.md")], files_checked=1)
    assert output.startswith("::error file=AGENTS%2Cunsafe%3Aexample.md::")


def test_sarif_uses_note_for_informational_findings() -> None:
    payload = json.loads(format_sarif([_finding(severity=Severity.INFO)], files_checked=1))
    assert payload["runs"][0]["results"][0]["level"] == "note"


def test_text_reporter_renders_control_characters_visibly() -> None:
    finding = _finding(path="unsafe\n\x1b[2J.md")
    output = format_text([finding], files_checked=1)
    assert "unsafe\\n\\x1b[2J.md" in output
    assert "unsafe\n" not in output
    assert "\x1b" not in output
