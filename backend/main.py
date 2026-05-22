from __future__ import annotations
from dotenv import load_dotenv; load_dotenv()

import base64
import json
import os
import re
import urllib.parse
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Body
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

from backend.artifact_client import trigger_build, get_pipeline_result
from backend.models import (
    BranchRecord,
    BuildFieldUpdate,
    BuildRecord,
    ExportFeishuRequest,
    IssueAnalysisRecord,
    ModelItem,
    PRRecord,
    SendRequest,
    TLMRecord,
    TtcUpdate,
    VersionRecord,
)

# ── persistent storage ─────────────────────────────────────────────────────
DATA_FILE = Path(__file__).parent / "data.json"
_data_lock = threading.Lock()  # protects entire read-modify-write cycle

# Default models only for the legacy 莲花山 ADAS E2E AES context
_LEGACY_CTX = "lhs__adas__e2e-aes"

# ── Feishu OAuth ────────────────────────────────────────────────────────────
FEISHU_OAUTH_APP_ID = os.environ.get("FEISHU_OAUTH_APP_ID", "YOUR_FEISHU_OAUTH_APP_ID")
FEISHU_OAUTH_APP_SECRET = os.environ.get("FEISHU_OAUTH_APP_SECRET", "YOUR_FEISHU_OAUTH_APP_SECRET")
FEISHU_OAUTH_REDIRECT_URI = os.environ.get("FEISHU_OAUTH_REDIRECT_URI", "http://YOUR_SERVER_IP:8000/auth/feishu/callback")
_DEFAULT_MODELS = [
    {"id": "model_sz26", "name": "SZ26"},
    {"id": "model_mr26", "name": "MR26"},
    {"id": "model_qzh",  "name": "QZH"},
    {"id": "model_sf",   "name": "SF"},
    {"id": "model_ur",   "name": "UR"},
]


def _load_data() -> dict:
    """Read-only load, no lock. For GET endpoints that never write."""
    data: dict = {}
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.setdefault("contexts", {})
    return data


@contextmanager
def _edit_data():
    """Atomic read-modify-write. Holds _data_lock for entire cycle."""
    with _data_lock:
        data: dict = {}
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data.setdefault("contexts", {})
        yield data
        tmp_file = DATA_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_file.replace(DATA_FILE)  # atomic: readers never see a truncated file


def _backup_data() -> None:
    """备份当前 data.json，保留最近 30 天。"""
    try:
        backup_dir = DATA_FILE.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"data_{ts}.json"
        import shutil
        shutil.copy2(DATA_FILE, backup_path)
        # 清理 30 天前的备份
        cutoff = datetime.now() - timedelta(days=30)
        for f in backup_dir.glob("data_*.json"):
            try:
                dt = datetime.strptime(f.stem[5:], "%Y%m%d_%H%M%S")
                if dt < cutoff:
                    f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _sync_in_progress_builds() -> None:
    """扫描所有 context 下 status=构建中 但无 final_version 的构建，主动查 pipeline 状态并写入。"""
    data = _load_data()
    pending = []  # [(ctx_key, model_id, build_id, pipeline_url)]
    for ctx_key, ns in data.get("contexts", {}).items():
        for model_id, builds in ns.get("builds", {}).items():
            for b in builds:
                if (
                    b.get("pipeline_url")
                    and not b.get("final_version")
                    and b.get("status") == "构建中"
                ):
                    pending.append((ctx_key, model_id, b["id"], b["pipeline_url"]))

    for ctx_key, model_id, build_id, pipeline_url in pending:
        try:
            result = get_pipeline_result(pipeline_url)
        except Exception:
            continue  # token 失效或网络错误，跳过这条，下次再试

        if result["status"] == "success":
            with _edit_data() as d:
                ns = _ctx(d, ctx_key)
                b = next(
                    (x for x in ns.get("builds", {}).get(model_id, []) if x["id"] == build_id),
                    None,
                )
                if b and not b.get("final_version"):
                    b["final_version"] = result.get("package", "")
                    if b.get("status") == "构建中":
                        b["status"] = "成功"
        elif result["status"] == "failed":
            with _edit_data() as d:
                ns = _ctx(d, ctx_key)
                b = next(
                    (x for x in ns.get("builds", {}).get(model_id, []) if x["id"] == build_id),
                    None,
                )
                if b and b.get("status") == "构建中":
                    b["status"] = "失败"


def _build_sync_loop() -> None:
    """后台线程：每 30 秒主动同步一次所有未完成构建的 pipeline 状态。"""
    while True:
        time.sleep(10)
        try:
            _sync_in_progress_builds()
        except Exception:
            pass


def _daily_backup_loop() -> None:
    """后台线程：每天凌晨 2 点执行一次备份。"""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        time.sleep((next_run - now).total_seconds())
        _backup_data()


def _ctx(data: dict, ctx: str) -> dict:
    """Return (and lazily create) the namespace dict for this context."""
    ns = data["contexts"].setdefault(ctx, {
        "models": [], "builds": {}, "branches": {},
        "pr_records": {}, "issue_analysis": {}, "version_records": {}, "tlm_records": {},
        "trash": [],
    })
    # Migrate: ensure keys exist in older namespaces
    ns.setdefault("trash", [])
    ns.setdefault("ttc", {})
    return ns


app = FastAPI()

# 启动每日凌晨 2 点备份的后台线程
threading.Thread(target=_daily_backup_loop, daemon=True, name="daily-backup").start()
# 启动后台构建状态同步线程（每 30 秒主动扫描，防止前端轮询中断导致不同步）
threading.Thread(target=_build_sync_loop, daemon=True, name="build-sync").start()

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
CALIB_OUTPUT_DIR = Path(__file__).parent / "ttc_calib_output"


