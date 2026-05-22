import os
import requests

_APP_ID = os.environ.get("FEISHU_APP_ID", "YOUR_FEISHU_APP_ID")
_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_FEISHU_APP_SECRET")
_BITABLE_APP_TOKEN = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "YOUR_BITABLE_APP_TOKEN")
_TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "YOUR_TABLE_ID")
_BASE = "https://open.feishu.cn/open-apis"


def _get_token() -> str:
    r = requests.post(
        f"{_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": _APP_ID, "app_secret": _APP_SECRET},
        timeout=10,
    )
    return r.json()["tenant_access_token"]


def fetch_deliverable_links(test_version: str) -> list:
    """
    通过测试版本（包名）在飞书多维表格中查找对应记录，返回交付物链接列表。
    test_version: 如 'LHUAS-V6.0.15-...-20260408.44967.tgz'
    """
    if not test_version or not test_version.strip():
        return []
    try:
        token = _get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "测试版本",
                        "operator": "contains",
                        "value": [test_version.strip()],
                    }
                ],
            },
            "field_names": ["交付物"],
        }
        r = requests.post(
            f"{_BASE}/bitable/v1/apps/{_BITABLE_APP_TOKEN}/tables/{_TABLE_ID}/records/search",
            headers=headers,
            json=body,
            timeout=15,
        )
        items = r.json().get("data", {}).get("items", [])
        if not items:
            return []
        # 取第一条记录的交付物字段
        fields = items[0].get("fields", {})
        deliverable = None
        for v in fields.values():
            if isinstance(v, list) and any(
                isinstance(x, dict) and x.get("type") == "mention" for x in v
            ):
                deliverable = v
                break
        if not deliverable:
            return []
        links = []
        for item in deliverable:
            if item.get("type") == "mention" and item.get("link"):
                links.append(item["link"])
        return links
    except Exception as e:
        print(f"[feishu-deliverable] {e}")
        return []
