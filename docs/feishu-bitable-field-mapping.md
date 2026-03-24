# 飞书多维表格字段映射文档（V1.1）

> 本文档定义 TalentFlow 输出结果写入飞书多维表格的字段映射规则。
> 对应代码：`core/feishu_bitable_writer.py`

---

## 0. 表结构概览

| 表 | 用途 | 唯一键 | 说明 |
|---|------|--------|------|
| Runs | 批次总索引 | run_id | 轻索引，不做重运营 |
| Candidates | 候选人决策总表 | run_id + candidate_id | 多 run 共用一张表，每次 run 新建视图 |
| Candidates 视图 | 每 run 的过滤视图 | — | 按 run_id 过滤 + rank 升序，HR 默认视图 |

---

## 1. Runs 表字段映射

| 飞书字段 | 类型 | 数据来源 | 说明 |
|---------|------|---------|------|
| 批次ID | 文本 | run_meta.run_id / 路径解析 | 格式：run_YYYYMMDD_HHMMSS |
| JD标题 | 文本 | batch_input.jd.title | 岗位名称 |
| JD地点 | 文本 | batch_input.jd.location | 城市/地点 |
| JD薪资范围 | 文本 | batch_input.jd.salary_range | 薪资范围 |
| 候选人数 | 数字 | quality_meta.candidate_count | 候选人总数 |
| 建议联系人数 | 数字 | 统计 should_contact=true 的人数 | — |
| Top候选人 | 文本 | final_output top 5 candidate_name | 用 ； 分隔 |
| 质量分 | 数字 | quality_meta.quality_score | 0-100 |
| 质量标记 | 文本 | quality_meta.quality_flag | ok / warning / fail |
| 身份冲突数 | 数字 | quality_meta.identity_conflict_count | — |
| 平均分 | 数字 | quality_meta.avg_score | 保留2位小数 |
| 输出版本 | 文本 | 固定 "talentflow-v1" | — |
| 批次摘要 | 文本 | owner_summary.md | 截断5000字 |
| batch_input路径 | 文本 | batch_input.json 绝对路径 | 追溯用 |
| final_output路径 | 文本 | final_output.json 绝对路径 | 追溯用 |
| 创建时间 | 日期 | run_meta.created_at / 当前时间 | 毫秒时间戳 |
| **结果视图** | 超链接 | 指向该 run 的 Candidates 视图 URL | 手动在飞书UI设置 |

---

## 2. Candidates 表字段映射

> ⚠️ 字段顺序由飞书 UI 控制，需手动拖拽调整。
> 推荐顺序：排名 → 候选人姓名 → 简历链接 → 角色标签 → 决策结论 → 优先级 → 行动时机 → 综合评分 → 核心判断 → [其余字段]

### 2.1 基础识别字段

| 飞书字段 | 类型 | 数据来源 | 说明 |
|---------|------|---------|------|
| 批次ID | 文本 | 同 Runs | 关联所属批次 |
| 候选人ID | 文本 | candidate_id | 系统唯一ID |
| 候选人姓名 | 文本 | candidate_name | 展示姓名 |
| 规范姓名 | 文本 | identity_meta.canonical_name | 归一化姓名 |
| 角色标签 | 文本 | role_label | 如"产品经理" |
| 来源平台 | 文本 | batch_input.candidates[i].source.platform | local / feishu / dingtalk |
| 原始文件名 | 文本 | batch_input.candidates[i].source.file_name | 简历文件名 |
| **简历链接** | 超链接 | **来源平台=feishu时** 生成文件链接；否则为空 | 飞书直传/云目录文件写入打开链接 |

### 2.2 AI 决策核心字段（建议前置显示）

| 飞书字段 | 类型 | 数据来源 | 说明 |
|---------|------|---------|------|
| 排名 | 数字 | rank | 1-N，升序 |
| 综合评分 | 数字 | total_score | 保留2位小数 |
| 决策结论 | 文本 | decision | strong_yes / yes / maybe / no |
| 优先级 | 文本 | priority | A / B / C |
| 行动时机 | 文本 | action_timing | today / this_week / optional / no_action |
| 核心判断 | 文本 | core_judgement | 核心判断文本 |

### 2.3 AI 行动字段

| 飞书字段 | 类型 | 数据来源 | 说明 |
|---------|------|---------|------|
| 建议联系 | 复选框 | action.should_contact | true/false |
| 推荐理由 | 文本 | reasons[] → ； 分隔 | — |
| 风险提示 | 文本 | risks[] → ； 分隔 | — |
| 核实问题 | 文本 | action.verification_question | 首轮验证问题 |
| 钩子消息 | 文本 | action.hook_message | 开场钩子 |
| 联系话术模板 | 文本 | action.message_template | 推荐联系话术 |

