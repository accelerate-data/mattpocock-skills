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
