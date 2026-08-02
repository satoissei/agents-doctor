"""Rendering of findings and load plans.

Output is deterministic so it can be diffed in CI, and plain ASCII so it survives
Windows consoles and log scrapers.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

from agents_doctor import __version__
from agents_doctor.models import Finding, LoadPlan, Severity

_SEVERITY_LABEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}

_CONTROL_CHARACTERS = {
    **{codepoint: f"\\x{codepoint:02x}" for codepoint in range(32)},
    127: "\\x7f",
}
_CONTROL_CHARACTERS.update({9: "\\t", 10: "\\n", 13: "\\r", 27: "\\x1b"})


def _visible_text(value: str) -> str:
    """Render control characters visibly in human-readable terminal output."""
    return value.translate(_CONTROL_CHARACTERS)


def _human_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    return f"{value / 1024:.1f} KiB"


def format_text(findings: Sequence[Finding], *, files_checked: int) -> str:
    """Human-readable report, one block per finding."""
    if not findings:
        return f"No problems found in {files_checked} instruction file(s)."

    lines: list[str] = []
    for finding in findings:
        label = _SEVERITY_LABEL[finding.severity]
        lines.append(
            f"{_visible_text(finding.location)}: {label} [{finding.rule}] "
            f"{_visible_text(finding.message)}"
        )
        if finding.hint:
            lines.append(f"    {_visible_text(finding.hint)}")
        lines.append("")

    counts = summarise(findings)
    summary = ", ".join(
        f"{counts[severity]} {_SEVERITY_LABEL[severity]}(s)"
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO)
        if counts[severity]
    )
    lines.append(f"{summary} in {files_checked} instruction file(s).")
    return "\n".join(lines)


def format_json(findings: Sequence[Finding], *, files_checked: int) -> str:
    """Machine-readable report for scripts and dashboards."""
    payload = {
        # Consumers parse this output; the version changes when the shape does.
        "schema_version": 1,
        "files_checked": files_checked,
        "summary": {
            _SEVERITY_LABEL[severity]: count for severity, count in summarise(findings).items()
        },
        "findings": [
            {
                "rule": f.rule,
                "name": f.name,
                "severity": f.severity.value,
                "path": f.path,
                "line": f.line,
                "message": f.message,
                "hint": f.hint,
                **({"context": f.context} if f.context else {}),
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)


def format_github(findings: Sequence[Finding], *, files_checked: int) -> str:
    """GitHub Actions workflow commands, rendered as inline annotations."""
    if not findings:
        return f"No problems found in {files_checked} instruction file(s)."
    lines = []
    for f in findings:
        level = "notice" if f.severity is Severity.INFO else f.severity.value
        # Workflow commands are newline-delimited, so the message must stay on one line.
        message = f"[{f.rule}] {f.message}"
        if f.hint:
            message += f" {f.hint}"
        location = f"file={_escape_property(f.path)}" + (f",line={f.line}" if f.line else "")
        lines.append(f"::{level} {location}::{_escape(message)}")
    return "\n".join(lines)


def format_sarif(findings: Sequence[Finding], *, files_checked: int) -> str:
    """Render findings as SARIF 2.1.0 for GitHub Code Scanning."""
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for finding in findings:
        rules.setdefault(
            finding.rule,
            {
                "id": finding.rule,
                "name": finding.name,
                "shortDescription": {"text": finding.name},
            },
        )
        result: dict[str, object] = {
            "ruleId": finding.rule,
            # SARIF accepts ``note`` rather than our internal ``info`` label.
            "level": _SEVERITY_LABEL[finding.severity],
            "message": {"text": finding.message},
        }
        location: dict[str, object] = {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": finding.path,
                }
            }
        }
        if finding.line:
            physical = location["physicalLocation"]
            if not isinstance(physical, dict):  # pragma: no cover - internal invariant
                raise RuntimeError("SARIF physical location must be an object")
            physical["region"] = {"startLine": finding.line}
        result["locations"] = [location]
        if finding.hint:
            result["fixes"] = [{"description": {"text": finding.hint}}]
        results.append(result)

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agents-doctor",
                        "version": __version__,
                        "informationUri": "https://github.com/satoissei/agents-doctor",
                        "rules": list(rules.values()),
                    }
                },
                "automationDetails": {"id": "agents-doctor"},
                "results": results,
                "properties": {"filesChecked": files_checked},
            }
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _escape(message: str) -> str:
    """Escape the characters GitHub treats as workflow-command syntax."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    """Escape a GitHub workflow-command property value.

    Annotation properties use commas and colons as delimiters in addition to the
    command-level percent and newline escaping. Repository paths are normally
    simple, but escaping them avoids malformed annotations for unusual filenames.
    """
    return _escape(value).replace(":", "%3A").replace(",", "%2C")


def summarise(findings: Iterable[Finding]) -> dict[Severity, int]:
    counts = dict.fromkeys(Severity, 0)
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def format_plan(plan: LoadPlan) -> str:
    """Render one load plan: what the agent sees, in the order it sees it."""
    lines = [
        f"Working directory: {_visible_text(plan.target)}/",
        f"Budget: {_human_bytes(plan.max_bytes)} ({plan.max_bytes:,} bytes)",
        "",
    ]
    if not plan.chunks:
        lines.append("  (no instruction files apply here)")
        return "\n".join(lines)

    lines.append("Loaded in this order (repository root first):")
    remaining = plan.max_bytes
    for index, chunk in enumerate(plan.chunks, start=1):
        file = chunk.file
        if file.unread and chunk.blank:
            status = "not read"
            detail = "known to be blank; consumes no budget"
        elif chunk.blank:
            status = "skipped"
            detail = "blank file; consumes no budget"
        elif chunk.skipped_after_cut:
            status = "skipped"
            detail = "prefix was blank after the cut; consumes no budget"
        elif chunk.dropped:
            status = "NEVER LOADED"
            detail = f"all {file.raw_size:,} bytes lost"
            if not chunk.lost_chars_known:
                detail += "; character count unknown because contents were not read"
        elif chunk.truncated:
            status = "CUT SHORT"
            detail = (
                f"{chunk.included_bytes:,} of {file.raw_size:,} bytes kept, "
                f"{chunk.lost_chars:,} characters lost"
            )
            if chunk.splits_character:
                detail += ", cut inside a character"
        else:
            status = "loaded"
            detail = f"{file.raw_size:,} bytes"
            if not file.is_ascii:
                detail += f" for {file.char_count:,} characters"
        remaining = max(0, remaining - chunk.included_bytes)
        lines.append(f"  {index}. [{status}] {_visible_text(file.rel)}")
        lines.append(f"     {detail}; {remaining:,} bytes of budget left")

    lines.append("")
    if plan.over_budget:
        lines.append(f"{plan.lost_bytes:,} bytes of instructions never reach the model.")
    else:
        lines.append(f"All instructions fit. {plan.headroom:,} bytes of headroom remain.")

    density = _character_density(plan)
    if density > 1.05:
        # The budget is counted in bytes, so non-ASCII authors reach it sooner. Say
        # by how much, in the unit they actually write in.
        lines.append(
            f"These instructions average {density:.1f} bytes per character, so the "
            f"{plan.max_bytes:,}-byte budget holds about "
            f"{int(plan.max_bytes / density):,} characters."
        )
    return "\n".join(lines)


def format_plan_json(plan: LoadPlan) -> str:
    """Render a load plan as stable machine-readable JSON."""
    remaining = plan.max_bytes
    chunks: list[dict[str, object]] = []
    for chunk in plan.chunks:
        file = chunk.file
        if file.unread and chunk.blank:
            status = "not_read"
        elif chunk.blank:
            status = "skipped"
        elif chunk.skipped_after_cut:
            status = "skipped_after_cut"
        elif chunk.dropped:
            status = "never_loaded"
        elif chunk.truncated:
            status = "cut_short"
        else:
            status = "loaded"
        remaining = max(0, remaining - chunk.included_bytes)
        chunks.append(
            {
                "path": file.rel,
                "status": status,
                "raw_bytes": file.raw_size,
                "included_bytes": chunk.included_bytes,
                "lost_bytes": chunk.lost_bytes,
                "lost_characters": chunk.lost_chars,
                "lost_characters_known": chunk.lost_chars_known,
                "content_read": not file.unread,
                "splits_character": chunk.splits_character,
                "remaining_bytes": remaining,
            }
        )

    payload = {
        "schema_version": 1,
        "target": plan.target,
        "max_bytes": plan.max_bytes,
        "requested_bytes": plan.requested_bytes,
        "loaded_bytes": plan.loaded_bytes,
        "lost_bytes": plan.lost_bytes,
        "headroom_bytes": plan.headroom,
        "over_budget": plan.over_budget,
        "chunks": chunks,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _character_density(plan: LoadPlan) -> float:
    """Bytes per known character across the files in a plan; 1.0 for pure ASCII."""
    known = [chunk.file for chunk in plan.chunks if chunk.file.content_known]
    total_bytes = sum(file.raw_size for file in known)
    total_chars = sum(file.char_count for file in known)
    return total_bytes / total_chars if total_chars else 1.0


def format_budget(plans: Sequence[LoadPlan]) -> str:
    """One row per working directory, worst pressure first."""
    header = f"{'working directory':<44} {'total':>10} {'budget':>10} {'used':>7}  status"
    lines = [header, "-" * len(header)]
    ordered = sorted(plans, key=lambda p: (-p.requested_bytes, p.target))
    for plan in ordered:
        used = plan.requested_bytes / plan.max_bytes * 100 if plan.max_bytes else 0.0
        if plan.over_budget:
            status = f"OVER by {plan.lost_bytes:,} B"
        elif used >= 80:
            status = "near limit"
        else:
            status = "ok"
        target = plan.target if plan.target == "." else f"{plan.target}/"
        target = _visible_text(target)
        if len(target) > 43:
            target = "..." + target[-40:]
        lines.append(
            f"{target:<44} {plan.requested_bytes:>10,} {plan.max_bytes:>10,} "
            f"{used:>6.1f}%  {status}"
        )
    return "\n".join(lines)
