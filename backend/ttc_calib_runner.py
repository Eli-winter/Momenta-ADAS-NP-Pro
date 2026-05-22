"""
TTC 标定后台任务管理器。

从网站 TTC 数据启动 aes-min-ttc-calibration skill 的 Steps 3-7，
通过 subprocess 调用 skill 的 venv Python，解析 STEP:N:msg 进度输出。
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

# skill 路径（Docker 内通过卷挂载）
SKILL_DIR = Path("/root/.agents/skills/aes-min-ttc-calibration")
SKILL_PYTHON = SKILL_DIR / "aes_ttc_venv" / "bin" / "python3"
SKILL_ENTRY = SKILL_DIR / "scripts" / "run_from_website.py"

# HTML 输出存放在 backend/ttc_calib_output/{ctx}/{model_id}/
OUTPUT_BASE = Path(__file__).parent / "ttc_calib_output"

OVERLAP_KEYS = {"100%": "100", "50%": "50", "-50%": "-50"}

# {job_key: {status, step, step_msg, html_urls, error, log}}
_JOBS: Dict[str, dict] = {}
_LOCK = threading.Lock()

STEP_LABELS = {
    0: "获取 ESS Token",
    1: "提取测试记录",
    2: "准备数据",
    3: "创建仿真场景集",
    4: "提交仿真任务",
    5: "等待仿真结果",
    6: "匹配数据",
    7: "曲线拟合与可视化",
    8: "完成",
}


def _job_key(model_id: str, ctx: str) -> str:
    return f"{ctx}__{model_id}"


def _set(job_key: str, **kwargs):
    with _LOCK:
        if job_key in _JOBS:
            _JOBS[job_key].update(kwargs)


def _worker(job_key: str, model_id: str, ttc_detail: dict, ctx: str, username: str,
            keycloak_user: str | None, keycloak_password: str | None):
    output_dir = OUTPUT_BASE / ctx / model_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # 写入 input JSON（供 skill 读取）
    input_json = output_dir / "website_input.json"
    input_json.write_text(json.dumps(ttc_detail, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        str(SKILL_PYTHON),
        str(SKILL_ENTRY),
        "--input-json", str(input_json),
        "--output-dir", str(output_dir),
        "--username", username,
        "--wait-completion",
    ]

    # 凭证优先级：用户传入 > 服务器环境变量
    import os as _os
    sub_env = _os.environ.copy()
    if keycloak_user:
        sub_env["KEYCLOAK_USER"] = keycloak_user
    if keycloak_password:
        sub_env["KEYCLOAK_PASSWORD"] = keycloak_password

    log_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(SKILL_DIR),
            env=sub_env,
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            log_lines.append(line)

            if line.startswith("STEP:"):
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    try:
                        step_num = int(parts[1])
                        step_msg = parts[2]
                        _set(job_key, step=step_num, step_msg=step_msg)
                    except ValueError:
                        pass

        proc.wait()

        if proc.returncode != 0:
            tail = "\n".join(log_lines[-30:])
            raise RuntimeError(f"skill 退出码 {proc.returncode}\n{tail}")

        # 收集生成的 HTML 链接
        html_urls: dict = {}
        for overlap_label, overlap_key in OVERLAP_KEYS.items():
            overlap_dir = output_dir / f"overlap_{overlap_key}"
            orig = overlap_dir / "matched_results_polyline_classification_2d.html"
            adj  = overlap_dir / "matched_results_polyline_adjust_classification_2d.html"
            if orig.exists() or adj.exists():
                html_urls[overlap_label] = {
                    "original": f"/ttc-calib/{ctx}/{model_id}/overlap_{overlap_key}/matched_results_polyline_classification_2d.html" if orig.exists() else None,
                    "adjusted": f"/ttc-calib/{ctx}/{model_id}/overlap_{overlap_key}/matched_results_polyline_adjust_classification_2d.html" if adj.exists() else None,
                }

        _set(job_key, status="done", step=8, step_msg="完成", html_urls=html_urls, log=log_lines)

    except Exception as exc:
        import traceback
        _set(job_key, status="error", error=str(exc), traceback=traceback.format_exc(), log=log_lines)


def start(model_id: str, ttc_detail: dict, ctx: str,
          keycloak_user: str | None = None, keycloak_password: str | None = None) -> str:
    """启动标定任务，返回 job_key。如已有运行中任务则返回其 key（不重复启动）。"""
    key = _job_key(model_id, ctx)
    with _LOCK:
        existing = _JOBS.get(key)
        if existing and existing.get("status") == "running":
            return key
        _JOBS[key] = {
            "status": "running",
            "step": 0,
            "step_msg": "初始化…",
            "html_urls": {},
            "error": None,
            "log": [],
            "started_at": time.time(),
        }

    threading.Thread(
        target=_worker,
        args=(key, model_id, ttc_detail, ctx, keycloak_user or "unknown", keycloak_user, keycloak_password),
        daemon=True,
        name=f"ttc-calib-{model_id}",
    ).start()
    return key


def _scan_html_urls(model_id: str, ctx: str) -> dict:
    """从文件系统扫描已生成的 HTML 文件，返回 html_urls 结构（服务器重启后恢复用）。"""
    output_dir = OUTPUT_BASE / ctx / model_id
    html_urls: dict = {}
    for overlap_label, overlap_key in OVERLAP_KEYS.items():
        overlap_dir = output_dir / f"overlap_{overlap_key}"
        orig = overlap_dir / "matched_results_polyline_classification_2d.html"
        adj  = overlap_dir / "matched_results_polyline_adjust_classification_2d.html"
        if orig.exists() or adj.exists():
            html_urls[overlap_label] = {
                "original": f"/ttc-calib/{ctx}/{model_id}/overlap_{overlap_key}/matched_results_polyline_classification_2d.html" if orig.exists() else None,
                "adjusted": f"/ttc-calib/{ctx}/{model_id}/overlap_{overlap_key}/matched_results_polyline_adjust_classification_2d.html" if adj.exists() else None,
            }
    return html_urls


def get_status(model_id: str, ctx: str) -> dict:
    """获取任务状态，未启动时返回 {'status': 'idle'}。"""
    key = _job_key(model_id, ctx)
    with _LOCK:
        job = _JOBS.get(key)
        if not job:
            # 内存状态丢失（服务器重启），尝试从文件系统恢复已有结果
            html_urls = _scan_html_urls(model_id, ctx)
            if html_urls:
                return {
                    "status": "done",
                    "step": 8,
                    "step_msg": "完成",
                    "step_label": STEP_LABELS.get(8, ""),
                    "total_steps": 8,
                    "html_urls": html_urls,
                    "error": None,
                }
            return {"status": "idle"}
        # 返回副本，不暴露完整 log（避免响应体过大）
        return {
            "status": job["status"],
            "step": job.get("step", 0),
            "step_msg": job.get("step_msg", ""),
            "step_label": STEP_LABELS.get(job.get("step", 0), ""),
            "total_steps": 8,
            "html_urls": job.get("html_urls", {}),
            "error": job.get("error"),
        }
