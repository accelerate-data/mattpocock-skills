# mattpocock-skills (AD delta) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish `accelerate-data/mattpocock-skills`, a vendored plugin holding the `mattpocock/skills` skills that `engineering-skills` does not provide, kept current by a weekly sync PR, and cut this workstation over to it.

**Architecture:** One stdlib-only script, `scripts/sync.py`, does fetch → delta → mirror → patch → NOTICE → report, and also a `--check` mode for CI. Two thin GitHub workflows call it. The pattern copies `accelerate-data/remotion-skills`.

**Tech Stack:** Python 3.11+ stdlib only (`tomllib`, `json`, `re`, `shutil`, `subprocess`, `pathlib`), GitHub Actions, `peter-evans/create-pull-request@v7`, `gh` CLI, Claude Code plugin CLI, `sync-agent-skills`.

**Spec:** `docs/superpowers/specs/2026-10-06-mattpocock-skills-delta-design.md`

## Global Constraints

- Repo `accelerate-data/mattpocock-skills`, **public**, MIT. Local path `~/scratch/ad-plugins/mattpocock-skills`.
- Git remote: `ssh://git@ssh.github.com:443/accelerate-data/mattpocock-skills.git`. Commits as Shwetank Sheel <github@shwetank.com>, **no** Co-Authored-By or AI trailers.
- Plugin name `mattpocock-skills`; both manifests carry the same version; start at `1.0.0`.
- Scope = upstream `.claude-plugin/plugin.json` → `skills[]` only. Kept = scope minus any `name:` found in `engineering-skills/skills/*/SKILL.md`. Expected today: 23 kept (drops `handoff`, `grill-with-docs`).
- `user_only` = `ask-matt`, `code-review`, `codebase-design`, `implement`, `improve-codebase-architecture`, `setup-matt-pocock-skills`, `tdd`.
- Flat layout `skills/<name>/`; no symlinks.
- Sync PR branch `chore/sync-upstream`; cron `0 9 * * 1`; human merges, no auto-merge.
- README must state the plugin is **the delta from `engineering-skills`**.
- Every write outside this machine (repo create, push, marketplace PR, plugin install/uninstall, settings edit) is previewed to the user and confirmed before it runs.

## Review Focus

1. **Upstream folder name ≠ `name:`** — use the frontmatter `name:` for both the delta and the target folder (test in Task 1).
2. **Multi-line `description: >` frontmatter** — inserting a flag after the `description:` line would land inside the folded scalar. Insert `disable-model-invocation: true` directly after the opening `---` (test in Task 2).
3. **`engineering-skills` SKILL.md without `name:`** — fall back to its folder name so a missing key does not silently re-admit a duplicate (test in Task 1).
4. **Upstream `openai.yaml` already has `policy:`** (20 of 35 do today) — set the existing key to `false` or insert under the existing block; never append a second `policy:` (test in Task 2).
5. **First run with no prior NOTICE / README without markers** — old SHA reports as `none`; missing README markers is a hard error, not a silent skip (test in Task 3).

---

### Task 1: Scaffold + delta and mirror

**Files:**
- Create: `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `sync.toml`, `.gitignore` (`__pycache__/`, `/.sync-cache/`)
- Create: `scripts/sync.py`
- Test: `scripts/test_sync.py`

**Interfaces:**
- Produces (in `scripts/sync.py`):
  - `load_config(root: Path) -> dict` — parses `sync.toml`.
  - `skill_name(skill_dir: Path) -> str` — frontmatter `name:`, else folder name.
  - `upstream_skills(upstream: Path, manifest: str) -> list[Path]` — resolves `skills[]`; `SystemExit` with message starting `::error::` if the manifest is missing, not JSON, has no `skills` list, or a listed dir has no `SKILL.md`.
  - `engineering_names(eng: Path) -> set[str]`
  - `compute_delta(skills: list[Path], excluded: set[str]) -> tuple[list[Path], list[str]]` — (kept dirs, dropped names), order preserved.
  - `mirror(kept: list[Path], dest: Path) -> None` — empties `dest`, copies each to `dest/<skill_name>`, deletes symlinks.
- Test helper (in `test_sync.py`): `make_skill(root: Path, rel: str, name: str, extra_frontmatter: str = "") -> Path`, `make_upstream(tmp: Path, rels: list[str]) -> Path` (writes the manifest).

Manifests: copy the shape of `remotion-skills` (`.claude-plugin` has name, description, version `1.0.0`, author `Accelerate Data`, repository, license `MIT`, `skills: "./skills/"`, keywords; `.codex-plugin` adds the `interface` block with displayName `Matt Pocock Skills (AD delta)`, category `Productivity`). Description: `"Matt Pocock's skills that engineering-skills does not already provide, vendored from mattpocock/skills and kept current by a weekly sync."`

`sync.toml`:
```toml
[upstream]
repo = "https://github.com/mattpocock/skills.git"
ref = "main"
manifest = ".claude-plugin/plugin.json"

