"""
本地文件适配器

功能：
- 从本地文件夹读取简历
- 支持多种文件格式
- 返回标准化的文件列表
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging


@dataclass
class LocalFile:
    """本地文件对象"""
    file_path: str
    file_name: str
    file_type: str
    size: int = 0


class LocalAdapter:
    """本地文件适配器"""

    def __init__(self):
        """初始化"""
        self.logger = logging.getLogger(__name__)

    def scan_folder(
        self,
        folder_path: str,
        file_types: Optional[List[str]] = None,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        扫描本地文件夹

        Args:
            folder_path: 文件夹路径
            file_types: 文件类型过滤，如 ['pdf', 'docx', 'png']
            recursive: 是否递归子文件夹

        Returns:
            {
                "total_files": 10,
                "files": [LocalFile, ...]
            }
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")

        if file_types is None:
            file_types = ['pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg']

        files = []
        pattern = "**/*" if recursive else "*"

        for file_path in folder.glob(pattern):
            if file_path.is_file():
                file_ext = file_path.suffix.lstrip('.').lower()
                if file_ext in file_types:
                    files.append(LocalFile(
                        file_path=str(file_path),
                        file_name=file_path.name,
                        file_type=file_ext,
                        size=file_path.stat().st_size
                    ))

        return {
            "total_files": len(files),
            "files": files
        }

    def read_file(self, file_path: str) -> Optional[bytes]:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容（bytes），失败返回None
        """
        try:
            path = Path(file_path)
            with open(path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"读取文件失败 {file_path}: {e}")
            return None
