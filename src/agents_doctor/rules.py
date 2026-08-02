"""The checks run by ``agents-doctor check``.

Rules are deliberately few and conservative. A false positive costs a user more
than a missed finding: it teaches them to ignore the tool. Anything that cannot
be decided from the repository alone is left alone.
"""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agents_doctor.config import Config
from agents_doctor.discovery import load_instruction_chunk
from agents_doctor.models import Finding, InstructionFile, LoadedChunk, LoadPlan, Severity


@dataclass(frozen=True)
class RuleSpec:
    """Static description of a rule, used for docs and ``--list-rules``."""

    id: str
    name: str
    default_severity: Severity
    summary: str


RULES: dict[str, RuleSpec] = {
    "AD001": RuleSpec(
        "AD001",
        "lost-instructions",
        Severity.ERROR,
        "Instructions never reach the model because the byte budget runs out.",
    ),
    "AD002": RuleSpec(
        "AD002",
        "broken-path-reference",
        Severity.ERROR,
        "A repository path named in the instructions does not exist.",
    ),
    "AD004": RuleSpec(
        "AD004",
        "empty-instructions",
        Severity.WARNING,
        "An instruction file holds no usable content.",
    ),
}


@dataclass
class Context:
    """Everything a rule needs to run."""

    root: Path
    config: Config
    files: list[InstructionFile]
    plans: dict[str, LoadPlan]
    """Load plan per repository directory, keyed by repo-relative path."""

    _basenames: set[str] | None = None

    def name_exists_anywhere(self, name: str) -> bool:
        """Whether anything in the repository -- file or directory -- carries this name.

        Instruction files habitually name something without saying where it lives
        ("see comms.py", "the rules live in models/"). That is shorthand for a
        file or directory elsewhere in the tree, not a claim about location, so it
        is only wrong when nothing of that name exists at all. Directories count:
        omitting them turns every `models/` into a false report. The index is
        built once, on the first question asked of it.
        """
        if self._basenames is None:
            excluded = set(self.config.exclude)
            found: set[str] = set()
            for _, dirnames, filenames in os.walk(self.root):
                dirnames[:] = [d for d in dirnames if d not in excluded]
                found.update(filenames)
                found.update(dirnames)
            self._basenames = found
        return name in self._basenames


def _fmt(count: int, unit: str) -> str:
    return f"{count:,} {unit}{'' if count == 1 else 's'}"


def _finding(
    rule_id: str,
    severity: Severity,
    *,
    path: str,
    line: int,
    message: str,
    hint: str | None = None,
    context: dict[str, Any] | None = None,
) -> Finding:
    """Build a finding, taking its name from the one place rules are declared."""
    return Finding(
        rule=rule_id,
        name=RULES[rule_id].name,
        severity=severity,
        path=path,
        line=line,
        message=message,
        hint=hint,
        context=context or {},
    )


# --------------------------------------------------------------------------- #
# AD001: instructions lost to the byte budget
# --------------------------------------------------------------------------- #