[engineering]
repo = "https://github.com/accelerate-data/engineering-skills.git"
ref = "main"

[patches]
user_only = ["ask-matt", "code-review", "codebase-design", "implement", "improve-codebase-architecture", "setup-matt-pocock-skills", "tdd"]
```

- [ ] **Step 1: Write failing tests** in `scripts/test_sync.py` (plain functions, run by a `__main__` loop over `test_*` globals, each in its own `tempfile.TemporaryDirectory`):
  - `test_delta_drops_engineering_names`: upstream `engineering/a`, `productivity/handoff`; eng has `handoff` → kept names `["a"]`, dropped `["handoff"]`.
  - `test_name_differs_from_folder`: upstream folder `engineering/foo` with `name: bar`; after `mirror`, `dest/bar/SKILL.md` exists and `dest/foo` does not.
  - `test_eng_skill_without_name_uses_folder`: eng `skills/handoff/SKILL.md` with no `name:` → `"handoff" in engineering_names(eng)`.
  - `test_mirror_flattens_and_drops_symlinks`: nested upstream with a symlink inside a skill → `dest/<name>` flat, `not any(p.is_symlink() for p in dest.rglob("*"))`, and a stale `dest/old` from before is gone.
  - `test_missing_manifest_fails`: no manifest → `SystemExit` whose message starts with `::error::`.
- [ ] **Step 2:** `python3 scripts/test_sync.py` → fails (`ImportError`/`AttributeError`).
- [ ] **Step 3:** Implement the five functions plus `load_config`. Frontmatter parse = lines between the first two `---` lines; match `^name:\s*(.+)$`, strip quotes.
- [ ] **Step 4:** `python3 scripts/test_sync.py` → all pass, prints `ok N tests`.
- [ ] **Step 5:** Commit `feat: delta and mirror for vendored mattpocock skills`.

### Task 2: Patches and NOTICE

**Files:**
- Modify: `scripts/sync.py`
- Test: `scripts/test_sync.py`

**Interfaces:**
- Consumes: `skill_name`, `mirror` from Task 1.
- Produces:
  - `patch_user_only(skills_dir: Path, names: list[str]) -> list[str]` — returns warnings (`"user_only: <name> not present"`) for missing names.
  - `write_notice(skill_dir: Path, source_rel: str, sha: str, patches: list[str]) -> None`
  - `read_previous_sha(skills_dir: Path) -> str` — SHA from any `NOTICE` line `Vendored from:   commit <sha>`, else `"none"`.

NOTICE text (exact):
```
skills/<name>/ — vendored from mattpocock/skills

  Upstream:        https://github.com/mattpocock/skills
  Source path:     <source_rel>
  Vendored from:   commit <sha>
  License:         MIT (see LICENSE at the repo root)

Local modifications, re-applied by scripts/sync.py on every sync:
  - <one line per patch, or "none">

