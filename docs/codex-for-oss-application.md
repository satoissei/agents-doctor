# Codex for Open Source application kit

This is a public, privacy-safe preparation sheet. Do **not** commit your legal name,
ChatGPT email address, OpenAI Organization ID, or non-public usage data here.

The [Codex for Open Source application](https://openai.com/form/codex-for-oss/)
reviews repository usage, ecosystem importance, active maintenance, and maintainer
role. A new project must not invent adoption metrics; apply only with facts that can
be verified from the public repository or a trustworthy public metric source.

## Current eligibility assessment

As of release `v0.2.3`, the repository provides public source, an OSI-approved
license, installation and usage examples, contribution and security processes,
issue and pull-request templates, a versioned changelog, tagged releases, automated
tests across supported Python versions and operating systems, dependency and static
security checks, PyPI and GitHub Marketplace distribution, and a maintainer release
playbook.

The main unresolved selection risk is **meaningful usage, broad adoption, or clear
ecosystem importance**. The repository does not currently claim external users,
downloads, downstream integrations, or other adoption evidence. A second release and
good maintenance process demonstrate continued maintenance, but do not by themselves
prove ecosystem impact. Before applying, add only independently verifiable evidence
such as public downstream use, package downloads, substantive third-party issues or
pull requests, or a documented dependency relationship. If none exists, submit the
early-stage wording below and accept that the application may not be competitive yet.
Maintainer verification downloads and maintainer-created examples are not external
adoption; follow the public evidence policy in [adoption.md](adoption.md).

## Submission checklist

- GitHub profile and repository are public.
- You are the primary maintainer or a core maintainer with write access.
- The default branch, tests, release notes, security policy, and support path are public.
- You have collected real stars, downloads, downstream use, or other ecosystem evidence
  if you cite it.
- Your OpenAI Organization ID and ChatGPT-account email are entered only in the form.
- No private paths, user data, API keys, or internal usage data are included.
- Each free-text response fits the form's stated 500-character limit.

## Recommended selections

- **Role:** select **Primary maintainer** only if you own the release and maintenance
  decisions; otherwise select **Core maintainer**.
- **Interested in:** select **API credits for my project** for issue triage, review,
  documentation, and release workflows.
- Select **Codex Security** only when there is a concrete security-review workflow
  for this repository and you are authorized to administer it.

## Paste-ready English responses

### Why does this repository qualify?

Use this early-stage version only while it remains true; replace it with verified
adoption data when it exists.

```text
agents-doctor is a public MIT-licensed Python CLI, pre-commit hook, and GitHub Action that detects AGENTS.md instructions silently lost to coding-agent byte budgets. I am the primary maintainer. The project is early-stage, so I do not claim adoption metrics that I cannot verify. I maintain public tests, CI across Python 3.9-3.13, release automation, a security policy, and an offline-by-design privacy boundary.
```

### How will you use API credits for your project?

```text
I would use API credits for maintainer workflows: triaging sanitized issues, reviewing pull requests against the documented loader model, drafting release notes from verified changes, and improving tests and documentation. A maintainer will review all outputs. Credits would be used only for this repository and never to scan or review systems or code that I do not own or administer.
```

### Anything else we should know?

```text
I am the repository owner and primary maintainer with write access. The project is deliberately transparent about its early-stage status and does not claim stars, downloads, or usage it cannot verify. It provides public contribution, security, privacy, governance, release, and compatibility documentation so users and contributors can assess both the tool and its maintenance practices.
```

Before submitting, re-check each sentence against the current public repository and
the [program terms](https://learn.chatgpt.com/docs/codex-for-oss-terms). The
program may change, and selection is not guaranteed.
