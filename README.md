# mattpocock-skills

This plugin is the delta from `accelerate-data/engineering-skills`. It contains every skill in the `mattpocock/skills` plugin manifest, except the skills whose name `engineering-skills` already ships. The sync computes this list fresh on every run.

Slash references such as `/handoff` resolve to the `engineering-skills` versions, because this plugin does not ship those skills.

## Skills

<!-- skills:start -->
| Skill | Invocation |
| --- | --- |
| ask-matt | user-only |
| code-review | user-only |
| codebase-design | user-only |
| diagnosing-bugs | model |
| domain-modeling | model |
| grill-me | user-only |
| grilling | model |
| implement | user-only |
| implement-spec | user-only |
| improve-codebase-architecture | user-only |
| pr | model |
| prototype | model |
| research | model |
| retro | user-only |
| setup-matt-pocock-skills | user-only |
| tdd | user-only |
| teach | user-only |
| to-questionnaire | user-only |
| to-spec | user-only |
| to-tickets | user-only |
| triage | user-only |
| wait-what | user-only |
| wayfinder | user-only |
| wizard | model |
| writing-for-agents | model |
<!-- skills:end -->

## User-only skills

Some skills run only when you call them by name. The model does not start them by itself. Upstream marks some skills this way already. The `user_only` list in `sync.toml` adds more skills to that set. For each listed skill, the sync sets `disable-model-invocation: true` in `SKILL.md`, and `allow_implicit_invocation: false` in `agents/openai.yaml` when that file exists. The table shows the result, read from each `SKILL.md`.

## Weekly sync

A GitHub workflow runs `scripts/sync.py` every week. The script clones `mattpocock/skills` and `engineering-skills`, rebuilds `skills/`, and updates this table. Each skill folder has a `NOTICE` file with the upstream commit. If the result differs from `main`, the workflow opens a pull request. If nothing changed, it opens no pull request.

Run the sync by hand with `python3 scripts/sync.py`. Run the checks with `python3 scripts/sync.py --check`. Run the tests with `python3 scripts/test_sync.py`.

## Install

```bash
claude plugin install mattpocock-skills@ad-internal-marketplace
```

The marketplace repository is `accelerate-data/plugin-marketplace`.

## License and attribution

The skills are by Matt Pocock and come from https://github.com/mattpocock/skills under the MIT license. See `LICENSE`.
