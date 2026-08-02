# Adoption and evidence policy

`agents-doctor` is offline and sends no telemetry, so maintainers cannot infer real
usage from the CLI. Adoption evidence is collected only from public integrations,
public reports, package and release statistics, and information users deliberately
choose to share.

## Try it without installing

From the repository you want to check, run the tagged release in a temporary pipx
environment:

```console
pipx run --spec "git+https://github.com/satoissei/agents-doctor.git@v0.2.1" agents-doctor check
```

The command reads the checked-out repository locally. Review the privacy and symlink
boundary in [PRIVACY.md](../PRIVACY.md) before using an untrusted checkout.

## Report real-world use

If you use or evaluate the project, submit the
[public adoption report](https://github.com/satoissei/agents-doctor/issues/new?template=adoption_report.yml).
A public repository link is the strongest evidence, but it is optional. Reports about
failed evaluations are useful too: adoption work must improve the product rather than
filter out negative outcomes.

Do not post private repositories, credentials, customer names, full instruction files,
or other non-public data. Explicit consent in the issue form is required before a
repository or report is quoted in an application, adopters list, or project update.

## What maintainers may count

Evidence must be independently verifiable and described with its source and date.
Acceptable signals include:

- a public third-party repository using the GitHub Action or pre-commit hook;
- a substantive issue or pull request from someone outside the maintainer account;
- package-index or release download statistics with maintainer verification traffic
  excluded where it can be identified; and
- a public project that documents agents-doctor as part of its maintenance workflow.

Maintainer-created examples, automated checks, self-downloads, stars from related
accounts, private traffic statistics, and unverified statements are not external
adoption. The project will publish an adopters list only after at least one adopter
explicitly consents to attribution.
