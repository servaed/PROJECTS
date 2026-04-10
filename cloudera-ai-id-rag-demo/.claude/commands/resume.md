# /resume — Resume a Work Session

When resuming work on this project, run the following steps:

1. Read `CLAUDE.md` for project conventions and safety rules.
2. Check `.claude/history/sessions/` for the most recent session log.
3. Check `.claude/history/decisions/` for any pending architectural decisions.
4. Review the "Next Steps" section of the latest session log.
5. Confirm the `.env` file is configured before running the app.

## Quick Status Commands

```bash
# Check which files have changed since last commit
git status

# Show recent commit history
git log --oneline -10

# Verify the vector store exists
ls data/vector_store/

# Run tests to confirm nothing is broken
pytest tests/ -v
```
