---
name: relay-review
description: Review code or a diff for concrete bugs, regressions, risks, and missing verification.
---

# Relay Review

1. Inspect the actual diff and current surrounding code; do not trust a summary as proof.
2. Trace each changed behavior through callers, state, errors, cleanup, and user-visible effects.
3. Prioritize findings by impact and likelihood.
4. Ground every finding in a file and line, with a concrete failure scenario.
5. Distinguish verified defects from open questions and test gaps.
6. Lead with findings; say clearly when none were found.
