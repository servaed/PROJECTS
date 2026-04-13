---
name: session-history
description: Maintain progress tracking across Claude Code sessions — create timestamped work logs, record decisions, and track next steps.
---

# Skill: Session History

## When to Create a Session Log

Create a session log after any work session that:
- Changes more than 2 files
- Makes an architectural decision
- Adds or removes a major component
- Completes a phase from the roadmap

## File Naming

```
.claude/history/sessions/YYYY-MM-DD-HHMM-<topic-slug>.md
.claude/history/decisions/YYYY-MM-DD-<decision-slug>.md
.claude/history/changelogs/YYYY-MM-DD.md
.claude/history/prompts/<prompt-name>.md
```

Use actual timestamps. Use lowercase-hyphenated slugs for topic names.

## Creating a Session Log

Copy the template from `.claude/skills/session-history/templates/session-log.md` and fill in:
- Objective of the session
- List of files changed
- Decisions made during the session
- Unresolved issues
- Concrete next steps

## Creating a Decision Log

Copy the template from `.claude/skills/session-history/templates/decision-log.md` and fill in:
- Context that led to the decision
- Options considered
- Chosen option and rationale
- Impact on the codebase or architecture

## Prompt Versioning

Store important prompts under `.claude/history/prompts/` with a descriptive filename.
Include the date they were created or last validated.

## Querying History

To review prior decisions:
```bash
ls .claude/history/decisions/
cat .claude/history/decisions/<file>.md
```
