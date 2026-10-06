#!/usr/bin/env python3
"""Vendor mattpocock/skills minus what engineering-skills already provides."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def load_config(root: Path) -> dict:
    return tomllib.loads((root / "sync.toml").read_text())


def skill_name(skill_dir: Path) -> str:
    lines = (skill_dir / "SKILL.md").read_text().splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            m = re.match(r"^name:\s*(.+)$", line)
            if m:
                return m.group(1).strip().strip("\"'")
    return skill_dir.name


def upstream_skills(upstream: Path, manifest: str) -> list[Path]:
    path = upstream / manifest
    try:
        skills = json.loads(path.read_text()).get("skills")
    except (OSError, ValueError, AttributeError):
        raise SystemExit(f"::error::upstream manifest {manifest} missing or not a JSON object")
    if not isinstance(skills, list):
        raise SystemExit(f"::error::upstream manifest {manifest} has no skills list")
    dirs = [upstream / s for s in skills]
    for d in dirs:
        if not (d / "SKILL.md").is_file():
            raise SystemExit(f"::error::listed skill {d} has no SKILL.md")
    return dirs


def engineering_names(eng: Path) -> set[str]:
    return {skill_name(p.parent) for p in (eng / "skills").rglob("SKILL.md")}


def compute_delta(skills: list[Path], excluded: set[str]) -> tuple[list[Path], list[str]]:
    kept, dropped = [], []
    for s in skills:
        name = skill_name(s)
        if name in excluded:
            dropped.append(name)
        else:
            kept.append(s)
    return kept, dropped


def mirror(kept: list[Path], dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for s in kept:
        target = dest / skill_name(s)
        shutil.copytree(s, target, symlinks=True)
        for p in list(target.rglob("*")):
            if p.is_symlink():
                p.unlink()


def _patch_skill_md(path: Path) -> None:
    lines = path.read_text().splitlines(keepends=True)
    flag = "disable-model-invocation: true\n"
    found = False
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        if re.match(r"^disable-model-invocation:", line):
            lines[i], found = flag, True
            break
    if not found:
        lines.insert(1, flag)
    path.write_text("".join(lines))


def _patch_openai_yaml(path: Path) -> None:
    lines = path.read_text().splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    key = "  allow_implicit_invocation: false\n"
    for i, line in enumerate(lines):
        if line.rstrip() == "policy:":
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")):
                if lines[j].strip().startswith("allow_implicit_invocation:"):
                    lines[j] = key
                    break
                j += 1
            else:
                lines.insert(i + 1, key)
            break
    else:
        lines += ["policy:\n", key]
    path.write_text("".join(lines))


def patch_user_only(skills_dir: Path, names: list[str]) -> list[str]:
    warnings = []
    for name in names:
        d = skills_dir / name
        if not (d / "SKILL.md").is_file():
            warnings.append(f"user_only: {name} not present")
            continue
        _patch_skill_md(d / "SKILL.md")
        yaml = d / "agents/openai.yaml"
        if yaml.is_file():
            _patch_openai_yaml(yaml)
    return warnings


def write_notice(skill_dir: Path, source_rel: str, sha: str, patches: list[str]) -> None:
    mods = "\n".join(f"  - {p}" for p in patches) or "  - none"
    (skill_dir / "NOTICE").write_text(
        f"skills/{skill_dir.name}/ — vendored from mattpocock/skills\n\n"
        "  Upstream:        https://github.com/mattpocock/skills\n"
        f"  Source path:     {source_rel}\n"
        f"  Vendored from:   commit {sha}\n"
        "  License:         MIT (see LICENSE at the repo root)\n\n"
        "Local modifications, re-applied by scripts/sync.py on every sync:\n"
        f"{mods}\n\n"
        "To refresh, run .github/workflows/sync-upstream.yml.\n"
    )


def read_previous_sha(skills_dir: Path) -> str:
    for notice in sorted(skills_dir.glob("*/NOTICE")):
        m = re.search(r"^\s*Vendored from:\s+commit (\S+)", notice.read_text(), re.M)
        if m:
            return m.group(1)
    return "none"


def render_report(old_sha, new_sha, before, after, dropped, warnings) -> str:
    def bullets(items):
        return "".join(f"- {i}\n" for i in sorted(items)) or "- none\n"

    out = (
        "## mattpocock-skills sync\n\n"
        f"Upstream commit: {old_sha} → {new_sha}\n\n"
        f"### Added\n{bullets(after - before)}\n"
        f"### Removed\n{bullets(before - after)}\n"
        f"### Dropped (already in engineering-skills)\n{bullets(dropped)}"
    )
    if warnings:
        out += f"\n### Warnings\n{bullets(warnings)}"
    return out


def update_readme(readme: Path, rows: list[tuple[str, bool]]) -> None:
    start, end = "<!-- skills:start -->", "<!-- skills:end -->"
    text = readme.read_text()
    if start not in text or end not in text:
        raise SystemExit(f"::error::{readme} is missing the skills markers")
    head, rest = text.split(start, 1)
    tail = rest.split(end, 1)[1]
    table = "| Skill | Invocation |\n| --- | --- |\n" + "".join(
        f"| {n} | {'model' if m else 'user-only'} |\n" for n, m in sorted(rows)
    )
    readme.write_text(f"{head}{start}\n{table}{end}{tail}")


def check(root: Path, eng: Path) -> list[str]:
    errors = []
    versions = {
        d: json.loads((root / d / "plugin.json").read_text()).get("version")
        for d in (".claude-plugin", ".codex-plugin")
    }
    if len(set(versions.values())) > 1:
        errors.append(f"manifest versions differ: {versions}")
    eng_names = engineering_names(eng)
    for md in sorted((root / "skills").glob("*/SKILL.md")):
        name = skill_name(md.parent)
        if name != md.parent.name:
            errors.append(f"skills/{md.parent.name}: name '{name}' does not match folder")
        if name in eng_names:
            errors.append(f"skills/{md.parent.name}: name '{name}' is already in engineering-skills")
    return errors


def clone(repo: str, ref: str, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, repo, str(dest)],
        capture_output=True, text=True,
    )
    if r.returncode:
        raise SystemExit(f"::error::clone of {repo} failed: {r.stderr.strip()}")
    return dest


def head_sha(repo_dir: Path) -> str:
    r = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream-dir")
    ap.add_argument("--eng-dir")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = Path.cwd()
    cfg = load_config(root)
    cache = root / ".sync-cache"
    eng = Path(args.eng_dir) if args.eng_dir else clone(
        cfg["engineering"]["repo"], cfg["engineering"]["ref"], cache / "engineering-skills")

    if args.check:
        errors = check(root, eng)
        print("\n".join(errors) or "check: clean")
        return 1 if errors else 0

    up = Path(args.upstream_dir) if args.upstream_dir else clone(
        cfg["upstream"]["repo"], cfg["upstream"]["ref"], cache / "upstream")
    skills_dir = root / "skills"
    old_sha = read_previous_sha(skills_dir)
    before = {p.name for p in skills_dir.iterdir() if p.is_dir()} if skills_dir.is_dir() else set()
    new_sha = head_sha(up)

    kept, dropped = compute_delta(upstream_skills(up, cfg["upstream"]["manifest"]), engineering_names(eng))
    mirror(kept, skills_dir)
    user_only = cfg["patches"]["user_only"]
    warnings = patch_user_only(skills_dir, user_only)
    for s in kept:
        name = skill_name(s)
        patches = []
        if name in user_only:
            patches.append("SKILL.md: disable-model-invocation: true")
            if (skills_dir / name / "agents/openai.yaml").is_file():
                patches.append("agents/openai.yaml: allow_implicit_invocation: false")
        write_notice(skills_dir / name, s.relative_to(up).as_posix(), new_sha, patches)
    shutil.copyfile(up / "LICENSE", root / "LICENSE")

    after = {skill_name(s) for s in kept}
    update_readme(root / "README.md", [(n, n not in user_only) for n in after])
    report = render_report(old_sha, new_sha, before, after, dropped, warnings)
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
