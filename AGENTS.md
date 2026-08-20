# Elitze Money Engine — Agent Instructions

Production-oriented autonomous revenue experimentation platform. See `README.md` for the
architecture, core loop, data model, and safety boundary. **Read the Safety Boundary section
of `README.md` before executing anything that spends money or touches production.**

## Agent Skills

This repo vendors [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (MIT).

- `.agents/skills/` — 24 skills, the source of truth
- `.agents/commands/` — 8 lifecycle commands
- `.agents/subagents/` — 4 specialist reviewer roles
- `.claude/{skills,commands,agents}/` — symlinks into the above for Claude Code
- `skills-lock.json` — pins the installed skill versions by content hash

A skill is a `SKILL.md` with `name` + `description` frontmatter. Match the task against the
descriptions, then read the full skill body before acting. Skills are instructions, not code.

### Lifecycle

```
DEFINE     PLAN      BUILD     VERIFY    REVIEW     SHIP
/spec  →  /plan  →  /build  →  /test  →  /review  →  /ship
```

Plus `/webperf` (measure before optimizing) and `/code-simplify` (clarity over cleverness).

`/build auto` generates the plan and implements every task in one approved pass. It requires a
real spec at `SPEC.md`, `docs/SPEC.md`, or `spec/*` — a README does not count — and it still
runs the full test-driven loop with one commit per task.

### Skills

| Skill | Use when |
|---|---|
| `spec-driven-development` | Defining what to build, before any code |
| `planning-and-task-breakdown` | Turning a spec into small atomic tasks |
| `incremental-implementation` | Building one vertical slice at a time |
| `test-driven-development` | Any logic change or bug fix — red, green, refactor |
| `code-review-and-quality` | Before merging anything |
| `debugging-and-error-recovery` | A test won't pass or the build breaks |
| `doubt-driven-development` | Risky, irreversible, or ambiguous work |
| `security-and-hardening` | Auth, secrets, input handling, spend paths |
| `api-and-interface-design` | Designing endpoints or module boundaries |
| `frontend-ui-engineering` | Building UI |
| `browser-testing-with-devtools` | Verifying browser runtime (needs chrome-devtools MCP) |
| `performance-optimization` | Something is measurably slow |
| `observability-and-instrumentation` | Adding logs, metrics, traces |
| `ci-cd-and-automation` | Pipelines and quality gates |
| `git-workflow-and-versioning` | Branching, commits, releases |
| `documentation-and-adrs` | Recording a decision that is hard to reverse |
| `deprecation-and-migration` | Removing or migrating existing behavior |
| `code-simplification` | Code works but is hard to read |
| `context-engineering` | Managing what goes into the context window |
| `source-driven-development` | Working from an authoritative source or upstream docs |
| `idea-refine` | An idea is still fuzzy |
| `interview-me` | Requirements need interrogation, one question at a time |
| `shipping-and-launch` | Releasing to production |
| `using-agent-skills` | How to author or apply skills here |

### Subagents

`code-reviewer` (five-axis review), `security-auditor`, `test-engineer`, `web-performance-auditor`.

## Project rules that override skill defaults

These come from the README's Principles and Safety Boundary and take precedence:

- **Real execution only.** Never present simulated or mock earnings as real revenue. Test
  fixtures must be unmistakably labelled as fixtures.
- **Every experiment is versioned** and records strategy ID, version, parent strategy, cost,
  revenue, profit, ROI, conversion rate, execution time, failures, policy result, and
  promotion status.
- **Every spend has a budget.** Any code path that can spend money needs an enforced budget
  cap plus a policy check before it runs.
- **Rollback is mandatory.** If a change cannot be undone with `git revert` or a documented
  runbook, stop and get explicit sign-off — invoke `doubt-driven-development`.
- **Production changes require policy checks** and must be auditable.
- Failed strategies are retained for analysis; never delete experiment history.
- Refuse work that falls inside the README's Safety Boundary exclusion list.

## Updating skills

```bash
npx skills update                 # refresh to upstream latest
npx skills list                   # show what is installed
```

Local edits to `.agents/skills/**` are intentional forks — note them here so an update does
not silently revert them. No local edits yet, except that the vendored commands and subagents
have the upstream `agent-skills:` plugin namespace stripped so they resolve against
`.agents/skills/` directly.
