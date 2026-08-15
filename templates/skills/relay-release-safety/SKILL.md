---
name: relay-release-safety
description: Prepare or perform release and production work with explicit scope and live verification.
---

# Relay Release Safety

1. Confirm the target, environment, version, audience, and authorized external action.
2. Inspect the real working tree and release configuration.
3. Verify credentials and remote state without printing secrets.
4. Run the required build, tests, signing, or packaging checks and retain their actual results.
5. Perform only the approved external action.
6. Verify the resulting live state and report rollback options and remaining risk.
