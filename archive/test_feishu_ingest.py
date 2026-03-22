"""
测试飞书文件夹批量摄入流程

使用方式：
1. 设置环境变量：
   export FEISHU_APP_ID=cli_xxx
   export FEISHU_APP_SECRET=xxx
   export FEISHU_RESUME_FOLDER_TOKEN=fldcnxxxxxxxx

2. 运行测试：
   python test_feishu_ingest.py
"""

import json
import os
from pathlib import Path

from feishu_folder_adapter import load_feishu_resume_files
# from resume_ingest import ingest_resume_files  # 需要先创建 resume_ingest.py


def main():
    folder_token = os.environ.get("FEISHU_RESUME_FOLDER_TOKEN")

    if not folder_token:
        print("❌ 缺少环境变量: FEISHU_RESUME_FOLDER_TOKEN")
        print("\n请设置以下环境变量：")
        print("  export FEISHU_APP_ID=cli_xxx")
        print("  export FEISHU_APP_SECRET=xxx")
        print("  export FEISHU_RESUME_FOLDER_TOKEN=fldcnxxxxxxxx")
        return

    print(f"📂 开始处理飞书文件夹: {folder_token}")

    try:
        # 第1步：从飞书云空间下载简历
        print("\n🔽 步骤1: 从飞书云空间下载简历...")
        adapter_result = load_feishu_resume_files(
            folder_token=folder_token,
            max_files=10,
            download_dir="./tmp/feishu_resumes",
            channel="feishu_bot"
        )

        print("✅ 下载完成！")
        print("\n=== 下载统计 ===")
        print(json.dumps(adapter_result["stats"], ensure_ascii=False, indent=2))

        if adapter_result["failures"]:
            print("\n⚠️  下载失败文件：")
            print(json.dumps(adapter_result["failures"], ensure_ascii=False, indent=2))

        if adapter_result["resume_files"]:
            print(f"\n📄 成功下载 {len(adapter_result['resume_files'])} 个简历文件")
            print("\n=== 前3个文件示例 ===")
            for idx, rf in enumerate(adapter_result["resume_files"][:3], 1):
                print(f"\n{idx}. {rf.file_name}")
                print(f"   文件ID: {rf.file_id}")
                print(f"   本地路径: {rf.file_path}")

            # 第2步：解析简历（需要 resume_ingest.py）
            # print("\n🔍 步骤2: 解析简历内容...")
            # ingest_result = ingest_resume_files(adapter_result["resume_files"])
            #
            # print("✅ 解析完成！")
            # print("\n=== 解析统计 ===")
            # print(json.dumps(ingest_result["stats"], ensure_ascii=False, indent=2))
            #
            # if ingest_result["candidates"]:
            #     print(f"\n👤 成功解析 {len(ingest_result['candidates'])} 个候选人")
            #     print("\n=== 候选人示例（第1个）===")
            #     print(json.dumps(ingest_result["candidates"][0], ensure_ascii=False, indent=2)[:4000])

        else:
            print("\n⚠️  未找到PDF简历文件")

    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