To refresh, run .github/workflows/sync-upstream.yml.
```

- [ ] **Step 1: Write failing tests:**
  - `test_patch_inserts_after_opening_fence`: SKILL.md with `description: >\n  line one\n  line two` → after patch, line 2 of the file is `disable-model-invocation: true` and the folded description is byte-identical.
  - `test_patch_is_idempotent`: patch twice → second run changes no file (compare bytes).
  - `test_patch_respects_existing_flag`: `disable-model-invocation: false` present → becomes `true`, appears once.
  - `test_openai_yaml_existing_policy`: `policy:\n  allow_implicit_invocation: true` → value `false`, `text.count("policy:") == 1`; file without `policy:` → block appended; no `agents/openai.yaml` → file not created.
  - `test_missing_user_only_warns`: names `["gone"]` → returns `["user_only: gone not present"]`, no exception.
  - `test_previous_sha`: no NOTICE → `"none"`; after `write_notice(..., sha="abc123", ...)` → `"abc123"`.
- [ ] **Step 2:** Run → fail.
- [ ] **Step 3:** Implement. Line-based edits only (no YAML library).
- [ ] **Step 4:** Run → all pass.
- [ ] **Step 5:** Commit `feat: user-only patch and NOTICE files`.

### Task 3: Report, README, CLI, check mode, first real sync

**Files:**
- Modify: `scripts/sync.py`
- Create: `README.md`, `LICENSE` (copied from the upstream clone), `skills/` (generated)
- Test: `scripts/test_sync.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2.
- Produces:
  - `render_report(old_sha: str, new_sha: str, before: set[str], after: set[str], dropped: list[str], warnings: list[str]) -> str` — markdown.
  - `update_readme(readme: Path, rows: list[tuple[str, bool]]) -> None` — replaces text between `<!-- skills:start -->` and `<!-- skills:end -->` with a table `| Skill | Invocation |` (`model` / `user-only`); `SystemExit` if markers are missing.
  - `check(root: Path, eng: Path) -> list[str]` — errors: manifest versions differ; a `skills/*/SKILL.md` `name:` ≠ folder; a name in `engineering_names(eng)`.
  - CLI: `python3 scripts/sync.py [--upstream-dir D] [--eng-dir D] [--check]`. Without `--*-dir`, shallow-clones the repos from `sync.toml` into `.sync-cache/`. Prints the report; appends it to `$GITHUB_STEP_SUMMARY` when set. `--check` prints errors and exits 1 if any.

README content: title; first paragraph states this plugin is **the delta from `accelerate-data/engineering-skills`**: every skill in `mattpocock/skills`' plugin manifest except those whose name `engineering-skills` already ships, computed fresh on every sync; slash references such as `/handoff` resolve to the `engineering-skills` versions; the user-only list and why; how the weekly sync PR works; marker block for the table; install via `plugin-marketplace`; MIT attribution to Matt Pocock.

- [ ] **Step 1: Write failing tests:**
  - `test_report_first_run`: `old_sha="none"` → report contains `none →` and lists dropped `handoff`.
  - `test_readme_markers_required`: README without markers → `SystemExit`.
  - `test_readme_table`: rows `[("tdd", False), ("grilling", True)]` → contains `| tdd | user-only |` and `| grilling | model |`.
  - `test_check_detects_collision_and_version_drift`: fixture root with `1.0.0` vs `1.0.1` and a skill named `handoff` while eng has `handoff` → two errors.
  - `test_end_to_end_idempotent`: run `main(["--upstream-dir", u, "--eng-dir", e])` with `cwd` = fixture root twice → no byte change on the second run.
- [ ] **Step 2:** Run → fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → all pass.
- [ ] **Step 5: Real sync.** `python3 scripts/sync.py`. Expected: `ls skills | wc -l` = `23`; `handoff` and `grill-with-docs` absent; `grep -l '^disable-model-invocation: true' skills/{ask-matt,code-review,codebase-design,implement,improve-codebase-architecture,setup-matt-pocock-skills,tdd}/SKILL.md | wc -l` = `7`; `python3 scripts/sync.py --check` exits 0; a second `python3 scripts/sync.py` leaves `git status --porcelain` empty after commit.
- [ ] **Step 6:** Commit `feat: first vendored sync of mattpocock skills (23)`.

### Task 4: Workflows

**Files:**
- Create: `.github/workflows/sync-upstream.yml`, `.github/workflows/check.yml`

**Interfaces:**
- Consumes: the CLI from Task 3.

`sync-upstream.yml`: `on: schedule (cron "0 9 * * 1") + workflow_dispatch`; `permissions: contents: write, pull-requests: write`; steps: `actions/checkout@v4` → `actions/setup-python@v5` (`3.12`) → `python3 scripts/sync.py` → if `git status --porcelain -- skills README.md LICENSE` is non-empty, bump the patch version in both manifests (fail if they differ first — reuse the remotion step body) → `peter-evans/create-pull-request@v7` with `branch: chore/sync-upstream`, `title: "chore: sync from mattpocock/skills"`, body = the report (pass it via a step output written by the sync step).

`check.yml`: `on: pull_request + push (main)`; steps: checkout → setup-python → `python3 scripts/test_sync.py` → clone engineering-skills shallow to `/tmp/eng` → `python3 scripts/sync.py --check --eng-dir /tmp/eng`.

