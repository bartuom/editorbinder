# Security Policy

## Supported Versions

Security fixes are handled on the current `main` branch and the latest GitHub
Release.

## Reporting A Vulnerability

Please do not report security issues in public GitHub Issues.

Email the maintainer with:

- the affected version or commit,
- reproduction steps,
- expected impact,
- whether the issue involves generated/imported scripts, packaging, or local
  file handling.

EditorBinder does not execute scripts automatically, but imported scripts can
contain arbitrary Python intended for Unreal Engine's Python Console. Always
review scripts before running them in a project.
