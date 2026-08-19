# Security policy

## Supported versions

Only the latest release receives security fixes. skillferry is currently in
alpha (0.x); treat it accordingly.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Report it to the
maintainer privately (the repository owner's contact shown on the GitHub
profile / PyPI metadata) with:

- affected version(s) and platform,
- a minimal reproduction (fake homes only — never real credentials),
- observed impact and, if possible, a proposed fix.

You will receive an acknowledgement within 7 days and a status update
within 30 days. After a fix is released, reports may be credited with the
reporter's consent.

## What we consider a vulnerability

- Any path where a resolved secret value can appear in `plan --json`,
  `doctor --json`, logs, `export --shareable`, or the local state ledger.
- Any path where `apply` silently overwrites content it does not own.
- Any path where the schema admits a literal secret into a workspace
  definition.
- Any path where a workspace can escape the managed roots (symlinks, path
  traversal) or manage `[protect]`-declared state.

## What is not a vulnerability

- A malicious *workspace* pointing MCP at arbitrary local commands: the
  workspace is user-authored input, like a shell script; `plan` preview and
  the portability grades are the review surface (see THREAT_MODEL).
- Local attackers with the user's account: skillferry is not a secret
  manager and does not re-encrypt secrets at rest.
- Agent-side behavior (whether an agent actually loads a rendered file) is
  a product-compatibility issue, not a skillferry vulnerability.

## Disclosure and fixes

Fixes ship as patch releases with a CHANGELOG entry, a regression test, and
— for anything touching secrets — an updated threat-model section.
