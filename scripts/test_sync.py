import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sync


def make_skill(root: Path, rel: str, name: str, extra_frontmatter: str = "") -> Path:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    fm = f"name: {name}\n" if name else ""
    (d / "SKILL.md").write_text(f"---\n{fm}description: x\n{extra_frontmatter}---\nbody\n")
    return d


def make_upstream(tmp: Path, rels: list[str]) -> Path:
    up = tmp / "up"
    for rel in rels:
        make_skill(up, rel, Path(rel).name)
    (up / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (up / ".claude-plugin/plugin.json").write_text(json.dumps({"skills": [f"./{r}" for r in rels]}))
    return up


def test_delta_drops_engineering_names(tmp):
    up = make_upstream(tmp, ["engineering/a", "productivity/handoff"])
    eng = tmp / "eng"
    make_skill(eng, "skills/handoff", "handoff")
    skills = sync.upstream_skills(up, ".claude-plugin/plugin.json")
    kept, dropped = sync.compute_delta(skills, sync.engineering_names(eng))
    assert [sync.skill_name(k) for k in kept] == ["a"]
    assert dropped == ["handoff"]


def test_name_differs_from_folder(tmp):
    make_skill(tmp, "up/engineering/foo", "bar")
    dest = tmp / "dest"
    sync.mirror([tmp / "up/engineering/foo"], dest)
    assert (dest / "bar/SKILL.md").exists()
    assert not (dest / "foo").exists()


def test_eng_skill_without_name_uses_folder(tmp):
    eng = tmp / "eng"
    make_skill(eng, "skills/handoff", "")
    assert "handoff" in sync.engineering_names(eng)


def test_mirror_flattens_and_drops_symlinks(tmp):
    s = make_skill(tmp, "up/a/b/s", "s")
    (s / "link").symlink_to(s / "SKILL.md")
    dest = tmp / "dest"
    (dest / "old").mkdir(parents=True)
    sync.mirror([s], dest)
    assert (dest / "s/SKILL.md").exists()
    assert not any(p.is_symlink() for p in dest.rglob("*"))
    assert not (dest / "old").exists()


def test_missing_manifest_fails(tmp):
    try:
        sync.upstream_skills(tmp, ".claude-plugin/plugin.json")
    except SystemExit as e:
        assert str(e.code).startswith("::error::")
    else:
        raise AssertionError("expected SystemExit")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        with tempfile.TemporaryDirectory() as d:
            t(Path(d))
    print(f"ok {len(tests)} tests")
