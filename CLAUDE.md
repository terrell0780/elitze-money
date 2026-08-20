# Elitze Money Engine

See [AGENTS.md](./AGENTS.md) for the full agent configuration: vendored skills, the
`/spec → /plan → /build → /test → /review → /ship` lifecycle, subagents, and the project
rules that override skill defaults.

Claude Code reads this repo's skills, commands, and subagents from `.claude/`, which symlinks
into `.agents/`. Edit files under `.agents/` — never the symlinks.

**Before any change that spends money, touches production, or cannot be reverted:** read the
Safety Boundary and Principles sections of `README.md` and invoke the
`doubt-driven-development` skill.
