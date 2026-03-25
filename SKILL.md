---
name: huntmind-recruiting
description: 当用户提供职位描述（JD）以及一份或多份候选人简历文件（尤其是 PDF、DOCX、TXT，或来自飞书/本地目录的批量简历），并希望完成候选人筛选、联系优先级排序、招聘判断、风险提示或招聘决策报告输出时使用。本 skill 用于招聘决策 workflow：简历读取、结构化输入构建、候选人判断、输出校验、质量门禁和报告生成。必要时可附带首轮验证问题与联系建议，但这不是主触发目标。不用于简历润色、不用于面试邀约文案、不用于普通闲聊、不用于通用办公任务。
compatibility:
  claude: ">= 3.5"
  surfaces:
    - claude-app
    - claude-code
metadata:
  domain: recruiting
  owner: HuntMind
  backend: TalentFlow
  stage: focused-v1
---

# HuntMind Recruiting Skill

## 1. 定位

这是 HuntMind 的招聘决策 skill。

- **HuntMind** 是 AI 招聘员工本体 / 对外能力体 / 决策主体
- **TalentFlow** 是该 skill 使用的招聘 workflow backend
- **TalentFlow 负责流程执行与结果守门，不替代 HuntMind 做主体判断**

本 skill 的任务不是"泛泛分析简历"，而是帮助用户完成一轮**可落地、可审计、可复核**的招聘判断闭环：

1. 哪些候选人值得联系
2. 联系优先级如何排序
3. 每位候选人的主要判断依据是什么
4. 哪些风险需要在首轮沟通中验证
5. 如何形成结构化输出和 owner 视图

---

## 2. 何时使用

当出现以下情况时，应触发本 skill：

- 用户上传一个 JD 和一份或多份候选人简历
- 用户提供飞书目录 / 本地目录，并要求批量筛选候选人
- 用户说"帮我筛这批简历"
- 用户说"给这批候选人排序"
- 用户说"判断哪些人值得联系"
- 用户说"生成招聘判断报告 / owner summary"
- 用户说"基于这个岗位，从这批简历里挑出优先联系的人"

---

## 3. 不应使用的场景

以下情况不要触发本 skill：

- 简历润色、改写、翻译
- 求职信、邀约短信、面试通知文案撰写
- 通用办公任务
- 纯聊天或概念讨论
- 与招聘决策无关的候选人沟通任务
- 单纯让模型"总结一份简历"，但没有招聘判断目标
- 用户只是想了解岗位写法、招聘流程常识或 HR 通识

如果任务已经从"招聘判断"转成"文案撰写 / 翻译 / 通用问答"，应让位给更合适的专长能力；不要强行继续使用本 skill。

---

## 4. 核心边界

### 4.1 决策边界

- HuntMind 是决策主体
- TalentFlow 是 workflow backend
- 本 skill 服务的是"招聘决策闭环"，不是"模型自由发挥"

### 4.2 工程边界

TalentFlow：

- 不选择模型
- 不决定主提示词策略
- 不管理 API key / base_url
- 不改变 HuntMind 的主体身份

TalentFlow 负责：

- 读取与整理材料
- 结构化输入
- 调用校验与质量门禁
- 整理最终产物

### 4.3 输出边界

本 skill 的主输出是：

- 候选人是否值得联系
- 候选人排序与优先级
- 招聘判断理由
- 风险与首轮验证点
- 结构化报告

"联系开场建议"最多只作为**附属输出**，不能喧宾夺主，更不能把 skill 误路由成"沟通文案 skill"。

---

### 4.4 评分体系责任边界

**核心原则：HuntMind 负责判断，脚本负责算分与守门。**

**HuntMind（模型）负责**：
- 对每个候选人按 7 维结构输出原始评分（`structured_score.dimension_scores`）
- 每个维度附简短判断依据（`dimension_evidence`）
- 给出 decision、reasons、risks、action 建议

**TalentFlow（脚本）负责**：
- 根据 JD 标题 / 候选人角色选择评分模板（`configs/scoring_templates.yaml`）
- 应用行业修正，重算 `weighted_total`，覆盖模型原始 `total_score`
- 自动生成 legacy `score_breakdown`（兼容层）
- 执行 gate 检查（A 类门槛 / no 门槛）
- 决定 priority、action_timing、rank
- 执行 identity conflict 检查和 decision-action 一致性守门

**禁止**：
- 脚本不得修改模型原始 `dimension_scores`
- 不得将 `score_breakdown` 当作主评分真相
- 不得跳过 `quality_gate.py` 直接交付结果

---

## 5. 支持的输入形态

支持以下输入：

- 结构化 JD（JSON）
- 非结构化 JD（文本、截图转文本、说明性描述）
- 一份或多份简历文件（PDF / DOCX / TXT / MD）
- 飞书文件夹 / 本地目录中的批量简历
- 可选补充信息：
  - 公司背景
  - 岗位上下文
  - 历史用人偏好
  - 团队结构
  - 岗位补充约束
  - 强制淘汰条件 / 加分项

如果 JD 非结构化，应先整理成稳定的岗位判断上下文，再进入后续流程。

