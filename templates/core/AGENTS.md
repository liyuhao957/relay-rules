# Relay Rules

## Load project context on demand

- Before substantive work, read `.relay/index.md`; it is the routing map, not a second full handbook.
- If its status is `pending`, follow `.relay/workflows/adapt.md` before relying on project-specific rules.
- Load only the files whose task or path trigger matches the current work. Do not read every `.relay` file up front.
- Current code, configuration, tests, and tool output beat project notes. Repair stale rules when evidence disproves them.

## Work from evidence

- Follow the current user request over older notes or summaries.
- Inspect the relevant code, configuration, tests, and current tool output before deciding.
- Check the working tree before editing; preserve unrelated user changes.

## Keep the change small

- Solve only the requested outcome and match the project's existing style.
- Prefer a direct change over new layers, dependencies, configuration, or generated process.
- Ask only when the choice changes product direction, data safety, irreversible actions, cost, release, or external users.

## Close the loop

- Trace the affected user path, including state, errors, and cleanup where relevant.
- Run the smallest test or build that proves the changed behavior.
- Run broader tests only for shared infrastructure, cross-module changes, releases, explicit user requests, or when targeted checks are insufficient.
- Do not weaken tests, security, or validation to make a check pass.
- Before finishing, report what changed, what was actually verified, and any remaining risk or unverified area.

## Maintain project rules

- When a change alters a durable command, boundary, convention, workflow, or risk, follow `.relay/workflows/maintain.md` and update only the affected project context.
- Keep rules short and reusable. Point to an existing source of truth instead of copying it, and do not save one-off task notes as permanent rules.

## External actions

- Confirm the exact scope before publishing, deploying, releasing, deleting, sending, charging, or changing production state.
- Never expose secrets or claim live state without checking it with the real tool.
