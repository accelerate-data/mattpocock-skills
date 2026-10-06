# Kickoff — execute the mattpocock-skills delta plan

Paste everything below the line into a fresh Claude Code session started in
`~/scratch/ad-plugins/mattpocock-skills`.

---

You are executing an approved implementation plan. Design and planning are done; do not re-open decisions.

**Read first, in this order:**
1. `docs/superpowers/specs/2026-10-06-mattpocock-skills-delta-design.md` — the approved spec.
2. `docs/superpowers/plans/2026-10-06-mattpocock-skills-delta.md` — the approved plan (7 tasks).
3. Reference pattern: `~/scratch/ad-plugins/remotion-skills` (`.github/workflows/sync-vendored-skills.yml`, `scripts/apply-local-patches.py`, both plugin manifests). Copy its shape; do not modify that repo.

**Execution method:** use `superpowers:subagent-driven-development`. Implementer subagents run on **Sonnet**; per-task and final whole-branch reviewers run on **Opus**. You (the controller) re-verify every reviewer and implementer claim yourself before marking a task done: run `python3 scripts/test_sync.py`, `python3 scripts/sync.py --check`, and the counts in Task 3 Step 5.

**State at start:**
- Local git repo on `main` with two commits (spec, plan). No remote yet.
- `accelerate-data/mattpocock-skills` does **not** exist on GitHub yet.
- This workstation currently uses `mattpocock-skills@claude-plugins-official` (v1.2.3), with 9 `Skill(mattpocock-skills:…)` deny rules in `~/.claude/settings.json` and a manual symlink `~/.codex/skills/mattpocock-skills` → `~/.agents/plugin-skills/mattpocock-skills`. Tasks 6–7 replace all three.

**Hard rules:**
- Tasks 1–4 are local and reversible: run them without stopping.
- Tasks 5, 6, 7 are USER checkpoints. Before each, show the exact preview the plan names (file list, diff, commands) and **wait for an explicit yes**. Do not merge the marketplace PR yourself. Task 7 starts only after the user says the marketplace PR is merged.
- Git: commit as Shwetank Sheel <github@shwetank.com>, **no** Co-Authored-By or AI trailer lines. Stage files by name, never `git add -A`. Remotes are SSH on port 443: `ssh://git@ssh.github.com:443/<owner>/<repo>.git`.
- PR bodies end with: `_Drafted with Claude's help — content and judgment are mine; Claude helped write and verify the change._`
- Python: stdlib only, 3.11+. No new dependencies.
- Auth failure (`gh`, `git push`, `claude plugin`) is a hard stop: report the exact command the user must run (for example `gh auth login`) and wait.
- rtk filters some command output. If a test or command result looks empty or wrong, re-run it with `rtk proxy <cmd>` before acting on it.
- Communicate with the user in short, plain ASD-STE-100 sentences. Report times in the workstation's local zone.

**Tools this session will have:** Bash (with `gh` authenticated as `admiraldata`, `git`, `python3`, `ruby`, `jq`, `claude` CLI, `codex` CLI, `~/.local/bin/sync-agent-skills`), file Read/Edit/Write, the Agent tool for subagents, and the Skill tool (`superpowers:*` from `ad-internal-marketplace`). It does **not** inherit this planning session's context — everything it needs is in the three files above.

**Done means:** all 7 tasks checked off in the plan file; Task 7 Step 5 verification output shown to the user; the docs and `LRN-CLAUDE` entry in Task 7 Step 6 written; a final summary listing the repo URL, the marketplace PR URL, the kept-skill count, and anything skipped with the reason.
