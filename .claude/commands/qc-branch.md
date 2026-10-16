---
description: Audit the current branch before pushing - review-file lint, packets, the CI checks, and a sample of sources re-opened
argument-hint: "[run name and lane, e.g. 2026-10-16-verify review; blank: the newest .packets run, lane review]"
---

Audit the current branch with the `qc-auditor` agent. Scope: $ARGUMENTS (a run name under `.packets/` and a lane, `review` for research branches or `prose` for copy-editing branches; when blank, the newest directory under `.packets/` and lane `review`).

1. The auditor audits the committed HEAD in this checkout and refuses to start on uncommitted changes, because its checks regenerate files it then restores. `git status --short` must show no change to a tracked file; if it does, commit or restore it and say which.
2. Start the `qc-auditor` with the run name, the lane and the report path `.packets/<run>/qc.md`. It changes nothing it audits.
3. Relay its verdict and findings table. For each BLOCKER, say which agent or step should fix it (a reader re-reads, the `record-editor` corrects a row, the `copy-editor` fixes prose), do that, commit, and audit again. Push only on PASS or PASS WITH WARNINGS, and carry the warnings into the pull request description.
