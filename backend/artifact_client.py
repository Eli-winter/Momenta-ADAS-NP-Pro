"""
Wrapper around artifact-skill's create_artifact_by_branch.
Directly calls Momenta CI API to trigger builds and return pipeline links.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ARTIFACT_SKILL_SCRIPTS = Path.home() / ".agents" / "skills" / "artifact-skill" / "scripts"


def _ensure_path() -> None:
    p = str(ARTIFACT_SKILL_SCRIPTS)
    if p not in sys.path:
        sys.path.insert(0, p)


def trigger_build(
    base_package: str,
    modules: list[dict],
    remark: str = "",
) -> dict:
    """
    Trigger a CI artifact build.

    modules: list of {"name": str, "branch": str, "commit_id": str}
    Returns {"task_link": str, "module_update_info": str}
    Raises on failure.
    """
    _ensure_path()
    from artifact_tools import create_artifact_by_branch  # type: ignore

    skill_modules = [
        {"name": m["name"], "branch": m["branch"], "commit": m.get("commit_id", "")}
        for m in modules
    ]
    result = create_artifact_by_branch(
        base_package=base_package,
        modules=skill_modules,
        remark=remark,
        user_union_id="",
    )
    if not result.get("task_link"):
        msg = result.get("module_update_info") or "未返回 pipeline 链接"
        raise RuntimeError(msg)
    return result


def get_pipeline_result(pipeline_url: str) -> dict:
    """
    Query pipeline variables to determine build outcome.

    Returns:
      {"status": "success", "package": "<name>"}
      {"status": "failed"}
      {"status": "running"}

    Detection rules (from EP pipeline variables API):
      - __flow1_artifacts non-empty  → success
      - any __Activity_XXX_result == False → failed
      - otherwise → running
    """
    m = re.search(r"/tasks/([a-f0-9]+)", pipeline_url)
    if not m:
        return {"status": "running"}
    task_id = m.group(1)

    _ensure_path()
    from artifact_tools import get_keycloak_token  # type: ignore
    import requests  # type: ignore

    token = get_keycloak_token()
    headers = {"Authorization": f"Bearer {token}"}

    url = "https://ep.momenta.works/backend/pipeline/api/pipelines/variables/global/list"
    resp = requests.get(url, headers=headers, params={"pipeline_task_id": task_id}, timeout=10)
    resp.raise_for_status()
    variables = resp.json().get("data") or []

    for item in variables:
        vname = item.get("variable_name", "")
        tv = item.get("typed_value", {})
        value = tv.get("value") if isinstance(tv, dict) else tv

        if vname == "__flow1_artifacts" and value and isinstance(value, str) and value.strip():
            return {"status": "success", "package": value.strip()}

        if vname.startswith("__Activity_") and vname.endswith("_result") and value is False:
            return {"status": "failed"}

    return {"status": "running"}


def get_package_name_by_pipeline_task(pipeline_url: str) -> str:
    """Kept for compatibility. Returns package name on success, empty string otherwise."""
    result = get_pipeline_result(pipeline_url)
    return result.get("package", "") if result["status"] == "success" else ""