---

## 6. 标准工作流

本 skill 默认按以下顺序执行，不应跳过关键守门步骤。

### 阶段 1：ingest

**目标**：把原始材料整理成可判断的标准输入。

执行要点：

- 读取目录 / 文件列表
- 解析 PDF / 文本
- 提取候选人基础信息
- 标准化候选人对象
- 构建 `batch_input.json`
- 写入 `run_meta.json`

要求：

- 尽量保留原始信息来源与解析痕迹
- 解析失败的文件要记录，不要静默吞掉
- 候选人对象字段命名必须稳定

确定性守门：

- 必须通过 `scripts/validate_batch_input.py`
- `batch_input.json` 必须符合 input schema
- 不合法时不得进入 decide 阶段

---

### 阶段 2：decide

**目标**：由 HuntMind 对候选人做招聘判断。

执行要点：

- HuntMind 读取 `batch_input.json`
- 结合岗位要求、公司上下文、决策规则、写作约束进行判断
- 对每位候选人生成结构化结果
- 给出可解释的联系建议、排序依据、风险点和验证建议

判断要求：

- 不把"信息缺失"直接当成风险结论
- 风险必须与岗位决策有关
- 排序必须体现资源稀缺下的真实优先级
- 结论必须能回答：
  1. 今天要不要联系这个人
  2. 如果只能联系少数候选人，他排第几
  3. 首轮沟通最该验证什么

参考约束：

- `references/decision-policy.md`
- `references/output-contract.md`
- `references/conversion-guidelines.md`
- `references/writing-style-constraints.md`

---

### 阶段 3：validate

**目标**：校验、清洗并做质量门禁。

执行要点：

- 校验 JSON 结构合法性
- 校验 required 字段完整性
- 修正非法枚举和明显异常
- 检查 score / rank / priority / action_timing 等关键字段
- 评估质量信号：
  - fallback 痕迹
  - 排序不稳定
  - 高分低优先级异常
  - A 类候选人缺失
  - 模板化空话过多
  - 结论与理由不一致

确定性守门：

- 使用 `scripts/validate_model_output.py`
- 使用 `scripts/quality_gate.py`

处理原则：

- 能清洗的先清洗
- 不能清洗但可标记的，进入人工复核态
- 质量门禁不通过时，不直接视为最终结果

---

### 阶段 4：report

**目标**：将合格结果整理为最终交付产物。

执行要点：

- 生成 `final_output.json`
- 生成 `quality_meta.json`
- 生成 `final_report.md`
- 生成 `owner_summary.md`

脚本入口：

- `scripts/finalize_report.py`

报告要求：

- owner_summary 要能快速支持业务决策
- final_report 要能支持人工复盘
- 输出既要简洁，也要保留可审计信息

---

## 7. 决策原则

本 skill 必须遵守以下原则：

### 7.1 决策优先，不做空泛总结

任务不是"总结简历内容"，而是"做招聘决策"。

### 7.2 decision 是招聘推进判断，不是能力评估

decision 的含义是"这个人在当前招聘约束下值不值得花一个沟通名额去推进"，而不是"这个人的绝对能力有多强"。

必须同时考虑 match_fit（方向匹配度）、recruitability（招聘可达性）和 mismatch_type（错位类型）三个维度：
- 一个能力强但 mismatch_type=hard_mismatch 的候选人，必须强制评为 no
- 一个能力中等但 mismatch_type=recoverable 的候选人，可保留为 maybe
- 一个能力强、match_fit 高、但薪资/层级远超岗位的企业不可达候选人，不应被评为 yes
- 一个能力中等但现实可达的候选人，可能更值得推进

### 7.3 排序必须有资源约束意识

不是"都还不错"，而是要在有限联系资源下做真实排序。

### 7.4 风险必须服务于下一步行动

风险的价值在于指导首轮验证，而不是制造模糊保守措辞。

### 7.5 输出必须可审计

每个重要判断都应可回溯到输入与规则，而不是凭空结论。

### 7.6 允许不确定，但不允许糊弄

可以表达"需要验证"，但不能用套话掩盖判断缺失。

---

## 8. 必须由脚本守门的部分

以下部分不能只靠语言约束，必须通过脚本守门：

- input schema 合法性
- output JSON 结构合法性
- required 字段完整性
- score / rank / priority / action_timing 合法性
- 报告产物完整性
- 质量门禁阈值

模型负责判断；脚本负责确定性校验。

---

## 9. 失败处理

- 如果简历解析失败，记录失败并继续处理其他文件
- 如果 `batch_input.json` 不合法，停止进入 decide 阶段
- 如果模型输出 JSON 不合法，进入校验 / 清洗流程
- 如果质量门禁不通过，标记人工复核，不直接视为最终结果
- 如果关键输入严重缺失，明确说明缺失项及其对判断的影响，不伪造信息

---

## 10. 当前阶段范围

当前阶段只打透一个收敛场景：

**一个 JD + 一批真实简历 + HuntMind 判断 + 稳定结构化输出**

当前不是：

