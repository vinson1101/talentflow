#!/usr/bin/env python3
"""
TalentFlow 目录结构验证脚本

检查所有必需的文件和目录是否存在
"""

import sys
from pathlib import Path


def check_structure():
    """检查目录结构"""
    project_root = Path(__file__).resolve().parent.parent

    print(f"🔍 检查 TalentFlow 目录结构")
    print(f"📁 项目根目录: {project_root}\n")

    # 必需的目录
    required_dirs = [
        "configs",
        "docs",
        "core",
        "adapters",
        "pipelines",
        "runs",
        "outputs",
        "archive",
        "skills/talentflow"
    ]

    # 必需的文件
    required_files = [
        "README.md",
        "requirements.txt",
        ".env.example",
        "configs/system_prompt.md",
        "configs/input.schema.json",
        "configs/output.schema.json",
        "docs/candidate_ingestion_spec.md",
        "core/__init__.py",
        "core/resume_ingest.py",
        "core/runner.py",
        "core/candidate_store.py",
        "core/batch_builder.py",
        "core/final_reporter.py",
        "adapters/__init__.py",
        "adapters/feishu_adapter.py",
        "adapters/local_adapter.py",
        "pipelines/__init__.py",
        "pipelines/process_feishu_folder.py",
        "pipelines/process_local_folder.py",
        "archive/feishu_folder_adapter.py",
        "archive/test_feishu_ingest.py"
    ]

    # 检查目录
    print("📂 检查目录...")
    missing_dirs = []
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists() and full_path.is_dir():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} (缺失)")
            missing_dirs.append(dir_path)

    # 检查文件
    print("\n📄 检查文件...")
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists() and full_path.is_file():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (缺失)")
            missing_files.append(file_path)

    # 总结
    print("\n" + "="*50)
    if not missing_dirs and not missing_files:
        print("✅ 目录结构完整！")
        return 0
    else:
        print("❌ 目录结构不完整！")
        if missing_dirs:
            print(f"\n缺失的目录 ({len(missing_dirs)}):")
            for d in missing_dirs:
                print(f"  - {d}")
        if missing_files:
            print(f"\n缺失的文件 ({len(missing_files)}):")
            for f in missing_files:
                print(f"  - {f}")
        return 1


if __name__ == "__main__":
    sys.exit(check_structure())
