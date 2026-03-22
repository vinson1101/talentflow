# TalentFlow 本地 / 临时目录接入流程

## 适用场景

当 HuntMind / OpenClaw 已经使用现有飞书能力完成：
1. 列出飞书目录内容
2. 下载候选人文件到某个临时目录

此时 **TalentFlow 不需要再实现一套飞书来源接入**。
对 TalentFlow 而言，这些文件已经等同于普通本地文件。

---

## 推荐调用方式

### 第一步：由外部能力下载到临时目录

例如：

```text
/tmp/huntmind_resumes/
├── 候选人A.pdf
├── 候选人B.docx
└── 候选人C.txt
```

### 第二步：调用 TalentFlow 本地 pipeline

```bash
cd talentflow
python3 pipelines/process_local_folder.py \
    /tmp/huntmind_resumes \
    --jd /path/to/jd.json \
    --types pdf docx txt
```

### 第三步：查看结果

```text
talentflow/runs/run_2026-03-22_173711/
├── batch_input.json          # 提交给模型的输入
├── run_meta.json             # 运行元数据
├── candidates/               # 候选人原始数据
│   ├── local_候选A_id.json
│   ├── local_候选B_id.json
│   └── ...
├── final_output.json         # AI 评估结果
├── quality_meta.json         # 质量检测元数据
├── final_report.md           # 详细报告
└── owner_summary.md          # 简短摘要
```

---

## 优势

1. **复用现有能力**：飞书下载能力已在 OpenClaw 插件包中实现
2. **职责分离**：TalentFlow 专注决策逻辑，不关心文件来源
3. **灵活性高**：支持任何来源的本地文件（飞书、手动上传、其他云盘）
4. **测试友好**：可以直接用本地文件测试，无需配置飞书

---

## 注意事项

1. **文件名清洗**：建议在外部下载时清洗文件名（去除特殊字符）
2. **临时目录**：建议使用 `/tmp/` 或项目内的 `runs/<run_id>/inbox/`
3. **JD 格式**：必须使用符合 `configs/input.schema.json` 的 JSON 格式
