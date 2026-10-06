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


def test_report_first_run(tmp):
    r = sync.render_report("none", "abc", set(), {"tdd"}, ["handoff"], [])
    assert "none →" in r and "handoff" in r


def test_readme_markers_required(tmp):
    r = tmp / "README.md"
    r.write_text("no markers\n")
    try:
        sync.update_readme(r, [("a", True)])
    except SystemExit:
        return
    raise AssertionError("expected SystemExit")


def test_readme_table(tmp):
    r = tmp / "README.md"
    r.write_text("x\n<!-- skills:start -->\nold\n<!-- skills:end -->\ny\n")
    sync.update_readme(r, [("tdd", False), ("grilling", True)])
    t = r.read_text()
    assert "| tdd | user-only |" in t and "| grilling | model |" in t
    assert "old" not in t and t.startswith("x\n") and t.endswith("y\n")


def make_root(tmp: Path, v1="1.0.0", v2="1.0.0") -> Path:
    root = tmp / "root"
    for d, v in ((".claude-plugin", v1), (".codex-plugin", v2)):
        (root / d).mkdir(parents=True)
        (root / d / "plugin.json").write_text(json.dumps({"version": v}))
    return root


def test_check_detects_collision_and_version_drift(tmp):
    root = make_root(tmp, "1.0.0", "1.0.1")
    make_skill(root, "skills/handoff", "handoff")
    eng = tmp / "eng"
    make_skill(eng, "skills/handoff", "handoff")
    assert len(sync.check(root, eng)) == 2


def test_engineering_names_ignores_nested(tmp):
    make_skill(tmp / "eng", "skills/x", "x")
    make_skill(tmp / "eng", "skills/x/ref/deep", "deep")
    assert sync.engineering_names(tmp / "eng") == {"x"}


def test_notice_and_readme_reflect_real_changes(tmp):
    import os
    up = make_upstream(tmp, ["engineering/a", "engineering/b", "engineering/c"])
    make_skill(up, "engineering/b", "b", "disable-model-invocation: true\n")
    make_skill(up, "engineering/c", "c", "disable-model-invocation: true\n")
    (up / "LICENSE").write_text("MIT\n")
    eng = tmp / "eng"
    make_skill(eng, "skills/z", "z")
    root = make_root(tmp)
    (root / "sync.toml").write_text(
        '[upstream]\nrepo = "x"\nref = "main"\nmanifest = ".claude-plugin/plugin.json"\n'
        '[engineering]\nrepo = "y"\nref = "main"\n[patches]\nuser_only = ["a", "b"]\n'
    )
    (root / "README.md").write_text("<!-- skills:start -->\n<!-- skills:end -->\n")
    old = os.getcwd()
    os.chdir(root)
    try:
        sync.main(["--upstream-dir", str(up), "--eng-dir", str(eng)])
    finally:
        os.chdir(old)
    t = (root / "README.md").read_text()
    assert "| a | user-only |" in t and "| b | user-only |" in t and "| c | user-only |" in t
    assert "disable-model-invocation" in (root / "skills/a/NOTICE").read_text()
    assert "  - none" in (root / "skills/b/NOTICE").read_text()
    assert "  - none" in (root / "skills/c/NOTICE").read_text()


def test_end_to_end_idempotent(tmp):
    import os
    up = make_upstream(tmp, ["engineering/a", "productivity/handoff"])
    (up / "LICENSE").write_text("MIT\n")
    eng = tmp / "eng"
    make_skill(eng, "skills/handoff", "handoff")
    root = make_root(tmp)
    (root / "sync.toml").write_text(
        '[upstream]\nrepo = "x"\nref = "main"\nmanifest = ".claude-plugin/plugin.json"\n'
        '[engineering]\nrepo = "y"\nref = "main"\n[patches]\nuser_only = ["a"]\n'
    )
    (root / "README.md").write_text("<!-- skills:start -->\n<!-- skills:end -->\n")
    old = os.getcwd()
    os.chdir(root)
    try:
        sync.main(["--upstream-dir", str(up), "--eng-dir", str(eng)])
        first = snapshot(root)
        sync.main(["--upstream-dir", str(up), "--eng-dir", str(eng)])
        assert snapshot(root) == first
        assert sync.main(["--check", "--eng-dir", str(eng)]) == 0
    finally:
        os.chdir(old)
    assert "disable-model-invocation: true" in (root / "skills/a/SKILL.md").read_text()
    assert not (root / "skills/handoff").exists()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        with tempfile.TemporaryDirectory() as d:
            t(Path(d))
    print(f"ok {len(tests)} tests")
