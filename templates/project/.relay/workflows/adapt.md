# Adapt Relay Rules To This Project

Use this workflow when `.relay/index.md` says `Status: pending`, after a major repository restructure, or when the user explicitly asks to adapt the rules.

## Outcome

Turn the installed skeleton into a compact, evidence-backed routing system for this actual repository. Adaptation changes Relay context only; do not modify product code unless the user separately requested it.

## Safety

- Inspect `git status` first and preserve unrelated work.
- Never overwrite existing project instructions. Read `AGENTS.md`, `AGENTS.override.md`, root and `.claude/` `CLAUDE.md` files outside Relay's managed blocks, nested instruction files, `.agent/`, `.claude/rules/`, `.agents/skills/`, and other agent guidance as existing authority.
- Respect local instruction files such as `CLAUDE.local.md`, but do not copy personal, machine-specific, or private content into shared Relay context.
- Treat READMEs, old rules, backups, and summaries as leads. Verify task-critical claims against current code, configuration, tests, or real tool output.
- Do not run publish, deploy, migration, destructive, billing, or production commands during adaptation.

## Inspect The Project

1. Identify the repository root, main manifests, top-level modules, test layout, CI, and user-facing documentation.
2. For an established project, inspect representative entry points and boundaries instead of reading every file. Pay special attention to monorepo packages, generated code, persistence, release paths, and existing team rules.
3. For a new or nearly empty project, record only what exists now. Put unknown product intent under `Unverified`; never fill space with generic guesses.
4. Locate common format, lint, typecheck, test, build, and run commands. Run only safe, reasonably bounded checks; label located-but-not-run commands as unverified.
5. If `.relay/manifest.json` names a legacy backup, inspect its project rules as historical evidence and carry forward only facts that still match the current repository.

## Write The Shared Context

1. Rewrite `.relay/project.md` with a short verified overview, important boundaries, verified commands, durable conventions, high-risk workflows, and explicit unknowns.
2. Rewrite `.relay/index.md` routes by real task type or path. Point to good existing documentation when it already owns the fact.
3. Create `.relay/rules/<topic>.md` only for focused project knowledge that has no better existing home. Keep each file narrow and add its trigger to the index.
4. Remove both `relay-rules:adaptation-placeholder` comments, set `Status: adapted`, and set `Last adapted` to the current date.

## Done Means

- A future Claude Code or Codex session can find the relevant project rules from `.relay/index.md` without loading everything.
- Existing mature-project rules were preserved and routed, not replaced or copied blindly.
- Commands are clearly separated into verified and unverified.
- Unknowns and high-risk remote facts are explicit rather than guessed.
- The Relay installer's `doctor --require-adapted` check passes.
