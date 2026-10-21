"""Build and publish the TestBudget GitHub check run.

The payload builders are plain functions over a plan dict (the plan.json
contract), so they can be tested without the network. ``publish_check_run``
sends them with an injectable ``request`` function.
"""

from __future__ import annotations

import json
import os
import urllib.request

API = "https://api.github.com"
CHECK_NAME = "TestBudget"
MAX_ANNOTATIONS = 50
MAX_TEXT = 60000
REQUIRED = (
    "sha",
    "risk_level",
    "budget_s",
    "selected",
    "skipped",
    "catch_rate_estimate",
)


def validate_plan(plan: dict) -> None:
    """Raise ValueError if the plan is missing a key from the plan.json contract."""
    missing = [key for key in REQUIRED if key not in plan]
    if missing:
        raise ValueError("plan is missing: " + ", ".join(missing))


def test_file(test_id: str) -> str:
    """Return the file part of a pytest (path::name) or Playwright (file › title) ID."""
    for separator in ("::", " › "):
        if separator in test_id:
            return test_id.split(separator)[0]
    return test_id


def build_summary(plan: dict) -> str:
    """Return the markdown summary: budget, risk, catch rate and counts."""
    validate_plan(plan)
    used = sum(t.get("duration_s", 0.0) for t in plan["selected"])
    rate = plan["catch_rate_estimate"]
    rate_text = "unknown" if rate is None else f"{rate:.0%}"
    return "\n".join(
        [
            f"**Risk level:** {plan['risk_level']}",
            f"**Budget:** {plan['budget_s']:.0f}s (planned run time {used:.1f}s)",
            f"**Historical catch rate:** {rate_text}",
            f"**Tests run:** {len(plan['selected'])}",
            f"**Tests skipped:** {len(plan['skipped'])}",
        ]
    )


def build_text(plan: dict) -> str:
    """Return the detail text: tests run with reasons, tests skipped with skip debt."""
    validate_plan(plan)
    lines = ["### Tests run", ""]
    for t in plan["selected"]:
        lines.append(
            f"- `{t['test_id']}` ({t.get('duration_s', 0.0):.1f}s): {t.get('reason', '')}"
        )
    if not plan["selected"]:
        lines.append("- none")
    lines += ["", "### Tests skipped", ""]
    for t in plan["skipped"]:
        lines.append(
            f"- `{t['test_id']}`: {t.get('skip_reason', 'not selected')} "
            f"(skip debt {t.get('skip_debt', 0)})"
        )
    if not plan["skipped"]:
        lines.append("- none")
    return "\n".join(lines)[:MAX_TEXT]


def build_annotations(plan: dict) -> list[dict]:
    """One annotation per skipped test, on its test file; warning if it has skip debt."""
    validate_plan(plan)
    annotations = []
    for t in plan["skipped"]:
        debt = t.get("skip_debt", 0)
        annotations.append(
            {
                "path": test_file(t["test_id"]),
                "start_line": 1,
                "end_line": 1,
                "annotation_level": "warning" if debt > 0 else "notice",
                "title": f"Skipped (debt {debt})",
                "message": f"{t['test_id']} skipped: {t.get('skip_reason', 'not selected')}",
            }
        )
    return annotations


def page_annotations(
    annotations: list[dict], size: int = MAX_ANNOTATIONS
) -> list[list[dict]]:
    """Split annotations into pages of at most ``size`` (the API limit is 50 per request)."""
    if size < 1:
        raise ValueError("page size must be at least 1")
    if not annotations:
        return [[]]
    return [annotations[i : i + size] for i in range(0, len(annotations), size)]


def build_payloads(plan: dict, name: str = CHECK_NAME) -> list[dict]:
    """Return the request bodies: the first creates the check run, the rest add pages."""
    validate_plan(plan)
    pages = page_annotations(build_annotations(plan))
    title = f"{len(plan['selected'])} run, {len(plan['skipped'])} skipped"
    summary = build_summary(plan)
    text = build_text(plan)
    outputs = [
        {"title": title, "summary": summary, "text": text, "annotations": page}
        for page in pages
    ]
    first = {
        "name": name,
        "head_sha": plan["sha"],
        "status": "completed",
        "conclusion": "neutral",
        "output": outputs[0],
    }
    return [first] + [{"output": output} for output in outputs[1:]]


def get_token(env: dict | None = None) -> str:
    """Return GITHUB_TOKEN or raise RuntimeError with a clear message."""
    environment = os.environ if env is None else env
    token = environment.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return token


def _http(method: str, url: str, token: str, body: dict | None = None) -> dict:
    """Send one GitHub API request and return the decoded JSON."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def publish_check_run(plan: dict, repo: str, token: str, request=_http) -> int:
    """Create the check run, or update the existing one for this SHA. Returns its id."""
    payloads = build_payloads(plan)
    base = f"{API}/repos/{repo}"
    found = request(
        "GET",
        f"{base}/commits/{plan['sha']}/check-runs?check_name={CHECK_NAME}",
        token,
        None,
    )
    existing = found.get("check_runs", [])
    if existing:
        run_id = existing[0]["id"]
        first = {k: v for k, v in payloads[0].items() if k != "head_sha"}
        request("PATCH", f"{base}/check-runs/{run_id}", token, first)
    else:
        run_id = request("POST", f"{base}/check-runs", token, payloads[0])["id"]
    for extra in payloads[1:]:
        request("PATCH", f"{base}/check-runs/{run_id}", token, extra)
    return run_id
