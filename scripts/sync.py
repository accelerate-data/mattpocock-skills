#!/usr/bin/env python3
"""Vendor mattpocock/skills minus what engineering-skills already provides."""
import json
import re
import shutil
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
