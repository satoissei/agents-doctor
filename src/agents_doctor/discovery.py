"""Reproduction of the loader that assembles AGENTS.md instructions.

This module is a deliberate port of ``codex-rs/core/src/agents_md.rs`` from
openai/codex (read at commit ``2b5bdcf``). Every rule in this package depends on
it being faithful, so the behaviour it mirrors is spelled out here:

1. The project root is the nearest ancestor of the working directory holding a
   root marker (``.git`` by default). Without one, only the working directory is
   considered.
2. Directories from the project root down to the working directory are visited in
   that order, so *root-most instructions are concatenated first*.
3. Each directory contributes at most one file: ``AGENTS.override.md``, then
   ``AGENTS.md``, then any configured fallback filenames.
4. Files are appended until ``project_doc_max_bytes`` is exhausted. A file that
   does not fit is cut **at a byte offset**; once nothing remains, the loop stops
   and later files are never read at all.
5. A file that is blank after cutting is skipped without consuming budget.

Consequence, and the reason this package exists: the working directory's own
instructions are concatenated *last*, so they are the first to be lost.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path

from agents_doctor.config import Config, _validate_local_names
from agents_doctor.models import InstructionFile, LoadedChunk, LoadPlan

#: Marker identifying the project root, matching codex's ``DEFAULT_PROJECT_ROOT_MARKERS``.
DEFAULT_ROOT_MARKERS = (".git",)

#: Preferred per-directory filename, matching ``LOCAL_AGENTS_MD_FILENAME``.
OVERRIDE_FILENAME = "AGENTS.override.md"

#: Default per-directory filename, matching ``DEFAULT_AGENTS_MD_FILENAME``.
DEFAULT_FILENAME = "AGENTS.md"


def find_project_root(start: Path, markers: Sequence[str] = DEFAULT_ROOT_MARKERS) -> Path:
    """Return the nearest ancestor of ``start`` containing a root marker.

    Falls back to ``start`` itself when no marker is found, which mirrors the
    loader's behaviour of considering only the working directory.
    """
    start = start.resolve()
    markers = _validate_local_names(list(markers), "root markers")
    if not markers:
        return start
    for candidate in (start, *start.parents):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return start


def candidate_filenames(config: Config) -> list[str]:
    """Filenames tried in a single directory, most preferred first."""
    names = [OVERRIDE_FILENAME, DEFAULT_FILENAME]
    for extra in _validate_local_names(config.fallback_filenames, "fallback_filenames"):
        if extra and extra not in names:
            names.append(extra)
    return names


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # pragma: no cover - defensive, target is always inside root
        return path.as_posix()


def read_instruction_file(path: Path, root: Path) -> InstructionFile:
    """Read one instruction file as raw bytes plus a leniently decoded view."""
    data = path.read_bytes()
    return InstructionFile(
        path=path,
        rel=_relative(path, root),
        data=data,
        # The loader decodes with from_utf8_lossy, so invalid sequences survive as
        # U+FFFD rather than raising. Mirror that instead of failing the run.
        text=data.decode("utf-8", errors="replace"),
    )


def instruction_path_in(directory: Path, config: Config) -> Path | None:
    """Return the selected instruction path without reading its contents.

    Symlinks are followed, matching the loader. This matters in practice: several
    well-known repositories ship ``AGENTS.md`` as a symlink to ``CLAUDE.md`` or
    similar.
    """
    for name in candidate_filenames(config):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def instruction_file_in(directory: Path, root: Path, config: Config) -> InstructionFile | None:
    """Return the selected instruction file with its contents read."""
    path = instruction_path_in(directory, config)
    return read_instruction_file(path, root) if path is not None else None


def unread_instruction_file(path: Path, root: Path) -> InstructionFile:
    """Represent a file the loader discovered but would not read after budget exhaustion."""
    size = path.stat().st_size
    return InstructionFile(
        path=path,
        rel=_relative(path, root),
        data=b"",
        text="",
        known_size=size,
        unread=True,
        # A zero-byte file is provably blank without reading it.
        content_known=size == 0,
    )


def load_instruction_chunk(file: InstructionFile, remaining: int) -> LoadedChunk:
    """Apply the loader's byte-budget rules to one already selected file.

    Repository-wide checks discover file contents once and reuse them here.  The
    ``unread`` flag still records that the real loader stops reading after the
    budget reaches zero; ``content_known`` records whether *the check* knows the
    contents from its earlier repository scan.
    """
    if remaining == 0:
        return LoadedChunk(
            file=replace(file, unread=True),
            included_bytes=0,
            blank=file.content_known and not file.text.strip(),
        )

    # A wholly blank file is a skip, not a loss: there was nothing in it for
    # the model to miss, and the loader spends no budget on it.
    is_blank = file.content_known and not file.text.strip()
    included = min(file.raw_size, remaining)
    kept = file.data[:included]
    if file.content_known and not kept.decode("utf-8", errors="replace").strip():
        # The loader drops content that is blank *after* the cut without
        # consuming budget. When the full file had text beyond the cut, that
        # text is genuinely lost, but this is distinct from a file dropped
        # after the budget was already spent: later files can still load.
        return LoadedChunk(
            file=file,
            included_bytes=0,
            blank=is_blank,
            skipped_after_cut=not is_blank,
        )
    return LoadedChunk(file=file, included_bytes=included)


def chain_directories(target: Path, root: Path) -> list[Path]:
    """Directories from ``root`` down to ``target``, root first."""
    target = target.resolve()
    root = root.resolve()
    dirs: list[Path] = []
    cursor = target
    while True:
        dirs.append(cursor)
        if cursor == root:
            break
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    dirs.reverse()
    return dirs


def build_load_plan(target: Path, root: Path, config: Config) -> LoadPlan:
    """Compute exactly what an agent loads when working in ``target``.

    The budget arithmetic mirrors the loader step for step, including the two
    details that surprise people: a file is cut at a raw byte offset, and a file
    that is blank after cutting is skipped without consuming any budget.
    """
    remaining = config.max_bytes
    chunks: list[LoadedChunk] = []
    for directory in chain_directories(target, root):
        path = instruction_path_in(directory, config)
        if path is None:
            continue
        if remaining == 0:
            chunks.append(load_instruction_chunk(unread_instruction_file(path, root), remaining))
            continue
        file = read_instruction_file(path, root)
        chunk = load_instruction_chunk(file, remaining)
        chunks.append(chunk)
        remaining -= chunk.included_bytes

    return LoadPlan(
        target=_relative(target, root) or ".",
        chunks=chunks,
        max_bytes=config.max_bytes,
    )


def _is_excluded(name: str, exclude: Iterable[str]) -> bool:
    return name in set(exclude)


def discover_instruction_files(root: Path, config: Config) -> list[InstructionFile]:
    """Every instruction file in the repository, in stable path order.

    Only the file a directory would actually contribute is returned, so a
    directory holding both ``AGENTS.override.md`` and ``AGENTS.md`` yields the
    override alone -- the same choice the loader makes.
    """
    found: list[InstructionFile] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _is_excluded(d, config.exclude))
        file = instruction_file_in(Path(dirpath), root, config)
        if file is not None:
            found.append(file)
    found.sort(key=lambda f: f.rel)
    return found