- 通用招聘平台
- 独立商业化系统
- 通用 HR agent 平台
- 面向所有招聘子任务的一体化万能 skill

---

## 11. 标准输出产物

本 skill 的最终标准产物包括：

- `candidates/`
- `batch_input.json`
- `run_meta.json`
- `final_output.json`
- `quality_meta.json`
- `final_report.md`
- `owner_summary.md`

---

## 12. Execution Contract - 执行约束（必须遵守）

以下约束通过 SKILL.md 强制执行，docs 目录下的说明文档只负责解释，不构成执行约束。

### 12.1 一轮 skill = 一轮完整招聘处理
- 一轮 skill 处理一个 JD + 一批简历
- 结果落 Runs 表（1条） + Candidates 表（N条）
- 不做跨批次合并、不做 backfill

### 12.2 JD / 简历输入方式
| 输入 | 方式 |
|------|------|
| JD | 结构化 `jd.json`（推荐）或自然语言描述 |
| 飞书云盘简历 | HR 上传到飞书云盘，提供 folder_token，调用 `load_feishu_resume_files()` 下载 |
| 聊天窗口简历 | HR 直接发送附件，保存到 inbox/ |

### 12.3 inbox 汇流，但 source 元信息必须保留
- 所有简历最终进入 `inbox/`，主处理逻辑不因来源分叉
- `source.platform` / `file_id` / `file_name` 必须写入 batch_input
- 用于追溯来源和生成 resume_link，不得丢弃

### 12.4 标准输出与飞书写表
- 最终产物：`final_output.json` + `owner_summary.md`
- 自动写入飞书 Runs 表 + Candidates 表
- HR 反馈字段（跟进状态/HR备注/面试结果/最终结果）不被 AI 覆盖

### 12.5 禁止事项
- ❌ backfill
- ❌ 演示评分算法 / 人工造数据跑 pipeline
- ❌ 改动前不跑 golden set 验证

### 12.6 改前必验
任何对评分体系、模板选择、pipeline 脚本的改动，必须：
1. 用 `evals/golden_set/product_manager_batch_001/` 回归集验证
2. 对照 `expected_review.md` 检查排名和质量分
3. 通过 quality_gate（quality_score ≥ 85）

### 12.7 写表 schema 稳定，视图 UX 可迭代
- 底层写表字段结构保持稳定
- 视图层（字段顺序、排序、筛选）允许在实战中人工微调
- 不为微调视图而频繁改动底层写表逻辑

### 12.8 HR 默认使用当前 run 视图
- 每轮结果默认通过「当前 run 过滤视图」查看
- 不建议直接浏览全量 Candidates 总表
- 视图过滤条件：`批次ID` = 当前 run_id

### 12.9 排名必须有，推荐不必须有
- 每批都按分数降序排名（1=最高分）
- 不是每批都必须有 strong_yes 或 A 类--整批不达标是正常结果
- 禁止为"有输出"强行凑推荐理由

### 12.10 展示模板（摘要卡片）
- **人类可读摘要**默认按 `references/summary-card-template.md` 生成
- **JSON / 飞书表格**为系统输出真相
- 摘要卡片属于展示层派生产物，服务业务阅读
- 不影响 `final_output.json` schema 和飞书字段
- 允许措辞微调，但区块结构（5个标准区块）须稳定

---

## 13. 参考文档

- `references/decision-policy.md`
- `references/output-contract.md`
- `references/scoring-policy.md` - **7维评分体系主规则**（含执行约束）
- `references/conversion-guidelines.md`
- `references/writing-style-constraints.md`
- `docs/TalentFlow-招聘审核完整流程说明-V1.4.md` - 流程说明（不构成执行约束）

这些文档用于补充规则与格式，不应把所有细节硬塞进本文件正文。

---

## 14. 脚本入口

- `scripts/validate_batch_input.py`
- `scripts/validate_model_output.py`
- `scripts/quality_gate.py`
- `scripts/finalize_report.py`

---

## 15. 触发测试样例

下面这些测试样例用于验证路由是否合理。

### 应触发

1. "这是一个高级产品经理 JD，下面有 10 份 PDF 简历，帮我筛一下。"
2. "我给你一个飞书文件夹，里面都是候选人简历，帮我排出优先联系顺序。"
3. "根据这个岗位，告诉我哪些候选人值得打第一轮电话。"
4. "请基于这批简历生成招聘判断报告和 owner summary。"
5. "帮我从这些候选人里选出最值得联系的前 5 个，并说明原因。"

### 不应触发

1. "帮我润色一下这份简历。"
2. "把这段面试邀约话术写得更专业一点。"
3. "招聘里常说的人岗匹配是什么意思？"
4. "把这份英文简历翻译成中文。"
5. "随便聊聊你怎么看待 AI 招聘。"

---

## 16. 使用提醒

当任务满足触发条件时，应优先把问题识别为：

**"用户要完成一轮招聘决策"**

而不是：

- "用户只是想看简历内容"
- "用户只是想写一段 HR 文案"
- "用户只是想讨论招聘概念"

本 skill 的价值不在信息搬运，而在于形成**可执行判断**。