def check_lost_instructions(ctx: Context, severity: Severity) -> list[Finding]:
    """Report every file that is cut short or skipped entirely.

    A file's fate depends on which directory the agent is working in, so the same
    file may be fine at the repository root and lost three levels down. Findings
    are reported once per file, naming how many working directories are affected,
    rather than once per directory -- otherwise a large monorepo produces pages of
    duplicates for a single root cause.
    """
    # Every plan that includes a file shares the same chain of ancestors above it,
    # so the budget left when the file is reached -- and therefore its fate -- is
    # identical in all of them. The first sighting is the whole story; the rest
    # only tell us how many working directories are affected.
    lost: dict[str, LoadedChunk] = {}
    affected: dict[str, list[str]] = {}
    for target, plan in sorted(ctx.plans.items()):
        for chunk in plan.chunks:
            if not (chunk.dropped or chunk.truncated):
                continue
            rel = chunk.file.rel
            affected.setdefault(rel, []).append(target)
            lost.setdefault(rel, chunk)

    findings: list[Finding] = []
    for rel, chunk in sorted(lost.items()):
        targets = affected[rel]
        where = (
            f"working in {targets[0]}/"
            if len(targets) == 1
            else f"working in {len(targets):,} directories, including {targets[0]}/"
        )
        if chunk.dropped:
            message = (
                f"never loaded when {where}: the budget is already spent by "
                f"instructions closer to the repository root"
            )
            hint = (
                f"Free at least {_fmt(chunk.file.raw_size, 'byte')} earlier in the chain, "
                f"or raise project_doc_max_bytes above {ctx.config.max_bytes:,}."
            )
        else:
            message = (
                f"cut short when {where}: "
                f"{_fmt(chunk.lost_bytes, 'byte')} "
                f"({_fmt(chunk.lost_chars, 'character')}) never reach the model"
            )
            hint = (
                f"Only the first {_fmt(chunk.included_bytes, 'byte')} survive. "
                f"Shorten the file or raise project_doc_max_bytes above "
                f"{ctx.config.max_bytes:,}."
            )
        if chunk.splits_character:
            message += "; the cut lands inside a multi-byte character, corrupting it"
        findings.append(
            _finding(
                "AD001",
                severity,
                path=rel,
                line=0,
                message=message,
                hint=hint,
                context={
                    "lost_bytes": chunk.lost_bytes,
                    "lost_chars": chunk.lost_chars,
                    "included_bytes": chunk.included_bytes,
                    "dropped": chunk.dropped,
                    "splits_character": chunk.splits_character,
                    "affected_directories": targets,
                },
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# AD002: broken path references
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

# Extensions that make a bare filename recognisable as a file rather than prose.
_PATH_EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".rb",
    ".java",
    ".kt",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cs",
    ".swift",
    ".sh",
    ".bash",
    ".ps1",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".lock",
    ".sql",
    ".proto",
    ".graphql",
    ".css",
    ".scss",
    ".html",
)

# A token is only treated as a repository path when it names a directory
# component or a recognisable filename, and nothing suggests a URL, shell
# fragment or placeholder.
_REJECT = re.compile(
    r"""(
        ^[a-zA-Z][a-zA-Z0-9+.-]*://   # URL
      | ^[~$]                          # home or variable expansion
      | ^-                             # command-line flag
      | [\s<>|&;{}()\[\]$*?!"'\\]      # shell metacharacters, globs, placeholders
      | ^@                             # package scope, not a path
      | =                              # an assignment, such as an environment variable
      | ^\d+$                          # bare number
    )""",
    re.VERBOSE,
)


def _looks_like_path(token: str) -> bool:
    token = token.strip()
    if not token or len(token) > 200 or _REJECT.search(token):
        return False
    if token.startswith("/"):
        # Absolute paths refer to the machine, not the repository.
        return False
    if _TEMPLATE.search(token):
        # A filename template such as versions/vYYYY_MM_DD.py names a shape, not a file.
        return False
    if "/" in token:
        return True
    if token.lower() in _PATH_EXTENSIONS:
        # A bare extension names a kind of file, not one in particular.
        return False
    # A bare filename says nothing about location, so it is checked differently --
    # see check_broken_path_reference -- but it still has to look like a file.
    return token.lower().endswith(_PATH_EXTENSIONS)


#: Placeholders that mark a filename template rather than a real file.
_TEMPLATE = re.compile(r"YYYY|XXX|NNN|_MM_|_DD_")


def _normalise(token: str) -> str:
    token = token.strip().rstrip(".,:;").split("#", 1)[0]
    while token.startswith("./"):
        token = token[2:]
    return token.rstrip("/")


def _inside_repository(path: Path, root: Path) -> Path | None:
    """Resolve ``path`` only when it remains inside the checked repository."""
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _iter_candidates(file: InstructionFile) -> Iterator[tuple[str, int]]:
    """Yield ``(token, line)`` for every path-like reference outside code blocks.

    Fenced blocks are skipped wholesale: they hold commands and sample output,
    where a path may legitimately describe a file the project does not have.
    """
    in_fence = False
    for lineno, line in enumerate(file.text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _INLINE_CODE.finditer(line):
            yield match.group(1), lineno
        for match in _MD_LINK.finditer(line):
            target = match.group(1).split("#", 1)[0]
            if target:
                yield target, lineno


def check_broken_path_reference(ctx: Context, severity: Severity) -> list[Finding]:
    """Report referenced repository paths that do not exist.

    References are resolved relative to the file's own directory first and the
    repository root second, because instruction files use both conventions.
    """
    findings: list[Finding] = []
    for file in ctx.files:
        base = ctx.root if file.directory == "." else ctx.root / file.directory
        seen = set()
        for raw_token, lineno in _iter_candidates(file):
            if not _looks_like_path(raw_token):
                continue
            token = _normalise(raw_token)
            if not token or (token, lineno) in seen:
                continue
            seen.add((token, lineno))
            if any(fnmatch.fnmatch(token, pattern) for pattern in ctx.config.ignore_paths):
                continue
            if set(token.split("/")) & set(ctx.config.exclude):
                # Excluded directories hold build output and dependencies, which are
                # absent from a clean checkout. Naming one is normal, not a mistake.
                continue
            candidates = [
                candidate
                for candidate in (
                    _inside_repository(base / token, ctx.root),
                    _inside_repository(ctx.root / token, ctx.root),
                )
                if candidate is not None
            ]
            if not candidates:
                continue
            if any(candidate.exists() for candidate in candidates):
                continue
            if "/" in token:
                # Report only when the containing directory exists. A reference into
                # a directory that is not there describes something other than a file
                # in this repository -- an API route, another project, a planned
                # layout -- and guessing at those is how a checker earns a reputation
                # for noise.
                if not any(candidate.parent.is_dir() for candidate in candidates):
                    continue
            elif ctx.name_exists_anywhere(token):
                # Shorthand for something that does live somewhere in the tree.
                continue
            findings.append(
                _finding(
                    "AD002",
                    severity,
                    path=file.rel,
                    line=lineno,
                    message=f"references `{token}`, which does not exist",
                    hint="Update the path, or add it to ignore_paths if it is created at runtime.",
                    context={"reference": token},
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# AD004: empty instruction files
# --------------------------------------------------------------------------- #

_PLACEHOLDER = re.compile(r"^\s*(tbd|todo|wip|coming soon|n/?a|\.\.\.)\s*$", re.IGNORECASE)


def check_empty_instructions(ctx: Context, severity: Severity) -> list[Finding]:
    """Report files with no usable content.

    The loader skips a blank file without spending budget, so this is not a
    truncation risk -- it is a file that looks like guidance and provides none.
    """
    findings: list[Finding] = []
    for file in ctx.files:
        body = [
            line.strip()
            for line in file.text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        meaningful = [line for line in body if not _PLACEHOLDER.match(line)]
        if meaningful:
            continue
        reason = "is empty" if not body else "contains only placeholder text"
        findings.append(
            _finding(
                "AD004",
                severity,
                path=file.rel,
                line=0,
                message=f"{reason}, so it gives the agent no guidance",
                hint="Add content or delete the file.",
            )
        )
    return findings


CHECKS: dict[str, Callable[[Context, Severity], list[Finding]]] = {
    "AD001": check_lost_instructions,
    "AD002": check_broken_path_reference,
    "AD004": check_empty_instructions,
}


def build_context(root: Path, config: Config, files: Sequence[InstructionFile]) -> Context:
    """Precompute every working-directory plan without rereading instruction files."""
    plans: dict[str, LoadPlan] = {}
    files_by_directory = {file.directory: file for file in files}
    excluded = set(config.exclude)
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in excluded)
        target = Path(dirpath)
        relative = target.relative_to(root).as_posix() or "."
        if relative == ".":
            chunks: list[LoadedChunk] = []
        else:
            parent = Path(relative).parent.as_posix()
            chunks = list(plans[parent].chunks)

        file = files_by_directory.get(relative)
        if file is not None:
            loaded = sum(chunk.included_bytes for chunk in chunks)
            remaining = max(0, config.max_bytes - loaded)
            chunks.append(load_instruction_chunk(file, remaining))

        plans[relative] = LoadPlan(
            target=relative,
            chunks=chunks,
            max_bytes=config.max_bytes,
        )
    return Context(root=root, config=config, files=list(files), plans=plans)


def run_rules(ctx: Context, only: Sequence[str] | None = None) -> list[Finding]:
    """Run every enabled rule and return findings, most severe first."""
    selected = [r.upper() for r in only] if only else list(RULES)
    findings: list[Finding] = []
    for rule_id in selected:
        spec = RULES.get(rule_id)
        if spec is None:
            raise KeyError(rule_id)
        severity = ctx.config.severity_for(rule_id, spec.default_severity)
        if severity is None:
            continue
        findings.extend(CHECKS[rule_id](ctx, severity))
    findings.sort(key=lambda f: f.sort_key())
    return findings