### 2.4 7维评分字段

| 飞书字段 | 类型 | 数据来源 |
|---------|------|---------|
| 硬技能匹配 | 数字 | structured_score.dimension_scores.hard_skill_match |
| 经验深度 | 数字 | structured_score.dimension_scores.experience_depth |
| 创新潜能 | 数字 | structured_score.dimension_scores.innovation_potential |
| 目标拆解执行 | 数字 | structured_score.dimension_scores.execution_goal_breakdown |
| 团队融合 | 数字 | structured_score.dimension_scores.team_fit |
| 意愿度 | 数字 | structured_score.dimension_scores.willingness |
| 稳定性 | 数字 | structured_score.dimension_scores.stability |
| 模板ID | 文本 | structured_score.template_id |
| 加权总分 | 数字 | structured_score.weighted_total |
| 证据摘要 | 文本 | 7维 dimension_evidence 拼接 |

**证据摘要格式**：
```
硬技能：...；经验深度：...；创新潜能：...；目标拆解执行：...；团队融合：...；意愿度：...；稳定性：...
```

### 2.5 身份与质量字段

| 飞书字段 | 类型 | 数据来源 | 说明 |
|---------|------|---------|------|
| 身份冲突 | 复选框 | identity_meta.has_conflict | true/false |
| 身份处理方案 | 文本 | identity_meta.resolution | unchanged / corrected / flagged |
| 冲突字段 | 文本 | identity_meta.conflict_fields[] → ； 分隔 | — |
| 质量备注 | 文本 | 自动生成 | identity冲突/分数不同步/evidence占位检测 |

### 2.6 轻反馈字段（仅保留4项）

| 飞书字段 | 类型 | 说明 |
|---------|------|------|
| 跟进状态 | 文本 | HR 填写 |
| HR备注 | 文本 | HR 填写 |
| 面试结果 | 文本 | HR 填写 |
| 最终结果 | 文本 | HR 填写 |

---

## 3. resume_link 生成规则

| 来源平台 | 生成逻辑 | 示例 |
|---------|---------|------|
| feishu | `https://ucn43sn4odey.feishu.cn/drive/{file_id}` | 飞书直传/云目录文件 |
| local / 其他 | 空字符串 | 本地文件无链接 |

> ⚠️ 后续若简历上传到飞书，file_id 需从 batch_input.json 的 `source.file_id` 字段读取。
> 当前黄金集为 local 来源，resume_link 为空。

---

## 4. Candidates 视图规则

每次 run 发布后，需在飞书 UI 中为该 run 创建视图：

- **过滤条件**：`批次ID` 等于该 run 的 run_id（如 `run_20260323_214437`）
- **排序**：按 `排名` 升序
- **视图命名**：推荐格式 `{run_id} 批次`（如 `20260323_214437 批次`）

---

## 5. quality_note 自动生成规则

| 异常类型 | 判断条件 | 写入内容 |
|---------|---------|---------|
| identity 冲突 | has_conflict = true | `identity conflict: {name} 存在身份冲突` |
| 文案分数不同步 | core_judgement 中提取分数与 total_score 差值 > 1.0 | `judgement score mismatch` |
| evidence 占位 | dimension_evidence 匹配正则 `^[\u4e00-\u9fa5a-zA-Z_]+\u7ef4\u5ea6\u8bc4\u4f30$` | `dimension evidence too generic` |

---

## 6. 唯一键与写入策略

| 表 | 唯一键 | 重复发布行为 |
|---|--------|------------|
| Runs | 批次ID | 存在则 UPDATE（幂等） |
| Candidates | 批次ID + 候选人ID | 同一 run 重复发布则 UPDATE；不同 run 保留多条 |

---

## 7. 飞书表格配置信息

| 项目 | 值 |
|------|-----|
| App Token | `AINFbZLOQaSo6rslOeZc95RTnPb` |
| App URL | https://ucn43sn4odey.feishu.cn/base/AINFbZLOQaSo6rslOeZc95RTnPb |
| Runs 表 ID | `tblv1QR1VRirZZGn` |
| Candidates 表 ID | `tblbiUBEv7rDWlli` |
| 当前视图 ID | `vewqA66fy1`（20260323_214437 批次）|

---

## 8. 待手动完成的配置

| 项目 | 操作 |
|------|------|
| Candidates 表字段顺序 | 在飞书 UI 中拖拽字段，使核心字段（排名~核心判断）前置 |
| Candidates 视图过滤 | 在飞书 UI 中设置过滤条件：批次ID = `run_20260323_214437`，排序：排名 升序 |
| Runs 表 结果视图 字段 | 在飞书 UI 中填入该 run 对应 Candidates 视图的 URL |

---

*最后更新：2026-03-24（V1.1：新增 resume_link、精简反馈字段至4项）*
