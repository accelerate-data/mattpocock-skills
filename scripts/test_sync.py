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


def make_folded(root: Path, name: str, extra: str = "") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: >\n  line one\n  line two\n{extra}---\nbody\n")
    return d


def snapshot(root: Path) -> dict:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_patch_inserts_after_opening_fence(tmp):
    d = make_folded(tmp, "a")
    sync.patch_user_only(tmp, ["a"])
    lines = (d / "SKILL.md").read_text().splitlines()
    assert lines[1] == "disable-model-invocation: true"
    assert lines[2:6] == ["name: a", "description: >", "  line one", "  line two"]


def test_patch_is_idempotent(tmp):
    d = make_folded(tmp, "a")
    (d / "agents").mkdir()
    (d / "agents/openai.yaml").write_text("interface:\n  display_name: \"A\"\n")
    sync.patch_user_only(tmp, ["a"])
    first = snapshot(tmp)
    sync.patch_user_only(tmp, ["a"])
    assert snapshot(tmp) == first


def test_patch_respects_existing_flag(tmp):
    d = make_folded(tmp, "a", "disable-model-invocation: false\n")
    sync.patch_user_only(tmp, ["a"])
    text = (d / "SKILL.md").read_text()
    assert text.count("disable-model-invocation") == 1
    assert "disable-model-invocation: true" in text


def test_openai_yaml_existing_policy(tmp):
    d = make_folded(tmp, "a")
    (d / "agents").mkdir()
    y = d / "agents/openai.yaml"
    y.write_text("interface:\n  x: 1\npolicy:\n  allow_implicit_invocation: true\n")
    sync.patch_user_only(tmp, ["a"])
    t = y.read_text()
    assert "allow_implicit_invocation: false" in t and "true" not in t
    assert t.count("policy:") == 1
    y.write_text("interface:\n  x: 1\n")
    sync.patch_user_only(tmp, ["a"])
    assert y.read_text().endswith("policy:\n  allow_implicit_invocation: false\n")
    y.write_text("policy:\n  other: 1\n")
    sync.patch_user_only(tmp, ["a"])
    t = y.read_text()
    assert t.count("policy:") == 1 and "allow_implicit_invocation: false" in t
    b = make_folded(tmp, "b")
    sync.patch_user_only(tmp, ["b"])
    assert not (b / "agents").exists()


def test_missing_user_only_warns(tmp):
    assert sync.patch_user_only(tmp, ["gone"]) == ["user_only: gone not present"]


def test_previous_sha(tmp):
    assert sync.read_previous_sha(tmp) == "none"
    d = make_folded(tmp, "a")
    sync.write_notice(d, "skills/x/a", "abc123", ["user-only"])
    assert sync.read_previous_sha(tmp) == "abc123"
    assert "  - user-only" in (d / "NOTICE").read_text()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        with tempfile.TemporaryDirectory() as d:
            t(Path(d))
    print(f"ok {len(tests)} tests")