@app.get("/")
def index():
    return FileResponse(
        FRONTEND_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/send")
async def send(req: SendRequest):
    pipeline_url = ""
    artifact_error = ""
    try:
        artifact_result = trigger_build(
            base_package=req.base_version,
            modules=[m.dict() for m in req.modules],
            remark=req.remark,
        )
        pipeline_url = artifact_result.get("task_link", "")
    except Exception as e:
        artifact_error = str(e)

    return {
        "ok": True,
        "pipeline_url": pipeline_url,
        "artifact_error": artifact_error,
    }


@app.get("/api/poll-final-version/{model_id}/{build_id}")
def poll_final_version(
    model_id: str,
    build_id: str,
    ctx: str = Query(_LEGACY_CTX),
):
    # Read-only check first (outside lock)
    data = _load_data()
    ns = _ctx(data, ctx)
    builds = ns.get("builds", {}).get(model_id, [])
    build = next((b for b in builds if b["id"] == build_id), None)
    if not build:
        return {"found": False, "error": "Build not found"}

    if build.get("final_version"):
        return {"found": True, "final_version": build["final_version"], "already_set": True}

    pipeline_url = build.get("pipeline_url", "")
    if not pipeline_url:
        return {"found": False, "error": "No pipeline URL"}

    # External HTTP call outside the lock
    try:
        result = get_pipeline_result(pipeline_url)
    except Exception as e:
        return {"found": False, "error": str(e)}

    if result["status"] == "success":
        package_name = result.get("package", "")
        with _edit_data() as data:
            ns = _ctx(data, ctx)
            b = next((x for x in ns.get("builds", {}).get(model_id, []) if x["id"] == build_id), None)
            if b:
                b["final_version"] = package_name
                if b.get("status") == "构建中":
                    b["status"] = "成功"
        return {"found": True, "final_version": package_name}

    if result["status"] == "failed":
        with _edit_data() as data:
            ns = _ctx(data, ctx)
            b = next((x for x in ns.get("builds", {}).get(model_id, []) if x["id"] == build_id), None)
            if b and b.get("status") == "构建中":
                b["status"] = "失败"
        return {"found": False, "pipeline_failed": True}

    return {"found": False}


@app.get("/api/devops-pr-status")
async def get_devops_pr_status(url: str, pat: str = ""):
    """Fetch PR status from Azure DevOps and map to Active/Done."""
    m = re.match(
        r"https://devops\.momenta\.works/([^/]+)/([^/]+)/_git/([^/]+)/pullrequest/(\d+)",
        url.strip(),
    )
    if not m:
        raise HTTPException(status_code=400, detail="Invalid Azure DevOps PR URL")
    org, project, repo, pr_id = m.groups()
    api_url = (
        f"https://devops.momenta.works/{org}/{project}/_apis/git/repositories"
        f"/{repo}/pullrequests/{pr_id}?api-version=6.0"
    )
    headers: dict = {"Accept": "application/json"}
    effective_pat = pat or os.environ.get("DEVOPS_PAT", "")
    if effective_pat:
        token = base64.b64encode(f":{effective_pat}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    try:
        import httpx
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(api_url, headers=headers)
        if resp.status_code == 401:
            return {"error": "unauthorized"}
        resp.raise_for_status()
        raw = resp.json().get("status", "")
        if raw in ("completed", "abandoned"):
            return {"status": "Done"}
        return {"status": "Active"}
    except Exception as e:
        return {"error": str(e)}


# ── portal config ────────────────────────────────────────────────────────────

@app.get("/api/portal-config")
def get_portal_config():
    data = _load_data()
    return data.get("portal_config", {})


@app.post("/api/portal-config")
async def save_portal_config(request: Request):
    body = await request.json()
    with _edit_data() as data:
        data["portal_config"] = body
    return {"ok": True}


# ── models ───────────────────────────────────────────────────────────────────

@app.get("/api/models")
def get_models(ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    ns = _ctx(data, ctx)
    models = ns.get("models", [])
    if not models and ctx == _LEGACY_CTX:
        models = _DEFAULT_MODELS[:]
    return models


@app.post("/api/models")
def save_models_endpoint(models: List[ModelItem], ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ctx(data, ctx)["models"] = [m.dict() for m in models]
    return {"ok": True}


@app.get("/api/recent-releases")
def get_recent_releases(limit: int = Query(30)):
    """Return the most recent builds across ALL contexts and models, sorted by created_at."""
    data = _load_data()
    mountains = data.get("portal_config", {}).get("mountains", [])
    mountain_name_map = {m["id"]: m["name"] for m in mountains}
    results = []
    for ctx_id, ns in data.get("contexts", {}).items():
        mountain_id = ctx_id.split("__")[0]
        mountain_name = mountain_name_map.get(mountain_id, mountain_id)
        model_name_map = {m["id"]: m["name"] for m in ns.get("models", [])}
        for model_id, builds in ns.get("builds", {}).items():
            model_name = model_name_map.get(model_id, "")
            for b in builds:
                if not b.get("is_manual") and b.get("created_at"):
                    results.append({
                        "ctx": ctx_id,
                        "model_id": model_id,
                        "mountain_name": mountain_name,
                        "model_name": model_name,
                        "final_version": b.get("final_version", ""),
                        "base_version": b.get("base_version", ""),
                        "status": b.get("status", ""),
                        "created_at": b.get("created_at", ""),
                        "remark": b.get("remark", ""),
                        "creator": b.get("creator", ""),
                    })
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results[:limit]


# ── builds ────────────────────────────────────────────────────────────────────

@app.get("/api/builds/{model_id}")
def get_builds(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _ctx(data, ctx).get("builds", {}).get(model_id, [])


@app.post("/api/builds/{model_id}")
def add_build(model_id: str, build: BuildRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        ns.setdefault("builds", {}).setdefault(model_id, []).insert(0, build.dict())
    return {"ok": True}


@app.patch("/api/builds/{model_id}/{build_id}")
def update_build(model_id: str, build_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        builds = _ctx(data, ctx).get("builds", {}).get(model_id, [])
        b = next((x for x in builds if x["id"] == build_id), None)
        if not b:
            raise HTTPException(status_code=404, detail="Build not found")
        b[update.field] = update.value
    return {"ok": True}


@app.delete("/api/builds/{model_id}/{build_id}")
def delete_build(model_id: str, build_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        ns_builds = _ctx(data, ctx).get("builds", {})
        if model_id in ns_builds:
            ns_builds[model_id] = [b for b in ns_builds[model_id] if b["id"] != build_id]
    return {"ok": True}


@app.delete("/api/builds/{model_id}")
def clear_builds(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ctx(data, ctx).setdefault("builds", {})[model_id] = []
    return {"ok": True}


# ── generic record helpers ────────────────────────────────────────────────────

def _get_col(ns: dict, key: str, model_id: str) -> list:
    return ns.get(key, {}).get(model_id, [])


def _ensure_col(ns: dict, key: str, model_id: str) -> list:
    ns.setdefault(key, {}).setdefault(model_id, [])
    return ns[key][model_id]


def _patch_rec(ns: dict, key: str, model_id: str, record_id: str,
               update: BuildFieldUpdate, label: str):
    """Mutate record in-place. Must be called inside _edit_data() block."""
    records = _get_col(ns, key, model_id)
    r = next((x for x in records if x["id"] == record_id), None)
    if not r:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    r[update.field] = update.value


def _delete_rec(ns: dict, key: str, model_id: str, record_id: str):
    """Remove record. Must be called inside _edit_data() block."""
    col = ns.get(key, {})
    if model_id in col:
        col[model_id] = [r for r in col[model_id] if r["id"] != record_id]


# ── branches ─────────────────────────────────────────────────────────────────

@app.get("/api/branches/{model_id}")
def get_branches(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _get_col(_ctx(data, ctx), "branches", model_id)


@app.post("/api/branches/{model_id}")
def add_branch(model_id: str, record: BranchRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ensure_col(_ctx(data, ctx), "branches", model_id).insert(0, record.dict())
    return {"ok": True}


@app.patch("/api/branches/{model_id}/{record_id}")
def update_branch(model_id: str, record_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _patch_rec(_ctx(data, ctx), "branches", model_id, record_id, update, "Branch record")
    return {"ok": True}


@app.delete("/api/branches/{model_id}/{record_id}")
def delete_branch(model_id: str, record_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _delete_rec(_ctx(data, ctx), "branches", model_id, record_id)
    return {"ok": True}


@app.post("/api/sync-adas-branches/{model_id}")
def sync_adas_branches(model_id: str, module: str = Query("adas_planning"), ctx: str = Query(_LEGACY_CTX)):
    """Sync branches for a given module (adas_planning or cp_planning) from builds + version_records."""
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        col = _ensure_col(ns, "branches", model_id)

        # Collect each branch's most recent source record date
        branch_latest: dict[str, str] = {}
        for build in ns.get("builds", {}).get(model_id, []):
            ts = build.get("created_at", "")
            for mod in build.get("modules", []):
                if mod.get("name") == module and mod.get("branch"):
                    br = mod["branch"]
                    if ts > branch_latest.get(br, ""):
                        branch_latest[br] = ts
        for vr in ns.get("version_records", {}).get(model_id, []):
            ts = vr.get("created_at", "")
            for mod in vr.get("modules", []):
                if mod.get("name") == module and mod.get("branch"):
                    br = mod["branch"]
                    if ts > branch_latest.get(br, ""):
                        branch_latest[br] = ts

        seen = set(branch_latest.keys())
        # Remove stale entries for this module
        col[:] = [b for b in col if b.get("module") != module or b.get("branch") in seen]
        # Add new / update existing
        existing = {b["branch"]: b for b in col if b.get("module") == module}
        for branch, ts in branch_latest.items():
            if module == "cp_planning":
                repo, url_path = "maf_planning", "path=%2F&"
            elif module == "camera_detection":
                repo, url_path = "mpa", "path=%2F&"
            else:
                repo, url_path = module, ""
            url = f"https://devops.momenta.works/Momenta/maf/_git/{repo}?{url_path}version=GB{urllib.parse.quote(branch, safe='')}&_a=history"
            if branch in existing:
                existing[branch]["last_used_at"] = ts
                existing[branch]["url"] = url
            else:
                safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", branch)
                col.append({
                    "id": f"br_auto_{module}_{safe_id}",
                    "module": module,
                    "branch": branch,
                    "url": url,
                    "remark": "",
                    "status": "使用中",
                    "last_used_at": ts,
                })

        # Sort: this module's entries by last_used_at desc, others stay in place
        this_mod = sorted([b for b in col if b.get("module") == module], key=lambda b: b.get("last_used_at", ""), reverse=True)
        others   = [b for b in col if b.get("module") != module]
        col[:] = this_mod + others
    return {"ok": True}


@app.post("/api/sync-pr-branches/{model_id}")
def sync_pr_branches(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    """Auto-sync dev_branch + dev_pr_url for each PR record from build history."""
    sync_module = "adas_planning"
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        pr_col    = _ensure_col(ns, "pr_records", model_id)
        tlm_col   = _get_col(ns, "tlm_records", model_id)
        builds    = ns.get("builds", {}).get(model_id, [])
        branch_col = _get_col(ns, "branches", model_id)

        tlm_by_id = {r["id"]: r for r in tlm_col}
        branch_url_by_name = {b["branch"]: b.get("url", "") for b in branch_col if b.get("branch")}

        pr_by_tlm = {r["tlm_id"]: r for r in pr_col if r.get("tlm_id")}
        updated = 0
        for tlm in tlm_col:
            tlm_url = tlm.get("tlm_url")
            if not tlm_url:
                continue

            # 找关联该 TLM 的构建记录
            matched = [b for b in builds if tlm_url in b.get("tlm_links", [])]
            sorted_builds = sorted(matched, key=lambda b: b.get("created_at", ""), reverse=True)

            # 从最新到最旧，找第一条含有 adas_planning branch 的构建
            branch = next(
                (m["branch"] for b in sorted_builds for m in b.get("modules", [])
                 if m.get("name") == sync_module and m.get("branch")),
                None
            )

            # 没有关联构建或所有构建都没有 adas_planning，清空开发分支
            if not branch:
                pr = pr_by_tlm.get(tlm["id"])
                if pr and (pr.get("dev_branch") or pr.get("dev_pr_url")):
                    pr["dev_branch"] = ""
                    pr["dev_pr_url"] = ""
                    updated += 1
                continue

            url = branch_url_by_name.get(branch, "")
            pr = pr_by_tlm.get(tlm["id"])
            if pr:
                if pr.get("dev_branch") != branch or pr.get("dev_pr_url") != url:
                    pr["dev_branch"] = branch
                    pr["dev_pr_url"] = url
                    updated += 1
            else:
                new_pr = {"id": f"pr_auto_{tlm['id']}", "tlm_id": tlm["id"], "dev_branch": branch, "dev_pr_url": url,
                          "backflow_r6_pr": "", "backflow_r6_status": "—", "backflow_main_pr": "", "backflow_main_status": "—", "remark": ""}
                pr_col.append(new_pr)
                pr_by_tlm[tlm["id"]] = new_pr
                updated += 1

    return {"ok": True, "updated": updated}


@app.get("/api/debug-pr-sync/{model_id}")
def debug_pr_sync(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    ns = _ctx(data, ctx)
    tlm_col = _get_col(ns, "tlm_records", model_id)
    builds  = ns.get("builds", {}).get(model_id, [])
    result = []
    for tlm in tlm_col:
        tlm_url = tlm.get("tlm_url", "")
        matched = [b for b in builds if tlm_url in b.get("tlm_links", [])]
        branch = None
        if matched:
            latest = max(matched, key=lambda b: b.get("created_at", ""))
            branch = next((m["branch"] for m in latest.get("modules", []) if m.get("name") == "adas_planning" and m.get("branch")), None)
        result.append({"tlm_id": tlm.get("id"), "desc": tlm.get("description"), "tlm_url": tlm_url, "matched_builds": len(matched), "branch": branch})
    return result


# ── pr-records ────────────────────────────────────────────────────────────────

@app.get("/api/pr-records/{model_id}")
def get_pr_records(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _get_col(_ctx(data, ctx), "pr_records", model_id)


@app.post("/api/pr-records/{model_id}")
def add_pr_record(model_id: str, record: PRRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        col = _ensure_col(_ctx(data, ctx), "pr_records", model_id)
        # upsert by tlm_id
        existing = next((r for r in col if r.get("tlm_id") == record.tlm_id), None) if record.tlm_id else None
        if existing:
            existing.update(record.dict())
        else:
            col.append(record.dict())
    return {"ok": True}


@app.patch("/api/pr-records/{model_id}/{record_id}")
def update_pr_record(model_id: str, record_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _patch_rec(_ctx(data, ctx), "pr_records", model_id, record_id, update, "PR record")
    return {"ok": True}


@app.delete("/api/pr-records/{model_id}/{record_id}")
def delete_pr_record(model_id: str, record_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _delete_rec(_ctx(data, ctx), "pr_records", model_id, record_id)
    return {"ok": True}


# ── issue-analysis ────────────────────────────────────────────────────────────

@app.get("/api/issue-analysis/{model_id}")
def get_issue_analysis(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _get_col(_ctx(data, ctx), "issue_analysis", model_id)


@app.post("/api/issue-analysis/{model_id}")
def add_issue_analysis(model_id: str, record: IssueAnalysisRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        col = _ensure_col(_ctx(data, ctx), "issue_analysis", model_id)
        if not any(r.get("id") == record.id for r in col):
            col.insert(0, record.dict())
    return {"ok": True}


@app.patch("/api/issue-analysis/{model_id}/{record_id}")
def update_issue_analysis(model_id: str, record_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _patch_rec(_ctx(data, ctx), "issue_analysis", model_id, record_id, update, "Issue analysis record")
    return {"ok": True}


@app.delete("/api/issue-analysis/{model_id}/{record_id}")
def delete_issue_analysis(model_id: str, record_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _delete_rec(_ctx(data, ctx), "issue_analysis", model_id, record_id)
    return {"ok": True}


# ── ttc-calibration ───────────────────────────────────────────────────────────

_TTC_EMPTY = lambda: {"test_version": "", "conclusion": {}, "detail": {}}


@app.get("/api/ttc/{model_id}")
def get_ttc(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _ctx(data, ctx)["ttc"].get(model_id, _TTC_EMPTY())


@app.patch("/api/ttc/{model_id}")
def update_ttc(model_id: str, update: TtcUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        rec = ns["ttc"].setdefault(model_id, _TTC_EMPTY())
        if update.test_version is not None:
            rec["test_version"] = update.test_version
        for _f in ("dev_branch", "commit_id", "complete_time_1", "complete_time_2",
                   "complete_time_3", "complete_time_4", "complete_time_5", "complete_time_6"):
            _v = getattr(update, _f, None)
            if _v is not None:
                rec[_f] = _v
        if update.section and update.overlap and update.ttc and update.speed:
            cell = rec.setdefault(update.section, {}).setdefault(update.overlap, {}).setdefault(update.ttc, {})
            if update.entries is not None:
                cell[update.speed] = update.entries
            elif update.value is not None:
                cell[update.speed] = update.value
    return {"ok": True}


# ── ttc export to feishu ──────────────────────────────────────────────────────

_WIKI_PARENT = "SIqlwOSUbiOmVKk0EaNcbvTwnqb"
_FS_BASE = "https://open.feishu.cn/open-apis"

@app.post("/api/ttc/{model_id}/export-feishu")
async def export_ttc_feishu(model_id: str, body: ExportFeishuRequest, ctx: str = Query(_LEGACY_CTX)):
    import re as _re, uuid, asyncio
    import requests as _req

    data = _load_data()
    ttc_data = _ctx(data, ctx)["ttc"].get(model_id, _TTC_EMPTY())
    detail   = ttc_data.get("detail", {})
    test_ver = ttc_data.get("test_version", "")

    SPEEDS   = ["130","120","110","100","90","80","70"]
    ROWS     = ["1.5","1.4","1.3","1.2","1.1","1.0","0.9","0.8","0.7","0.6"]
    OVERLAPS = [("重叠率100%","100%"),("重叠率50%","50%"),("重叠率-50%","-50%")]
    FOLDER   = os.environ.get("FEISHU_FOLDER_TOKEN", "YOUR_FEISHU_FOLDER_TOKEN")
    BASE     = "https://open.feishu.cn/open-apis"
    APP_ID   = os.environ.get("FEISHU_APP_ID", "YOUR_FEISHU_APP_ID")
    APP_SEC  = os.environ.get("FEISHU_APP_SECRET", "YOUR_FEISHU_APP_SECRET")

    # 飞书 text_element_style.background_color 枚举（1~10）
    COLOR_GREEN  = 4   # 绿 → all Pass
    COLOR_YELLOW = 3   # 黄 → 混合
    COLOR_RED    = 1   # 红 → all Fail

    def _gen_id():
        return uuid.uuid4().hex[:16]

    def _norm(raw):
        if not raw: return []
        if isinstance(raw, list): return raw
        return [{"value": v, "tag": ""} for v in str(raw).split("\n") if v.strip()]

    def _cell_color(entries):
        if not entries: return 0
        tags = [e.get("tag", "") for e in entries]
        if not any(tags): return 0
        if all(t == "Pass" for t in tags): return COLOR_GREEN
        if all(t and t != "Pass" for t in tags): return COLOR_RED
        return COLOR_YELLOW

    def _parse_inline(text):
        """将 [text](url) 转为飞书 text_run elements，保留超链接。"""
        elements = []
        i, n = 0, len(text)
        while i < n:
            if text[i] == "[":
                m = _re.match(r"\[([^\]]*)\]\((https?://[^)]*)\)", text[i:])
                if m:
                    elements.append({"text_run": {
                        "content": m.group(1),
                        "text_element_style": {"link": {"url": m.group(2)}},
                    }})
                    i += m.end()
                    continue
            j = i + 1
            while j < n and text[j] != "[":
                j += 1
            elements.append({"text_run": {"content": text[i:j]}})
            i = j
        return elements or [{"text_run": {"content": ""}}]

    def _text_block(block_type, text, bold=False):
        bid = _gen_id()
        field = {2: "text", 4: "heading2"}[block_type]
        elems = _parse_inline(text)
        if bold:
            for e in elems:
                e["text_run"].setdefault("text_element_style", {})["bold"] = True
        return bid, {"block_id": bid, "block_type": block_type, field: {"elements": elems}, "children": []}

    def _build_table(overlap_data):
        all_blocks = []
        cell_ids   = []

        def add_cell(content, is_header=False, bg_color=0):
            cell_bid = _gen_id()
            text_bid = _gen_id()
            cell_ids.append(cell_bid)

            if isinstance(content, str):
                elems = _parse_inline(content)
                if is_header:
                    for e in elems:
                        e["text_run"].setdefault("text_element_style", {})["bold"] = True
            else:
                parts = []
                for e in content:
                    val = e.get("value", "")
                    tag = e.get("tag", "")
                    parts.append(val + (f" [{tag}]" if tag else ""))
                elems = _parse_inline(" / ".join(parts)) if parts else [{"text_run": {"content": ""}}]

            if bg_color:
                for e in elems:
                    e["text_run"].setdefault("text_element_style", {})["background_color"] = bg_color
            all_blocks.append({"block_id": cell_bid, "block_type": 32, "table_cell": {}, "children": [text_bid]})
            all_blocks.append({"block_id": text_bid, "block_type": 2, "text": {"elements": elems}, "children": []})

        # 表头行
        add_cell("TTC(s) \\ 车速(kph)", is_header=True)
        for s in SPEEDS:
            add_cell(s, is_header=True)

        # 数据行
        for ttc_val in ROWS:
            row_data = overlap_data.get(ttc_val, {})
            add_cell(ttc_val, is_header=True)
            for speed in SPEEDS:
                entries = _norm(row_data.get(speed))
                add_cell(entries, bg_color=_cell_color(entries))

        table_bid = _gen_id()
        table_block = {
            "block_id": table_bid,
            "block_type": 31,
            "table": {"property": {
                "row_size": 1 + len(ROWS),
                "column_size": 1 + len(SPEEDS),
                "column_width": [140] + [100] * len(SPEEDS),
                "header_row": True,
            }},
            "children": cell_ids,
        }
        return table_bid, [table_block] + all_blocks

    def _hdr(tok):
        return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    try:
        # 1. 获取 token（优先 user token，否则用 app token）
        if body.user_token:
            tok = body.user_token
        else:
            r = _req.post(f"{BASE}/auth/v3/tenant_access_token/internal",
                          json={"app_id": APP_ID, "app_secret": APP_SEC}, timeout=10)
            tok = r.json().get("tenant_access_token", "")
            if not tok:
                return {"ok": False, "error": "获取 app token 失败"}

        # 2. 创建文档
        r2 = _req.post(f"{BASE}/docx/v1/documents", headers=_hdr(tok),
                       json={"title": body.doc_title, "folder_token": FOLDER}, timeout=30)
        d2 = r2.json()
        if d2.get("code", 0) != 0:
            return {"ok": False, "error": f"创建文档失败: {d2.get('msg')}"}
        doc_id  = d2["data"]["document"]["document_id"]
        doc_url = f"https://momenta.feishu.cn/docx/{doc_id}"

        # 3. 构建所有块
        first_ids  = []
        all_blocks = []

        if test_ver:
            bid, b = _text_block(2, f"测试版本：{test_ver}")
            first_ids.append(bid); all_blocks.append(b)

        for label, key in OVERLAPS:
            hid, hb = _text_block(4, label)
            first_ids.append(hid); all_blocks.append(hb)
            tid, tblocks = _build_table(detail.get(key, {}))
            first_ids.append(tid); all_blocks.extend(tblocks)

        # 4. 批量插入（descendant API）
        block_map = {b["block_id"]: b for b in all_blocks}
        descendants = []
        def _collect(bid):
            b = block_map.get(bid)
            if b:
                descendants.append(b)
                for cid in b.get("children", []):
                    _collect(cid)
        for fid in first_ids:
            _collect(fid)

        r3 = _req.post(
            f"{BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/descendant?document_revision_id=-1",
            headers=_hdr(tok),
            json={"children_id": first_ids, "index": -1, "descendants": descendants},
            timeout=60,
        )
        d3 = r3.json()
        if d3.get("code", 0) != 0:
            return {"ok": False, "error": f"插入块失败: {d3.get('msg')} | {r3.text[:300]}"}

        # 5. 设置组织内可读
        _req.patch(
            f"{BASE}/drive/v1/permissions/{doc_id}/public",
            headers=_hdr(tok),
            params={"type": "docx"},
            json={"external_access_entity": "closed", "link_share_entity": "tenant_readable"},
            timeout=10,
        )

        # 6. 转移所有权给 eli.mao
        _req.post(
            f"{BASE}/drive/v1/permissions/{doc_id}/members/transfer_owner?type=docx&need_notification=false",
            headers=_hdr(tok),
            json={"member_type": "openid", "member_id": "ou_a92b343ce73b44d7eda4e4012a4fba31",
                  "remove_old_owner": True, "alive_transfer": False},
            timeout=10,
        )
        return {"ok": True, "url": doc_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── tlm-records ───────────────────────────────────────────────────────────────

@app.get("/api/tlm-records/{model_id}")
def get_tlm_records(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _get_col(_ctx(data, ctx), "tlm_records", model_id)


@app.post("/api/tlm-records/{model_id}")
def add_tlm_record(model_id: str, record: TLMRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ensure_col(_ctx(data, ctx), "tlm_records", model_id).insert(0, record.dict())
    return {"ok": True}


@app.patch("/api/tlm-records/{model_id}/{record_id}")
def update_tlm_record(model_id: str, record_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _patch_rec(_ctx(data, ctx), "tlm_records", model_id, record_id, update, "TLM record")
    return {"ok": True}


@app.delete("/api/tlm-records/{model_id}/{record_id}")
def delete_tlm_record(model_id: str, record_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _delete_rec(_ctx(data, ctx), "tlm_records", model_id, record_id)
    return {"ok": True}


class IdsPayload(BaseModel):
    ids: List[str]

@app.post("/api/tlm-records/{model_id}/reorder")
def reorder_tlm_records(model_id: str, payload: IdsPayload, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        col = _ensure_col(ns, "tlm_records", model_id)
        by_id = {r["id"]: r for r in col}
        reordered = [by_id[i] for i in payload.ids if i in by_id]
        # append any records not in the payload (safety)
        seen = set(payload.ids)
        reordered += [r for r in col if r["id"] not in seen]
        ns["tlm_records"][model_id] = reordered
    return {"ok": True}


# ── trash ─────────────────────────────────────────────────────────────────────

@app.get("/api/trash")
def get_trash(ctx: str = Query(_LEGACY_CTX)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        original = ns.get("trash", [])
        kept = []
        for item in original:
            try:
                deleted_at = datetime.fromisoformat(item["deleted_at"].replace("Z", "+00:00"))
                if deleted_at >= cutoff:
                    kept.append(item)
            except Exception:
                kept.append(item)  # 解析失败的条目保留
        ns["trash"] = kept
    return kept


@app.post("/api/trash")
async def add_to_trash(request: Request, ctx: str = Query(_LEGACY_CTX)):
    item = await request.json()
    with _edit_data() as data:
        _ctx(data, ctx).setdefault("trash", []).insert(0, item)
    return {"ok": True}


@app.delete("/api/trash/{item_id}")
def purge_trash_item(item_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        ns = _ctx(data, ctx)
        ns["trash"] = [x for x in ns.get("trash", []) if x.get("id") != item_id]
    return {"ok": True}


@app.delete("/api/trash")
def clear_trash(ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ctx(data, ctx)["trash"] = []
    return {"ok": True}


# ── version-records ───────────────────────────────────────────────────────────

@app.get("/api/version-records/{model_id}")
def get_version_records(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    data = _load_data()
    return _get_col(_ctx(data, ctx), "version_records", model_id)


@app.post("/api/version-records/{model_id}")
def add_version_record(model_id: str, record: VersionRecord, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _ensure_col(_ctx(data, ctx), "version_records", model_id).insert(0, record.dict())
    return {"ok": True}


@app.patch("/api/version-records/{model_id}/{record_id}")
def update_version_record(model_id: str, record_id: str, update: BuildFieldUpdate, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _patch_rec(_ctx(data, ctx), "version_records", model_id, record_id, update, "Version record")
    return {"ok": True}


@app.delete("/api/version-records/{model_id}/{record_id}")
def delete_version_record(model_id: str, record_id: str, ctx: str = Query(_LEGACY_CTX)):
    with _edit_data() as data:
        _delete_rec(_ctx(data, ctx), "version_records", model_id, record_id)
    return {"ok": True}




@app.get("/auth/feishu/login")
def feishu_login():
    params = urllib.parse.urlencode({
        "client_id": FEISHU_OAUTH_APP_ID,
        "redirect_uri": FEISHU_OAUTH_REDIRECT_URI,
        "response_type": "code",
    })
    return RedirectResponse(f"https://open.feishu.cn/open-apis/authen/v1/authorize?{params}")


@app.get("/auth/feishu/login-sheets")
def feishu_login_sheets():
    params = urllib.parse.urlencode({
        "client_id": FEISHU_OAUTH_APP_ID,
        "redirect_uri": FEISHU_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "drive:drive sheets:spreadsheet sheets:spreadsheet:create",
    })
    return RedirectResponse(f"https://open.feishu.cn/open-apis/authen/v1/authorize?{params}")


# 用 Harz-GPT app 做 OAuth，拿到有 docx:document 权限的用户 token
_HARZ_APP_ID     = os.environ.get("FEISHU_APP_ID", "YOUR_FEISHU_APP_ID")
_HARZ_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_FEISHU_APP_SECRET")

@app.get("/auth/feishu/login-docx")
def feishu_login_docx():
    params = urllib.parse.urlencode({
        "client_id": FEISHU_OAUTH_APP_ID,
        "redirect_uri": FEISHU_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "docx:document drive:drive",
        "state": "docx",
    })
    return RedirectResponse(f"https://open.feishu.cn/open-apis/authen/v1/authorize?{params}")


@app.get("/auth/feishu/callback")
async def feishu_callback(code: str = Query(...), state: str = Query("")):
    import httpx

    _app_id     = FEISHU_OAUTH_APP_ID
    _app_secret = FEISHU_OAUTH_APP_SECRET

    def err(msg):
        return HTMLResponse(
            '<!DOCTYPE html><html><head><meta charset=utf-8></head><body>'
            '<p style="font-family:sans-serif;text-align:center;padding:40px;color:#e05">'
            + '授权失败：' + msg +
            '</p><p style="text-align:center"><button onclick="window.close()">关闭</button></p>'
            '</body></html>'
        )

    async with httpx.AsyncClient(timeout=10) as client:
        r1 = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": _app_id, "app_secret": _app_secret},
        )
        app_token = r1.json().get("tenant_access_token", "")
        if not app_token:
            return err("获取 app_access_token 失败")

        r2 = await client.post(
            "https://open.feishu.cn/open-apis/authen/v1/access_token",
            headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
            json={"grant_type": "authorization_code", "code": code},
        )
        user_access_token = r2.json().get("data", {}).get("access_token", "")
        if not user_access_token:
            return err("换取 user_access_token 失败: " + r2.text[:120])

        r3 = await client.get(
            "https://open.feishu.cn/open-apis/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
        user = r3.json().get("data", {})

    name = user.get("name", "")
    en_name = user.get("en_name", "")
    open_id = user.get("open_id", "")
    if not open_id:
        return err("获取用户信息失败")

    js_name = repr(name)
    js_en_name = repr(en_name)
    js_oid = repr(open_id)
    js_token = repr(user_access_token)
    html = (
        '<!DOCTYPE html><html><head><meta charset=utf-8></head><body>'
        '<script>'
        'if(window.opener){window.opener.postMessage({feishuOwner:{name:'
        + js_name + ',en_name:' + js_en_name + ',open_id:' + js_oid + ',user_token:' + js_token + '}},"*");}'
        'setTimeout(function(){window.close();},800);'
        '</script>'
        '<p style="font-family:sans-serif;text-align:center;padding:40px">授权成功，窗口即将关闭...</p>'
        '</body></html>'
    )
    return HTMLResponse(html)

@app.get("/api/feishu-deliverable")
def get_feishu_deliverable(test_version: str = Query(...)):
    """通过测试版本（包名）查询飞书多维表格中的交付物链接，供前端轮询。"""
    try:
        from .feishu_record_util import fetch_deliverable_links
        links = fetch_deliverable_links(test_version)
        return {"links": links}
    except Exception as e:
        return {"links": [], "error": str(e)}


RPA_MOUNTAIN_MAP = {
    "莲花山": "67fcfb9886ff117e09380c1e",
    "小洋山": "68a2d9f887344b895562469b",
    "天马山": "673c03dca97394411611fab4",
    "白云山": "67ff6566bd7b73ca17b2b839",
    "Harz":   "harz-p4",
}


RPA_MOUNTAIN_SIMPLE = {
    "莲花山": "lhuas",
    "小洋山": "xyangs",
    "天马山": "tmas-p",
    "白云山": "bys",
    "Harz":   "harz-p4",
}


class CreateRPARequest(BaseModel):
    work_item_name: str
    mountain_name: str = ""
    user_key: str = ""


@app.post("/api/create-rpa-requirement")
async def create_rpa_requirement(req: CreateRPARequest):
    import httpx, logging, re
    project_key = RPA_MOUNTAIN_MAP.get(req.mountain_name)
    if not project_key:
        return {"success": False, "message": f"暂不支持该山头：{req.mountain_name}"}

    # ── 优先路径：MCP 创建，creator = user_key ─────────────────────────────
    if req.user_key:
        MCP_KEY = "m-2127104a-3bb6-44b6-abb4-33f0c20f4026"
        mcp_url = f"https://project.feishu.cn/mcp_server/v1?mcpKey={MCP_KEY}&userKey={req.user_key}"
        mcp_body = {
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {
                "name": "create_workitem",
                "arguments": {
                    "project_key": project_key,
                    "work_item_type": "story",
                    "fields": [{"field_key": "name", "field_value": req.work_item_name}],
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                mr = await client.post(mcp_url, json=mcp_body, headers={"Content-Type": "application/json"})
            md = mr.json()
            logging.warning(f"[RPA-mcp] mountain={req.mountain_name} status={mr.status_code} body={md}")
            content_text = ""
            for c in (md.get("result") or {}).get("content") or []:
                content_text += c.get("text", "")
            is_error = (md.get("result") or {}).get("isError", False)
            if not is_error and content_text:
                id_match = re.search(r'\b(\d{8,})\b', content_text)
                work_item_id = id_match.group(1) if id_match else None
                simple_name = RPA_MOUNTAIN_SIMPLE.get(req.mountain_name, "")
                if work_item_id and simple_name:
                    detail_url = f"https://project.feishu.cn/{simple_name}/story/detail/{work_item_id}"
                else:
                    url_match = re.search(r'https://project\.feishu\.cn/\S+/\d+', content_text)
                    detail_url = url_match.group(0) if url_match else None
                if work_item_id:
                    # 把成功使用的 user_key 存入全局池
                    _add_known_user_key(req.user_key)
                    return {"success": True, "work_item_id": work_item_id, "detail_url": detail_url}
            err_msg = content_text or "MCP 创建失败"
            logging.warning(f"[RPA-mcp] 失败: {err_msg}")
            return {"success": False, "message": f"创建失败：{err_msg}"}
        except Exception as e:
            logging.warning(f"[RPA-mcp] 异常: {e}")
            return {"success": False, "message": f"创建失败: {e}"}

    # ── 回退路径：OpenAPI（creator = 服务账号）──────────────────────────────
    payload = {"work_item_name": req.work_item_name, "project_key": project_key}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://rpa.momenta.cn/backend/rocky-robot/api/open-api/story-requirements/create",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        data = resp.json()
        logging.warning(f"[RPA-create] mountain={req.mountain_name} status={data.get('status')} data={data.get('data')}")
        if data.get("status") == 10000:
            d = data.get("data", {})
            detail_url = d.get("detail_url") or d.get("url")
            work_item_id = d.get("id") or d.get("work_item_id")
            return {"success": True, "work_item_id": work_item_id, "detail_url": detail_url}
        return {"success": False, "message": data.get("message", "创建失败")}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/tlm-title-sync")
async def tlm_title_sync(work_item_id: str = Query(...)):
    """从飞书 MCP 拉取 TLM 需求最新标题（无需 user_key，app 级读取）。"""
    import httpx, re
    MCP_KEY = "m-2127104a-3bb6-44b6-abb4-33f0c20f4026"
    USER_KEY = "7605529922928528570"
    TLM_PROJECT_KEY = "65d6c20802cf2c99dcba17b9"
    mcp_url = f"https://project.feishu.cn/mcp_server/v1?mcpKey={MCP_KEY}&userKey={USER_KEY}"
    mcp_body = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_workitem_brief",
            "arguments": {
                "project_key": TLM_PROJECT_KEY,
                "work_item_id": work_item_id,
                "fields": ["name"],
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            mr = await client.post(mcp_url, json=mcp_body, headers={"Content-Type": "application/json"})
        md = mr.json()
        content_text = ""
        for c in (md.get("result") or {}).get("content") or []:
            content_text += c.get("text", "")
        is_error = (md.get("result") or {}).get("isError", False)
        if not is_error and content_text:
            # 尝试解析 JSON
            try:
                obj = json.loads(content_text)
                attr = obj.get("work_item_attribute") or obj
                name = attr.get("work_item_name") or attr.get("name") or (attr.get("fields") or {}).get("name", "")
            except Exception:
                m = re.search(r'"work_item_name"\s*:\s*"([^"]+)"', content_text)
                name = m.group(1) if m else ""
            if name:
                return {"success": True, "title": name}
        return {"success": False, "message": content_text or "未找到标题"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _add_known_user_key(user_key: str):
    """把 user_key 存入 data.json 全局 known_user_keys 池。"""
    if not user_key:
        return
    data = _load_data()
    keys = data.setdefault("known_user_keys", [])
    if user_key not in keys:
        keys.append(user_key)
        save_data(data)


@app.get("/api/rpa-title-sync")
async def rpa_title_sync(rpa_url: str = Query(...)):
    """从飞书 MCP 拉取 RPA 需求最新标题，依次尝试所有已知 user_key。"""
    import httpx, re
    MCP_KEY = "m-2127104a-3bb6-44b6-abb4-33f0c20f4026"
    DEFAULT_USER_KEY = "7605529922928528570"
    PROJECT_KEY_MAP = {
        "lhuas":  "67fcfb9886ff117e09380c1e",
        "xyangs": "68a2d9f887344b895562469b",
        "tmas-p": "673c03dca97394411611fab4",
        "bys":    "67ff6566bd7b73ca17b2b839",
    }
    m = re.search(r'project\.feishu\.cn/([^/]+)/story/detail/(\d+)', rpa_url)
    if not m:
        return {"success": False, "message": "URL格式不匹配"}
    simple_name, work_item_id = m.group(1), m.group(2)
    project_key = PROJECT_KEY_MAP.get(simple_name, simple_name)

    data = _load_data()
    all_keys = list(dict.fromkeys([DEFAULT_USER_KEY] + data.get("known_user_keys", [])))

    mcp_body = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_workitem_brief",
            "arguments": {"project_key": project_key, "work_item_id": work_item_id, "fields": ["name"]},
        },
    }
    last_error = ""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for user_key in all_keys:
                mcp_url = f"https://project.feishu.cn/mcp_server/v1?mcpKey={MCP_KEY}&userKey={user_key}"
                mr = await client.post(mcp_url, json=mcp_body, headers={"Content-Type": "application/json"})
                md = mr.json()
                content_text = ""
                for c in (md.get("result") or {}).get("content") or []:
                    content_text += c.get("text", "")
                is_error = (md.get("result") or {}).get("isError", False)
                if not is_error and content_text:
                    try:
                        obj = json.loads(content_text)
                        attr = obj.get("work_item_attribute") or obj
                        name = attr.get("work_item_name") or attr.get("name") or ""
                    except Exception:
                        m2 = re.search(r'"work_item_name"\s*:\s*"([^"]+)"', content_text)
                        name = m2.group(1) if m2 else ""
                    if name:
                        return {"success": True, "title": name}
                last_error = content_text or "未找到标题"
        return {"success": False, "message": last_error}
    except Exception as e:
        return {"success": False, "message": str(e)}


class CreateTLMRequest(BaseModel):
    work_item_name: str
    fo_roles: List[str] = []
    ppm_roles: List[str] = []
    owner_username: str = ""
    owner_open_id: str = ""
    user_token: str = ""
    user_key: str = ""
    mountain_name: str = ""
    function_id: str = ""


@app.post("/api/create-tlm-requirement")
async def create_tlm_requirement(req: CreateTLMRequest):
    """创建 TLM 需求。有 user_key 时通过飞书项目 MCP server 创建（创建者为用户本人），否则回退 RPA。"""
    import httpx, logging, re

    MCP_KEY = "m-2127104a-3bb6-44b6-abb4-33f0c20f4026"
    TLM_PROJECT_KEY = "65d6c20802cf2c99dcba17b9"

    # ── 优先路径：通过 MCP server 创建，creator = user_key ──────────────
    if req.user_key:
        mcp_url = f"https://project.feishu.cn/mcp_server/v1?mcpKey={MCP_KEY}&userKey={req.user_key}"

        # Build auto-fill fields based on portal context
        _PRODUCT_MAP = {
            "e2e-aes": ("AES",  "f28b7zdqg"),
            "lane-aes": None,
            "slif":    ("SLIF", "gyi1hlnsj"),
        }
        _MOUNTAIN_MAP = {
            "莲花山": "524rgo7x5",
            "小洋山": "小洋山",
            "Mainline": "主线",
            "主线": "主线",
            "Harz": "hzv8c22ux",
        }
        is_cp = req.function_id == "cp"
        extra_fields: list = []
        # 所属模块团队 (select)
        team_option = "qa417x9oq" if is_cp else "ADAS Planing"
        extra_fields.append({"field_key": "field_41d85f", "field_value": team_option})
        # 所属模块 (select)
        module_option = "scunwkqqi" if is_cp else "7a8xx014p"
        extra_fields.append({"field_key": "field_i9foyw", "field_value": module_option})
        # 所属产品 (multi_select)
        prod_info = _PRODUCT_MAP.get(req.function_id)
        if prod_info:
            prod_label, prod_id = prod_info
            extra_fields.append({"field_key": "field_24b40f", "field_value": json.dumps([{"label": prod_label, "option_id": prod_id}])})
        # 所属项目 (multi_select)
        proj_id = _MOUNTAIN_MAP.get(req.mountain_name)
        if proj_id:
            extra_fields.append({"field_key": "field_a42f81", "field_value": json.dumps([{"label": req.mountain_name, "option_id": proj_id}])})
        # 需求描述 (multi_text)
        extra_fields.append({"field_key": "field_ef5a4e", "field_value": req.work_item_name})
        # PPM 角色 (role_owners) — role_key=role_ba5c99，owner=创建者 user_key
        extra_fields.append({
            "field_key": "role_owners",
            "field_value": json.dumps([{"role": "role_ba5c99", "owners": [req.user_key]}]),
        })

        mcp_body = {
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {
                "name": "create_workitem",
                "arguments": {
                    "project_key": TLM_PROJECT_KEY,
                    "work_item_type": "TLM导入",
                    "fields": [{"field_key": "name", "field_value": req.work_item_name}] + extra_fields,
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                mr = await client.post(mcp_url, json=mcp_body, headers={"Content-Type": "application/json"})
            md = mr.json()
            logging.warning(f"[TLM-mcp] user_key={req.user_key} status={mr.status_code} body={md}")
            content_text = ""
            for c in (md.get("result") or {}).get("content") or []:
                content_text += c.get("text", "")
            is_error = (md.get("result") or {}).get("isError", False)
            if not is_error and content_text:
                url_match = re.search(r'https://project\.feishu\.cn/\S+/\d+', content_text)
                id_match  = re.search(r'\b(\d{8,})\b', content_text)
                work_item_id = id_match.group(1) if id_match else None
                detail_url   = url_match.group(0) if url_match else (
                    f"https://project.feishu.cn/mainstream/tlm_requirement/detail/{work_item_id}" if work_item_id else None
                )
                if work_item_id:
                    return {"success": True, "work_item_id": work_item_id, "detail_url": detail_url}
            # user_key 有误时直接报错，不静默回退
            err_msg = content_text or "MCP 创建失败"
            logging.warning(f"[TLM-mcp] 失败: {err_msg}")
            return {"success": False, "message": f"创建失败：{err_msg}"}
        except Exception as e:
            logging.warning(f"[TLM-mcp] 异常: {e}")
            return {"success": False, "message": f"创建失败: {e}"}

    # ── 回退路径：RPA 代理（创建者固定为插件账号） ──────────────────────
    payload: dict = {"work_item_name": req.work_item_name}
    if req.fo_roles:
        payload["fo_roles"] = req.fo_roles
    if req.ppm_roles:
        payload["ppm_roles"] = req.ppm_roles
        payload["owner_roles"] = req.ppm_roles
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://rpa.momenta.cn/backend/rocky-robot/api/open-api/tlm-requirements/create",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        data = resp.json()
    except Exception as e:
        return {"success": False, "message": f"请求失败: {e}"}
    logging.warning(f"[TLM-rpa] payload={payload} status={data.get('status')} data={data.get('data')} msg={data.get('message')}")
    if data.get("status") == 10000:
        d = data.get("data", {})
        work_item_id = d.get("id") or d.get("work_item_id")
        detail_url = d.get("url") or d.get("detail_url") or (
            f"https://project.feishu.cn/mainstream/tlm_requirement/detail/{work_item_id}" if work_item_id else None
        )
        return {"success": True, "work_item_id": work_item_id, "detail_url": detail_url}
    return {"success": False, "message": data.get("message", "创建失败")}


@app.get("/api/debug/tlm-raw-workitem")
async def debug_tlm_raw_workitem(work_item_id: str = Query(default="6931335510")):
    """调用 MCP get_workitem 返回完整字段，用于发现 PPM role 的 field_key。"""
    import httpx
    MCP_KEY = "m-2127104a-3bb6-44b6-abb4-33f0c20f4026"
    USER_KEY = "7605529922928528570"
    TLM_PROJECT_KEY = "65d6c20802cf2c99dcba17b9"
    mcp_url = f"https://project.feishu.cn/mcp_server/v1?mcpKey={MCP_KEY}&userKey={USER_KEY}"
    mcp_body = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_workitem",
            "arguments": {
                "project_key": TLM_PROJECT_KEY,
                "work_item_id": work_item_id,
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            mr = await client.post(mcp_url, json=mcp_body, headers={"Content-Type": "application/json"})
        md = mr.json()
        content_text = ""
        for c in (md.get("result") or {}).get("content") or []:
            content_text += c.get("text", "")
        try:
            parsed = json.loads(content_text)
        except Exception:
            parsed = content_text
        return {"raw_mcp": md, "content_parsed": parsed}
    except Exception as e:
        return {"error": str(e)}


# ── TTC Calibration (curve fitting) ──────────────────────────────────────────

@app.post("/api/ttc/{model_id}/run-calibration")
def run_ttc_calibration(model_id: str, ctx: str = Query(_LEGACY_CTX), body: dict = Body(default={})):
    """启动最小 TTC 标定（Steps 3-7），异步后台执行。"""
    from backend.ttc_calib_runner import start as _calib_start
    data = _load_data()
    ttc_data = _ctx(data, ctx)["ttc"].get(model_id, _TTC_EMPTY())
    detail = ttc_data.get("detail", {})
    if not detail:
        raise HTTPException(status_code=400, detail="当前车型暂无测试详细数据")
    keycloak_user = body.get("keycloak_user") or None
    keycloak_password = body.get("keycloak_password") or None
    job_key = _calib_start(model_id, detail, ctx, keycloak_user=keycloak_user, keycloak_password=keycloak_password)
    return {"ok": True, "job_key": job_key}


@app.get("/api/ttc/{model_id}/calibration-status")
def get_ttc_calibration_status(model_id: str, ctx: str = Query(_LEGACY_CTX)):
    """查询标定任务进度。"""
    from backend.ttc_calib_runner import get_status as _calib_status
    return _calib_status(model_id, ctx)


@app.get("/ttc-calib/{ctx}/{model_id}/{overlap}/{filename}")
def serve_calib_html(ctx: str, model_id: str, overlap: str, filename: str):
    """提供生成的标定 HTML 文件。"""
    # 安全校验：只允许 .html 文件，禁止路径穿越
    if not filename.endswith(".html") or ".." in filename or ".." in overlap:
        raise HTTPException(status_code=400, detail="非法文件名")
    path = CALIB_OUTPUT_DIR / ctx / model_id / overlap / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件尚未生成")
    return FileResponse(path, media_type="text/html")
