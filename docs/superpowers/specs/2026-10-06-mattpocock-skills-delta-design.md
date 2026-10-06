# mattpocock-skills (AD delta) — design

**Date:** 2026-10-06
**Repo:** `accelerate-data/mattpocock-skills` (public, MIT) — local clone `~/scratch/ad-plugins/mattpocock-skills`
**Pattern source:** `accelerate-data/remotion-skills` (vendored subset + weekly sync PR)

## Purpose

Ship the skills from `mattpocock/skills` that `accelerate-data/engineering-skills` does not already provide, as one AD plugin. It replaces the official `mattpocock-skills@claude-plugins-official` plugin.

Success:

- No skill name appears twice across `engineering-skills` and this plugin, in Claude Code, Codex, or OpenCode.
- No skill needs a `Skill(...)` deny rule to stay out of the way.
- Upstream changes arrive as a reviewed PR, never silently.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| D1 | Which upstream skills are in scope | The skills listed in upstream `.claude-plugin/plugin.json` → `skills[]`. Upstream `misc/` and `in-progress/` are out. |
| D2 | What counts as "in engineering-skills" | Name match only. A kept skill is any in-scope upstream skill whose `name:` is not a `name:` in `engineering-skills/skills/*/SKILL.md`. |
| D3 | How the exclusion is maintained | Computed at every sync from the live `engineering-skills` repo. No static exclude list. |
| D4 | Skills that are currently denied | `ask-matt`, `code-review`, `codebase-design`, `implement`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `tdd` are patched to user-only (`disable-model-invocation: true`). The 9 deny rules are removed. |
| D5 | Plugin and repo name | `mattpocock-skills`. The README states clearly that the plugin is the delta from `engineering-skills`. |
| D6 | Visibility | Public. Upstream is MIT; LICENSE and per-skill NOTICE files keep attribution. |
| D7 | Sync mechanism | Vendored copy plus a scheduled sync PR. A git fork and a marketplace-only entry were rejected: a fork turns every excluded or patched skill into a merge conflict, and a marketplace entry cannot patch or compute the delta. |

## Repo layout

```
.claude-plugin/plugin.json      name mattpocock-skills, skills "./skills/", version x.y.z
.codex-plugin/plugin.json       same name and version
skills/<name>/                  flat; upstream category folders removed
  SKILL.md (+ upstream files)
  NOTICE                        upstream URL, source path, commit SHA, MIT, local patches
sync.toml                       upstream repo and manifest path, engineering-skills repo, user_only list
scripts/sync.py                 all sync logic; runs locally and in CI
scripts/test_sync.py            assert-based self-check against fixture repos
.github/workflows/sync-upstream.yml
.github/workflows/check.yml
LICENSE                         upstream MIT text, copyright kept
README.md                       delta statement, generated skill table, how sync works
```

## Sync flow (`scripts/sync.py`)

1. **Fetch.** Shallow-clone `mattpocock/skills` (`main`) and record its HEAD SHA. Shallow-clone `accelerate-data/engineering-skills` (public, no token).
2. **Resolve upstream set.** Read upstream `.claude-plugin/plugin.json` → `skills[]`. If the file is missing or the shape changed, exit non-zero with an `::error::` line.
3. **Compute delta.** Collect `name:` from every `engineering-skills/skills/*/SKILL.md`. Keep upstream skills whose `name:` is not in that set.
4. **Mirror.** Delete `skills/*`. Copy each kept skill flat to `skills/<name>/`. Delete symlinks.
5. **Patch.** For each name in `sync.toml` → `user_only`: set `disable-model-invocation: true` in the SKILL.md frontmatter; if `agents/openai.yaml` exists, set `policy.allow_implicit_invocation: false`. A listed name that is not present produces a warning in the report, not a failure.
6. **NOTICE.** Write `skills/<name>/NOTICE` with upstream URL, source path, commit SHA, license, and the patches applied.
7. **Report.** Print a markdown summary (old SHA → new SHA, skills added or removed upstream, skills dropped or restored by the delta, patch warnings) to stdout and `$GITHUB_STEP_SUMMARY`. Regenerate the README skill table between marker comments.

The previous upstream SHA is read from any existing NOTICE file.

Kept skills reference `/handoff` and `/grill-with-docs` by slash name. `engineering-skills` provides both names, so these references resolve to the AD versions. They are not patched.

## Workflows

**`sync-upstream.yml`** — triggers: weekly cron (Monday 09:00 UTC) and `workflow_dispatch`.

1. Run `scripts/sync.py`.
2. If `skills/` or `README.md` changed: bump the patch version in both manifests (they must match before the bump).
3. Open or update a PR on branch `chore/sync-upstream` with the step 7 summary as the body, using `peter-evans/create-pull-request`.

A human merges. No auto-merge.

**`check.yml`** — triggers: every PR and push to `main`.

- Both manifest versions are equal.
- Every `skills/*/SKILL.md` has a `name:` equal to its folder name.
- No skill name collides with a current `engineering-skills` skill name.
- `python scripts/test_sync.py` passes.

## Testing

`scripts/test_sync.py` builds small fixture repos in a temp directory and runs `sync.py` against them. It asserts:

- a skill whose name exists in the fixture `engineering-skills` is dropped;
- nested upstream paths are flattened;
- the user-only patch is applied, and a second run produces no diff (idempotent);
- a missing upstream manifest makes the run fail.

## Rollout

Each step that writes outside this machine is previewed and confirmed first.

1. **Local build.** Build the repo and run `sync.py` for real. Expect 23 skills, 7 of them user-only, README with the delta statement.
2. **GitHub.** `gh repo create accelerate-data/mattpocock-skills --public` with remote `ssh://git@ssh.github.com:443/accelerate-data/mattpocock-skills.git`. Push `main`. Run the sync workflow once by `workflow_dispatch`; expect no diff and no PR.
3. **Marketplace.** PR to `accelerate-data/plugin-marketplace` adding `{"name": "mattpocock-skills", "source": {"source": "url", "url": "https://github.com/accelerate-data/mattpocock-skills.git"}}`.
4. **Cutover on this workstation.**
   - `claude plugin uninstall mattpocock-skills@claude-plugins-official`, then install `mattpocock-skills@ad-internal-marketplace`.
   - Remove the 9 `Skill(mattpocock-skills:…)` deny rules from `~/.claude/settings.json`.
   - Remove the link `~/.codex/skills/mattpocock-skills`.
   - Run `sync-agent-skills` and `sync-agent-skills --codex --yes`.
5. **Verify.**
   - Claude Code `/skills`: `mattpocock-skills:*` comes from `ad-internal-marketplace`; no `handoff` or `grill-with-docs`.
   - Codex: `codex debug prompt-input` lists the model-invocable set.
   - OpenCode: `~/.agents/plugin-skills/mattpocock-skills` points at the new install path.
6. **Docs.** Update `~/Documents/ailearnings/_docs/agent-plugin-sync.md` and `_docs/projects.md`. Log an `LRN-CLAUDE` entry.

## Out of scope

- Upstream `misc/` and `in-progress/` skills.
- Auto-merge of sync PRs.
- Changes to `engineering-skills`.
