import os
import re
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# 复用你前面已经有的 ingestion 层
# from resume_ingest import ResumeFile
from dataclasses import dataclass


@dataclass
class ResumeFile:
    source_platform: str
    file_id: str
    file_name: str
    file_path: Optional[str] = None
    file_bytes: Optional[bytes] = None
    file_url: Optional[str] = None
    folder_id: Optional[str] = None
    channel: Optional[str] = None
    mime_type: Optional[str] = None
    extra_meta: Optional[Dict[str, Any]] = None


class FeishuAPIError(Exception):
    pass


class FeishuFolderAdapter:
    BASE_URL = "https://open.feishu.cn"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        download_dir: str = "./tmp/feishu_resumes",
        timeout: int = 30,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.download_dir = Path(download_dir)
        self.timeout = timeout
        self.session = requests.Session()

        self._tenant_access_token: Optional[str] = None
        self._token_expire_at: float = 0

    # =========================
    # 基础请求
    # =========================
    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        url = f"{self.BASE_URL}{path}"
        resp = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout,
            stream=stream,
        )
        return resp

    def get_tenant_access_token(self) -> str:
        now = time.time()
        if self._tenant_access_token and now < self._token_expire_at - 60:
            return self._tenant_access_token

        resp = self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json_body={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            },
        )

        try:
            data = resp.json()
        except Exception as e:
            raise FeishuAPIError(f"token response not json: {resp.text[:500]}") from e

        if resp.status_code != 200 or data.get("code") != 0:
            raise FeishuAPIError(
                f"get_tenant_access_token failed: http={resp.status_code}, body={data}"
            )

        token = data["tenant_access_token"]
        expire = data.get("expire", 7200)

        self._tenant_access_token = token
        self._token_expire_at = now + expire
        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.get_tenant_access_token()}"
        }

    # =========================
    # 文件夹 / 文件能力
    # =========================
    def list_folder_items(self, folder_token: str, page_size: int = 50) -> List[Dict[str, Any]]:
        """
        列出飞书文件夹下内容
        """
        items: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            params = {
                "folder_token": folder_token,
                "page_size": page_size,
            }
            if page_token:
                params["page_token"] = page_token

            resp = self._request(
                "GET",
                "/open-apis/drive/v1/files",
                headers=self._auth_headers(),
                params=params,
            )

            try:
                data = resp.json()
            except Exception as e:
                raise FeishuAPIError(f"list_folder_items response not json: {resp.text[:500]}") from e

            if resp.status_code != 200 or data.get("code") != 0:
                raise FeishuAPIError(
                    f"list_folder_items failed: http={resp.status_code}, body={data}"
                )

            page_items = data.get("data", {}).get("files", [])
            items.extend(page_items)

            has_more = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("next_page_token")

            if not has_more:
                break

        return items

    def download_file(self, file_token: str, dest_path: str) -> str:
        """
        下载飞书文件到本地
        """
        resp = self._request(
            "GET",
            f"/open-apis/drive/v1/files/{file_token}/download",
            headers=self._auth_headers(),
            stream=True,
        )

        if resp.status_code != 200:
            try:
                body = resp.json()
            except Exception:
                body = resp.text[:500]
            raise FeishuAPIError(
                f"download_file failed: http={resp.status_code}, body={body}"
            )

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 128):
                if chunk:
                    f.write(chunk)

        return str(dest)

    # =========================
    # 过滤与转换
    # =========================
    @staticmethod
    def _safe_filename(name: str) -> str:
        name = name.strip().replace("/", "_").replace("\\", "_")
        name = re.sub(r"[^\w\-.()\u4e00-\u9fff]+", "_", name)
        return name[:180] or "resume.pdf"

    @staticmethod
    def _is_pdf_item(item: Dict[str, Any]) -> bool:
        name = (item.get("name") or item.get("title") or "").lower()
        mime_type = (item.get("mime_type") or "").lower()
        file_type = (item.get("type") or "").lower()

        if name.endswith(".pdf"):
            return True
        if "pdf" in mime_type:
            return True
        if file_type == "pdf":
            return True
        return False

    @staticmethod
    def _build_stable_file_id(item: Dict[str, Any]) -> str:
        file_id = item.get("token") or item.get("file_token") or item.get("id")
        if file_id:
            return str(file_id)

        raw = json.dumps(item, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"unknown_{digest}"

    def list_pdf_items(self, folder_token: str, max_files: Optional[int] = None) -> List[Dict[str, Any]]:
        items = self.list_folder_items(folder_token)
        pdf_items = [x for x in items if self._is_pdf_item(x)]
        if max_files is not None:
            pdf_items = pdf_items[:max_files]
        return pdf_items

    def build_resume_files_from_folder(
        self,
        folder_token: str,
        *,
        max_files: Optional[int] = None,
        keep_local_copy: bool = True,
        channel: str = "feishu_bot",
    ) -> Dict[str, Any]:
        """
        folder -> 下载 PDF -> ResumeFile[]
        """
        pdf_items = self.list_pdf_items(folder_token=folder_token, max_files=max_files)

        resume_files: List[ResumeFile] = []
        failures: List[Dict[str, Any]] = []

        self.download_dir.mkdir(parents=True, exist_ok=True)

        for idx, item in enumerate(pdf_items, 1):
            file_id = self._build_stable_file_id(item)
            file_token = item.get("token") or item.get("file_token") or item.get("id")
            file_name = item.get("name") or item.get("title") or f"resume_{idx}.pdf"
            file_url = item.get("url") or item.get("link") or ""
            mime_type = item.get("mime_type") or "application/pdf"

            if not file_token:
                failures.append({
                    "file_name": file_name,
                    "file_id": file_id,
                    "status": "failed",
                    "reason": "missing file_token"
                })
                continue

            safe_name = self._safe_filename(file_name)
            local_path = str(self.download_dir / safe_name)

            try:
                self.download_file(file_token=file_token, dest_path=local_path)

                resume_files.append(
                    ResumeFile(
                        source_platform="feishu",
                        file_id=file_id,
                        file_name=file_name,
                        file_path=local_path,
                        file_url=file_url,
                        folder_id=folder_token,
                        channel=channel,
                        mime_type=mime_type,
                        extra_meta=item,
                    )
                )

            except Exception as e:
                failures.append({
                    "file_name": file_name,
                    "file_id": file_id,
                    "status": "failed",
                    "reason": str(e)
                })

        return {
            "resume_files": resume_files,
            "failures": failures,
            "stats": {
                "total_pdf_files": len(pdf_items),
                "success_count": len(resume_files),
                "failed_count": len(failures),
                "keep_local_copy": keep_local_copy,
            }
        }


# =========================
# 便捷函数：给 HuntMind 直接调
# =========================
def load_feishu_resume_files(
    folder_token: str,
    *,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    download_dir: str = "./tmp/feishu_resumes",
    max_files: Optional[int] = None,
    channel: str = "feishu_bot",
) -> Dict[str, Any]:
    app_id = app_id or os.getenv("FEISHU_APP_ID")
    app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")

    if not app_id or not app_secret:
        raise RuntimeError("Missing FEISHU_APP_ID / FEISHU_APP_SECRET")

    adapter = FeishuFolderAdapter(
        app_id=app_id,
        app_secret=app_secret,
        download_dir=download_dir,
    )

    return adapter.build_resume_files_from_folder(
        folder_token=folder_token,
        max_files=max_files,
        channel=channel,
    )


if __name__ == "__main__":
    folder_token = os.getenv("FEISHU_RESUME_FOLDER_TOKEN")
    if not folder_token:
        raise SystemExit("Please set FEISHU_RESUME_FOLDER_TOKEN")

    result = load_feishu_resume_files(
        folder_token=folder_token,
        max_files=10,
    )

    print(json.dumps({
        "stats": result["stats"],
        "failures": result["failures"],
        "sample_files": [
            {
                "file_id": x.file_id,
                "file_name": x.file_name,
                "file_path": x.file_path,
            }
            for x in result["resume_files"][:3]
        ]
    }, ensure_ascii=False, indent=2))
