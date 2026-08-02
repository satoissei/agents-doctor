# Codex compatibility

## Supported reference

Version `0.2.1` models the instruction-loading behaviour read from
[`openai/codex` commit `2b5bdcf`](https://github.com/openai/codex/tree/2b5bdcf67547860f2e5c5a605009a70026796b2b).
It is a behavioural compatibility target, not a claim that this project embeds or
controls Codex.

The covered behaviour is:

1. locate the nearest project-root marker (`.git` by default);
2. visit directories from root to the working directory;
3. choose `AGENTS.override.md`, `AGENTS.md`, then configured fallback filenames;
4. consume `project_doc_max_bytes` in raw-byte order; and
5. skip a retained prefix that is blank without spending budget.

The tool follows instruction-file symlinks because that is part of the modeled
behaviour. It does not claim compatibility with undocumented agent behaviour,
third-party instruction formats, or future Codex releases.

## Maintenance procedure

When upstream changes are suspected or reported:

1. identify the upstream commit, release, and relevant source or documentation;
2. create a minimal fixture demonstrating the old and new behaviour;
3. update `discovery.py`, its docstring, and focused tests together;
4. update this file, `README.md`, and the changelog with the new reference; and
5. publish a tagged release after the full quality gate passes.

Reports that demonstrate a divergence with a sanitized reproduction are the highest
priority maintenance input. Do not include private instruction contents in the report.
