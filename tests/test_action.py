from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def test_action_is_composite_with_both_modes():
    action = load("action.yml")
    assert action["runs"]["using"] == "composite"
    assert "mode" in action["inputs"]
    conditions = " ".join(str(s.get("if", "")) for s in action["runs"]["steps"])
    assert "plan" in conditions and "ingest" in conditions


def test_action_caches_history_with_cache_actions():
    uses = [s.get("uses", "") for s in load("action.yml")["runs"]["steps"]]
    assert any(u.startswith("actions/cache/restore") for u in uses)
    assert any(u.startswith("actions/cache/save") for u in uses)


def test_action_rejects_unknown_mode():
    first = load("action.yml")["runs"]["steps"][0]["run"]
    assert "exit 1" in first and "mode must be" in first


def test_workflow_runs_on_pull_requests_and_uses_local_action():
    workflow = load(".github/workflows/testbudget.yml")
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers
    steps = workflow["jobs"]["testbudget"]["steps"]
    assert any(s.get("uses") == "./" for s in steps)


def test_action_installs_from_its_own_path_not_the_callers_workspace():
    steps = load("action.yml")["runs"]["steps"]
    install = next(s for s in steps if s.get("name") == "Install TestBudget")["run"]
    assert "github.action_path" in install
    assert "github.workspace" not in install
