"""Core data types shared by discovery, rules and reporters."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class Severity(enum.Enum):
    """How badly a finding affects the agent's behaviour."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 3, "warning": 2, "info": 1}[self.value]

    @classmethod
    def parse(cls, value: str) -> Severity:
        try:
            return cls(value.strip().lower())
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"unknown severity: {value!r}") from exc


@dataclass(frozen=True)
class InstructionFile:
    """A single AGENTS.md (or AGENTS.override.md) on disk."""

    path: Path
    """Absolute path to the file."""

    rel: str
    """Repo-relative POSIX path, used in every user-facing message."""

    data: bytes
    """Raw bytes. The budget is measured in bytes, so this is the source of truth."""

    text: str
    """Contents decoded leniently, mirroring the agent's own lossy decode."""

    known_size: int | None = None
    """File size obtained without reading contents after the loader budget is spent."""

    unread: bool = False
    """Whether contents were intentionally left unread because the loader would skip them."""

    content_known: bool = True
    """Whether ``data`` and ``text`` contain the file's actual contents.

    A size-only placeholder is used when reproducing the loader after its budget
    is exhausted.  Keeping this separate from ``unread`` matters to repository
    checks: discovery may already know the contents even though the simulated
    loader would not read that file.
    """

    @property
    def raw_size(self) -> int:
        """Size in bytes, which is what the byte budget is measured in."""
        return self.known_size if self.known_size is not None else len(self.data)

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def bytes_per_char(self) -> float:
        """Above 1.0 for non-ASCII text; ~3.0 for Japanese, Chinese and Korean.

        A CJK instruction file exhausts the same byte budget roughly three times
        faster than an English one of equal length.
        """
        return self.raw_size / self.char_count if self.char_count else 0.0

    @property
    def is_ascii(self) -> bool:
        """ASCII text spends one byte per character, so bytes and characters agree."""
        return self.raw_size == self.char_count

    @property
    def directory(self) -> str:
        """Repo-relative POSIX directory this file governs (``"."`` at the root)."""
        parent = self.rel.rsplit("/", 1)[0] if "/" in self.rel else ""
        return parent or "."


@dataclass(frozen=True)
class LoadedChunk:
    """One instruction file's fate inside a byte budget."""

    file: InstructionFile
    included_bytes: int
    """How many bytes of this file survive the budget."""

    blank: bool = False
    """The file holds no visible text, so the loader skips it without spending budget.

    A blank file is not *lost* -- there was nothing in it to lose -- which is why
    it must never be conflated with a dropped one.
    """

    skipped_after_cut: bool = False
    """The retained prefix was blank, so the loader skipped this file without
    consuming budget even though the full file contains content beyond the cut.
    """

    @property
    def dropped(self) -> bool:
        """The budget ran out before this file: the agent never sees any of it."""
        return (
            not self.blank
            and not self.skipped_after_cut
            and self.included_bytes == 0
            and self.file.raw_size > 0
        )

    @property
    def truncated(self) -> bool:
        """The budget ran out part-way through this file."""
        return 0 < self.included_bytes < self.file.raw_size

    @property
    def lost_bytes(self) -> int:
        if self.blank:
            return 0
        return max(0, self.file.raw_size - self.included_bytes)

    @property
    def splits_character(self) -> bool:
        """The cut lands inside a multi-byte character, corrupting it.

        The agent truncates raw bytes and then decodes leniently, so a cut in the
        middle of a UTF-8 sequence turns that character into U+FFFD. This only
        happens with non-ASCII text, which makes it a CJK-specific hazard.
        """
        if not self.truncated:
            return False
        kept = self.file.data[: self.included_bytes]
        try:
            kept.decode("utf-8")
        except UnicodeDecodeError:
            return True
        return False

    @property
    def lost_chars(self) -> int:
        """Known characters lost, or zero when the contents were not inspected."""
        if not self.truncated:
            return self.file.char_count if self.dropped else 0
        kept = self.file.data[: self.included_bytes].decode("utf-8", errors="ignore")
        return max(0, self.file.char_count - len(kept))

    @property
    def lost_chars_known(self) -> bool:
        """Whether ``lost_chars`` is an exact count rather than an unknown value."""
        return self.file.content_known


@dataclass(frozen=True)
class LoadPlan:
    """What an agent loads when it is asked to work in ``target``.

    Files appear in the order the agent concatenates them: repository root first,
    the directory being worked in last. The budget is consumed in that same order,
    which is why the *most specific* instructions are the first ones to be lost.
    """

    target: str
    """Repo-relative POSIX directory the plan was computed for."""

    chunks: list[LoadedChunk]
    max_bytes: int

    @property
    def requested_bytes(self) -> int:
        return sum(chunk.file.raw_size for chunk in self.chunks)

    @property
    def loaded_bytes(self) -> int:
        return sum(chunk.included_bytes for chunk in self.chunks)

    @property
    def lost_bytes(self) -> int:
        return sum(chunk.lost_bytes for chunk in self.chunks)

    @property
    def over_budget(self) -> bool:
        return self.lost_bytes > 0

    @property
    def headroom(self) -> int:
        """Bytes that may still be added before anything is silently dropped."""
        if self.over_budget:
            return 0
        return max(0, self.max_bytes - self.loaded_bytes)


@dataclass(frozen=True)
class Finding:
    """A single problem to report."""

    rule: str
    """Stable rule id, e.g. ``AD001``."""

    name: str
    """Human-readable rule slug, e.g. ``truncated-instructions``."""

    severity: Severity
    path: str
    """Repo-relative POSIX path the finding is anchored to."""

    line: int
    """1-indexed line, or 0 when the finding is about the file as a whole."""

    message: str
    hint: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path

    def sort_key(self) -> tuple[int, str, int, str]:
        return (-self.severity.rank, self.path, self.line, self.rule)