- [ ] **Step 1:** Write both files.
- [ ] **Step 2:** Validate YAML syntax with `ruby -ryaml -e 'YAML.load_file(ARGV[0])' <file>` for each file; expect no output. If `actionlint` is installed (`brew list actionlint`), run it; expect no findings.
- [ ] **Step 3:** Commit `ci: weekly upstream sync PR and PR checks`.

### Task 5: Publish to GitHub (USER checkpoint)

- [ ] **Step 1: Preview** to the user: repo name, visibility public, file list (`git ls-files`), and that `main` will be pushed. Wait for yes.
- [ ] **Step 2:** `gh repo create accelerate-data/mattpocock-skills --public --description "Matt Pocock's skills that engineering-skills does not provide — vendored, weekly upstream sync"`; `git remote add origin ssh://git@ssh.github.com:443/accelerate-data/mattpocock-skills.git`; `git push -u origin main`.
- [ ] **Step 3:** `gh run list -R accelerate-data/mattpocock-skills --workflow check.yml -L 1` → `completed success`.
- [ ] **Step 4:** `gh workflow run sync-upstream.yml -R accelerate-data/mattpocock-skills`; wait; expect run success and `gh pr list -R accelerate-data/mattpocock-skills` empty (no diff).

### Task 6: Marketplace entry (USER checkpoint)

**Files:**
- Modify: `~/scratch/ad-plugins/plugin-marketplace/.claude-plugin/marketplace.json` (and the Codex marketplace file if the repo has one — check `ls .agents/plugins` first, since Codex reads `sparse_paths = [".agents/plugins"]`).

- [ ] **Step 1:** In `plugin-marketplace`, `git pull`, branch `feat/mattpocock-skills`, add the entry `{"name": "mattpocock-skills", "source": {"source": "url", "url": "https://github.com/accelerate-data/mattpocock-skills.git"}}` (mirror the field set of the `remotion-skills` entry, including any `description`/`category`) in every marketplace manifest the repo keeps. Run the repo's own validation if it has one (check `.github/workflows` / `package.json` scripts).
- [ ] **Step 2: Preview** the diff and PR body to the user; wait for yes.
- [ ] **Step 3:** Push and `gh pr create`. PR body ends with the CLAUDE.md disclaimer line. Report the PR URL. Merge only on the user's say-so.

### Task 7: Cutover, verify, document (USER checkpoint)

Runs after the marketplace PR is merged.

- [ ] **Step 1: Preview** the cutover list to the user; wait for yes.
- [ ] **Step 2:** `claude plugin marketplace update ad-internal-marketplace`; `claude plugin uninstall mattpocock-skills@claude-plugins-official`; `claude plugin install mattpocock-skills@ad-internal-marketplace`.
- [ ] **Step 3:** Remove the 9 `Skill(mattpocock-skills:…)` entries from `permissions.deny` in `~/.claude/settings.json` (back up first to `settings.json.bak-20261006-mp`).
- [ ] **Step 4:** `rm ~/.codex/skills/mattpocock-skills` (it is a symlink — confirm with `test -L` first). Run `~/.local/bin/sync-agent-skills` and `~/.local/bin/sync-agent-skills --codex --yes`; re-run `--codex` → "already matches".
- [ ] **Step 5: Verify.**
  - `jq '.plugins["mattpocock-skills@ad-internal-marketplace"]' ~/.claude/plugins/installed_plugins.json` → one user-scope entry; no `@claude-plugins-official` entry.
  - `ls <installPath>/skills | wc -l` → `23`; no `handoff`, `grill-with-docs`.
  - `readlink ~/.agents/plugin-skills/mattpocock-skills` → path under `cache/ad-internal-marketplace/mattpocock-skills/1.0.0`.
  - `codex debug prompt-input hi | grep -o 'mattpocock-skills/[a-z-]*/SKILL.md' | sort -u` → only model-invocable skills, none of the 7 user-only.
- [ ] **Step 6: Docs.** Update `~/Documents/ailearnings/_docs/agent-plugin-sync.md` (mattpocock now from `ad-internal-marketplace`; deny rules gone; remove the manual Codex link note) and `_docs/projects.md` (new repo entry). Add an `LRN-CLAUDE-20261006-NNN` entry to `LEARNINGS.md`: plugin skills cannot be hidden by `skillOverrides`, so curate by vendoring a delta repo.
