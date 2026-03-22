---
name: huntmind-recruiting
description: 当用户提供职位描述（JD）以及一份或多份候选人简历文件（尤其是 PDF、DOCX、TXT，或来自飞书/本地目录的批量简历），并希望完成候选人筛选、联系优先级排序、招聘判断、风险提示、联系话术生成或招聘决策报告输出时使用。本 skill 用于招聘决策 workflow：简历读取、结构化输入构建、候选人判断、输出校验、质量门禁和报告生成。不用于简历润色、不用于面试邀约文案、不用于普通闲聊、不用于通用办公任务。
---

# HuntMind Recruiting Skill

## 定位

这是 **HuntMind 的招聘决策 skill**。

- **HuntMind** 是 AI 招聘员工本体 / 对外能力体 / 决策主体
- **TalentFlow** 是该 skill 使用的招聘 workflow backend

本 skill 的目标不是“分析简历”，而是帮助用户完成一轮可落地的招聘判断闭环：
- 哪些候选人值得联系
- 联系优先级如何排序
- 首轮验证问题是什么
- 应该用什么方式开场
- 最终如何形成结构化报告和 owner 视图

## 触发条件

当出现以下情况时触发：

- 用户上传 JD 和一份或多份简历文件
- 用户提供飞书目录 / 本地目录，并要求筛选候选人
- 用户说“帮我筛这批简历”
- 用户说“给这批候选人排序 / 给联系优先级”
- 用户说“生成招聘判断报告 / owner summary”

## 不触发场景

以下情况不要使用本 skill：

- 简历润色、改写、翻译
- 面试邀约文案撰写
- 通用办公任务
- 纯聊天或概念讨论
- 与招聘决策无关的候选人沟通任务

## 输入形态

支持以下输入：

- 结构化 JD（JSON）
- 非结构化 JD（需要先整理）
- 一份或多份简历文件（PDF / DOCX / TXT / MD）
- 飞书文件夹 / 本地目录中的批量简历
- 可选：公司背景、岗位上下文、历史偏好、岗位补充约束

## 工作流阶段

### 阶段 1：ingest

目的：把原始简历材料整理成可判断的标准输入。

执行要点：
- 读取目录 / 文件列表
- 解析 PDF / 文本
- 标准化候选人对象
- 生成 `batch_input.json`
- 写入 `run_meta.json`

确定性守门：
- 必须通过 `scripts/validate_batch_input.py`
- `batch_input` 必须符合 input schema

### 阶段 2：decide

目的：由 HuntMind 对候选人做招聘判断。

执行要点：
- HuntMind 读取 `batch_input.json`
- 结合岗位上下文、决策规则和写作约束进行判断
- 生成结构化结果 JSON

重要边界：
- TalentFlow 不选择模型
- TalentFlow 不决定 prompt
- TalentFlow 不管理 API key / base_url
- 决策主体始终是 HuntMind

参考约束：
- `references/decision-policy.md`
- `references/output-contract.md`
- `references/conversion-guidelines.md`
- `references/writing-style-constraints.md`

### 阶段 3：validate

目的：把 HuntMind 的判断结果校验、清洗并做质量门禁。

执行要点：
- 校验 JSON 结构合法性
- 校验 required 字段完整性
- 修正非法枚举和明显异常
- 评估质量（如 fallback 痕迹、排序稳定性、A 类优先级缺失等）

确定性守门：
- 使用 `scripts/validate_model_output.py`
- 使用 `scripts/quality_gate.py`

### 阶段 4：report

目的：将合格结果转为最终产物。

执行要点：
- 生成 `final_output.json`
- 生成 `quality_meta.json`
- 生成 `final_report.md`
- 生成 `owner_summary.md`

脚本入口：
- `scripts/finalize_report.py`

## 决策原则

- 任务不是“分析简历”，而是“做招聘决策”
- 必须帮助用户回答：
  1. 今天要不要联系这个人
  2. 如果只能打 3 个电话，他排第几
  3. 应该用什么方式开场
- 风险必须是判断，不是“信息缺失描述”
- 输出必须可审计、可复盘、可继续人工复核

## 必须正确的部分

以下部分不能只靠语言约束，必须通过脚本守门：

- input schema 合法性
- output JSON 结构合法性
- required 字段完整性
- score / rank / priority / action_timing 合法性
- 报告产物完整性
- 质量门禁阈值

## 当前阶段范围

当前阶段只打透一个收敛场景：

**一个 JD + 一批真实简历 + HuntMind 判断 + 稳定结构化输出。**

当前不是：
- 通用招聘平台
- 独立商业化系统
- 通用 HR agent 平台

## 输出产物

本 skill 的最终标准产物包括：

- `candidates/`
- `batch_input.json`
- `run_meta.json`
- `final_output.json`
- `quality_meta.json`
- `final_report.md`
- `owner_summary.md`

## 失败处理

- 如果简历解析失败，记录失败并继续处理其他文件
- 如果 `batch_input` 不合法，停止进入判断阶段
- 如果模型输出 JSON 不合法，进入校验/清洗流程
- 如果质量门禁不通过，标记人工复核，不直接视为最终结果

## 参考文档

- `references/decision-policy.md`
- `references/output-contract.md`
- `references/conversion-guidelines.md`
- `references/writing-style-constraints.md`

## 脚本入口

- `scripts/validate_batch_input.py`
- `scripts/validate_model_output.py`
- `scripts/quality_gate.py`
- `scripts/finalize_report.py`
