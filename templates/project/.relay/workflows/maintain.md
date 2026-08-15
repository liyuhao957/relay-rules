# Maintain Project Rules

Use this workflow when code changes a durable project fact, when a route becomes stale, or when the user asks to review the rules themselves. Ordinary one-off implementation details do not need a rule update.

## Update

1. Inspect the current diff and the evidence behind the affected rule.
2. Update only the matching entry in `.relay/index.md`, `.relay/project.md`, or the relevant `.relay/rules/*.md` file.
3. Add a rule only when it will guide multiple future tasks and has a clear task or path trigger.
4. Prefer a pointer to an authoritative project document over duplicated content.
5. Remove or rewrite stale, conflicting, overly broad, or ignored rules. Keep the index short enough to scan before every substantive task.

## Preserve

- Do not edit Relay's managed block markers or `.relay/workflows/*`.
- Do not turn a current file layout into a permanent constraint unless the project intentionally guarantees it.
- Do not record secrets, credentials, private machine paths, transient failures, chat history, or unverified production state.

## Verify

- Check that every route names a real file or an intentionally unresolved item.
- Re-run or relocate changed commands before calling them verified.
- Run the Relay installer's doctor after structural rule changes.
