from pydantic import BaseModel
from typing import Any, List, Optional


class Module(BaseModel):
    name: str
    branch: str
    commit_id: str


class SendRequest(BaseModel):
    base_version: str
    modules: List[Module]
    remark: str


class ModelItem(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    name: str
    stage: str = "正在进行"


class BuildRecord(BaseModel):
    id: str
    created_at: str
    base_version: str
    modules: List[Module]
    remark: str
    pipeline_url: str = ""
    final_version: str = ""
    status: str = "构建中"
    test_plan: str = ""
    test_report: List[dict] = []
    tlm_links: List[str] = []
    rpa_links: List[str] = []
    is_manual: bool = False
    manual_label: str = ""
    creator: str = ""
    creator_open_id: str = ""


class BuildFieldUpdate(BaseModel):
    field: str
    value: Any


class BranchRecord(BaseModel):
    id: str
    module: str = ""
    branch: str = ""
    url: str = ""
    remark: str = ""
    status: str = "使用中"  # 使用中 | 已废弃


class PRRecord(BaseModel):
    id: str
    tlm_id: str = ""          # 关联的需求记录 ID
    dev_branch: str = ""
    dev_pr_url: str = ""
    backflow_r6_pr: str = ""
    backflow_r6_status: str = "—"
    backflow_main_pr: str = ""
    backflow_main_status: str = "—"
    remark: str = ""


class VersionRecord(BaseModel):
    id: str
    name: str = ""
    base_version: str = ""
    modules: List[Module] = []
    pipeline_url: str = ""
    package_name: str = ""
    build_status: str = ""
    test_req: str = ""
    test_report: str = ""
    remark: str = ""


class IssueAnalysisRecord(BaseModel):
    id: str = ""
    build_id: str = ""
    test_plan: str = ""
    test_version: str = ""
    test_report: str = ""
    test_issue: str = ""
    group_chat: str = ""
    tlm_links: List[str] = []
    created_at: str = ""


class ExportFeishuRequest(BaseModel):
    doc_title: str
    user_token: str = ""


class TtcUpdate(BaseModel):
    test_version: Optional[str] = None
    section: Optional[str] = None
    overlap: Optional[str] = None
    ttc: Optional[str] = None
    speed: Optional[str] = None
    value: Optional[str] = None
    entries: Optional[List[dict]] = None
    dev_branch: Optional[str] = None
    commit_id: Optional[str] = None
    complete_time_1: Optional[str] = None
    complete_time_2: Optional[str] = None
    complete_time_3: Optional[str] = None
    complete_time_4: Optional[str] = None
    complete_time_5: Optional[str] = None
    complete_time_6: Optional[str] = None


class TLMRecord(BaseModel):
    id: str
    description: str = ""
    owner: str = ""
    tlm_url: str = ""
    tlm_title: str = ""
    rpa_url: str = ""
    rpa_title: str = ""
    version_info: str = ""
    created_at: str = ""
