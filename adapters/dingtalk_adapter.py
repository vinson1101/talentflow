"""
钉钉适配器（预留）

功能：
- 从钉钉云空间读取简历
- 支持钉钉API
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DingTalkAdapter:
    """钉钉文件适配器"""

    def __init__(self):
        """初始化"""
        logger.warning("DingTalkAdapter 尚未实现")

    def list_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """列出文件夹内容"""
        raise NotImplementedError("钉钉适配器尚未实现")

    def download_file(self, file_id: str) -> Optional[str]:
        """下载文件"""
        raise NotImplementedError("钉钉适配器尚未实现")
