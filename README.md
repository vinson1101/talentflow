# TalentFlow - 招聘决策流水线

> 候选人流转与招聘决策自动化工具

---

## 🎯 项目简介

TalentFlow 是一个专业的招聘决策辅助系统，帮助HR和猎头快速评估候选人，提高决策效率和准确性。

### 核心能力

- 🔍 **多渠道简历摄入**：支持飞书、本地文件、钉钉（规划中）
- 🤖 **AI智能评估**：基于职位需求自动分析候选人匹配度
- 📊 **结构化输出**：生成决策报告、风险评估、面试建议
- 🔄 **批量处理**：一次性评估多个候选人，自动排序
- 📝 **多格式导出**：支持JSON、Markdown、飞书表格

---

## 📁 目录结构

```
talentflow/
├── configs/              # 配置文件
│   ├── system_prompt.md   # AI提示词模板
│   ├── input.schema.json  # 输入数据契约
│   └── output.schema.json # 输出数据契约
├── docs/                 # 文档
│   └── candidate_ingestion_spec.md  # 简历摄入规范
├── core/                 # 核心逻辑（平台无关）
│   ├── resume_ingest.py   # 简历解析
│   ├── runner.py          # 评估执行
│   ├── candidate_store.py # 数据存储
│   ├── batch_builder.py   # 批量输入构建
│   └── final_reporter.py  # 报告生成
├── adapters/             # 数据源适配器
│   ├── feishu_adapter.py  # 飞书适配器
│   ├── dingtalk_adapter.py # 钉钉适配器
│   └── local_adapter.py   # 本地文件适配器
├── pipelines/            # 处理流程入口
│   ├── process_feishu_folder.py  # 飞书文件夹处理
│   └── process_local_folder.py   # 本地文件夹处理
├── runs/                 # 运行记录（中间产物）
├── outputs/              # 最终输出（报告、表格）
├── archive/              # 归档文件（实验代码）
└── skills/               # Skill化（OpenClaw集成）
    └── talentflow/
```

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 处理本地文件夹简历

```bash
python pipelines/process_local_folder.py /path/to/resumes --jd jd.md
```

### 处理飞书文件夹简历

```bash
python pipelines/process_feishu_folder.py fldcnxxxxx --jd jd.md
```

---

## 📋 使用场景

### 场景1：批量评估本地简历

```bash
# 扫描 /data/resumes 文件夹下的所有PDF
python pipelines/process_local_folder.py /data/resumes \
    --jd company_jd.md \
    --types pdf docx
```

### 场景2：从飞书云空间评估

```bash
# 处理飞书文件夹中的简历
python pipelines/process_feishu_folder.py WWzZfxn8KlIlgWdAdB7cxurqnOc \
    --jd company_jd.md
```

### 场景3：作为OpenClaw Skill使用

```python
from skills.talentflow.entry import TalentFlowSkill

skill = TalentFlowSkill()
result = skill.process({
    "source": "feishu",
    "folder_token": "fldcnxxxxx",
    "jd": "职位描述内容"
})
```

---

## 🔧 配置说明

### 环境变量（可选）

创建 `.env` 文件：

```bash
# 飞书配置（如果使用飞书适配器）
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# AI模型配置（如果使用非默认模型）
AI_MODEL=zhipu/glm-4.7
```

### 配置文件

- **configs/system_prompt.md**：AI评估提示词模板
- **configs/input.schema.json**：候选人输入数据结构
- **configs/output.schema.json**：评估结果数据结构

---

## 📊 输出格式

### 运行目录结构

```
runs/run_2026-03-22_180500/
├── candidates/           # 候选人数据
│   ├── cand_001.json
│   ├── cand_001.md
│   └── ...
├── batch_input.json      # 批量输入
├── final_output.json     # 最终输出
├── final_report.md       # 最终报告
└── run_meta.json         # 运行元数据
```

### 最终报告

生成在 `outputs/` 目录，包含：
- 候选人汇总统计
- 详细评估结果
- 决策建议
- 面试问题

---

## 🎓 核心原则

TalentFlow 遵循以下设计原则：

1. **决策优先**：每个候选人都必须给出明确决策（strong_yes/yes/maybe/no）
2. **证据驱动**：每个判断必须引用简历中的具体信息
3. **风险强制**：每个候选人必须输出1-3条风险分析
4. **转化导向**：提供可执行的行动建议（话术、面试问题）
5. **现实主义**：考虑薪资、稳定性、沟通难度等现实因素

---

## 🔮 后续规划

- [ ] 支持Word简历解析
- [ ] 支持图片简历OCR
- [ ] 钉钉适配器实现
- [ ] 飞书表格自动录入
- [ ] Web界面
- [ ] API服务化

---

## 📝 License

MIT

---

## 👥 贡献

欢迎提交Issue和Pull Request！

---

**创建时间**：2026年3月22日
**版本**：v0.1.0
**状态**：开发中
