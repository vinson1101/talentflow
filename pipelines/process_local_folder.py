"""
处理本地文件夹简历

Pipeline入口：
1. 扫描本地文件夹
2. 解析简历内容
3. AI评估决策
4. 生成报告
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.local_adapter import LocalAdapter
from core.resume_ingest import ingest_resume_files
from core.candidate_store import CandidateStore
from core.batch_builder import BatchBuilder
from core.final_reporter import FinalReporter


def process_local_folder(
    folder_path: str,
    jd_content: str,
    file_types: list = None,
    run_dir: Path = None
):
    """
    处理本地文件夹简历

    Args:
        folder_path: 本地文件夹路径
        jd_content: 职位描述
        file_types: 文件类型过滤，如 ['pdf', 'docx']
        run_dir: 运行目录（可选）
    """
    # 1. 创建运行目录
    if run_dir is None:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        run_dir = PROJECT_ROOT / "runs" / f"run_{timestamp}"

    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 运行目录: {run_dir}")

    # 2. 扫描本地文件夹
    print(f"\n🔍 步骤1: 扫描本地文件夹 {folder_path}")
    adapter = LocalAdapter()
    scan_result = adapter.scan_folder(folder_path, file_types=file_types)

    print(f"✅ 找到 {scan_result['total_files']} 个文件")

    if scan_result['total_files'] == 0:
        print("⚠️  没有找到简历文件")
        return

    # 3. 解析简历
    print(f"\n📄 步骤2: 解析简历")
    # TODO: 转换为 ResumeFile 对象
    # ingest_result = ingest_resume_files(resume_files)

    # 4. 构建批量输入
    print(f"\n🔧 步骤3: 构建批量输入")
    batch_builder = BatchBuilder(jd_content)
    # batch_input = batch_builder.build_batch_input(candidates)
    # batch_builder.save_batch_input(batch_input, run_dir)

    # 5. AI评估决策
    print(f"\n🤖 步骤4: AI评估决策")
    # TODO: 调用AI模型进行评估

    # 6. 保存结果
    print(f"\n💾 步骤5: 保存结果")
    store = CandidateStore(run_dir)
    # for candidate in evaluated_candidates:
    #     store.save_candidate(candidate, candidate['id'])

    # 7. 生成最终报告
    print(f"\n📊 步骤6: 生成最终报告")
    reporter = FinalReporter(run_dir / ".." / "outputs")
    # report_path = reporter.generate_final_report(evaluated_candidates, meta)
    # print(f"\n✅ 报告已生成: {report_path}")

    print(f"\n✅ 处理完成！")


if __name__ == "__main__":
    # 示例用法
    import argparse

    parser = argparse.ArgumentParser(description="处理本地文件夹简历")
    parser.add_argument("folder_path", help="本地文件夹路径")
    parser.add_argument("--jd", help="职位描述文件路径")
    parser.add_argument("--types", nargs='+', default=['pdf'], help="文件类型（默认: pdf）")
    parser.add_argument("--run-dir", help="运行目录（可选）")

    args = parser.parse_args()

    # 读取JD
    if args.jd:
        jd_path = Path(args.jd)
        with open(jd_path, 'r', encoding='utf-8') as f:
            jd_content = f.read()
    else:
        jd_content = "请提供职位描述"

    # 处理
    process_local_folder(
        folder_path=args.folder_path,
        jd_content=jd_content,
        file_types=args.types,
        run_dir=Path(args.run_dir) if args.run_dir else None
    )
