# 飞书多维表格字段映射文档

> 本文档说明 TalentFlow 输出数据如何映射到飞书多维表格字段。  
> 对应代码：`core/feishu_bitable_writer.py`

---

## 一、数据来源

| 飞书数据源 | 说明 |
|-----------|------|
| `final_output.json` | 候选人决策真相（top_recommendations 列表） |
| `quality_meta.json` | 批次质量元数据 |
| `run_meta.json` | 运行时元数据（当前版本未使用） |
| `owner_summary.md` | HR 可读摘要 |
| `batch_input.json` | JD 信息和候选人输入列表 |

---

## 二、Runs 表字段映射

| 飞书字段名 | 类型 | 数据来源 | 说明 |
|-----------|------|---------|------|
| `run_id` | 文本 | 解析 final_output_path | 格式：`run_YYYYMMDD_HHMMSS` |
| `jd_title` | 文本 | batch_input.jd.title | JD 标题 |
| `jd_location` | 文本 | batch_input.jd.location | 工作地点 |
| `jd_salary_range` | 文本 | batch_input.jd.salary_range | 薪资范围 |
| `candidate_count` | 数字 | quality_meta.candidate_count | 候选人总数 |
| `contact_count` | 数字 | quality_meta.candidate_count × quality_meta.contact_ratio | 应联系人数 |
| `top_candidate_names` | 文本 | final_output.top_recommendations 中 priority=A 的候选人姓名 | 逗号分隔 |
| `quality_score` | 数字 | quality_meta.quality_score | 质量分（0-100） |
| `quality_flag` | 文本 | quality_meta.quality_flag | 质量标记（ok/warn/error） |
| `identity_conflict_count` | 数字 | quality_meta.identity_conflict_count | 身份冲突人数 |
| `avg_score` | 数字 | quality_meta.avg_score | 平均分 |
| `output_version` | 文本 | 固定值 "v1" | 输出版本标记 |
| `owner_summary` | 文本 | owner_summary.md 原文 | HR 摘要（截断至5000字） |
| `batch_input_path` | 文本 | batch_input.json 绝对路径 | 追溯用 |
| `final_output_path` | 文本 | final_output.json 绝对路径 | 追溯用 |
| `created_at` | 日期 | 当前时间（毫秒时间戳） | 批次创建时间 |

---

## 三、Candidates 表字段映射

### 基础识别（6个字段）

| 飞书字段名 | 类型 | 数据来源 | 说明 |
|-----------|------|---------|------|
| `run_id` | 文本 | 同 Runs 表 run_id | 关联批次 |
| `candidate_id` | 文本 | final_output.candidate_id | 全局唯一ID |
| `candidate_name` | 文本 | final_output.candidate_name | 候选人姓名 |
| `canonical_name` | 文本 | final_output.identity_meta.canonical_name | 规范姓名（去别名后） |
| `role_label` | 文本 | final_output.role_label | 角色标签 |
| `source_platform` | 文本 | 固定值 "local" | 数据来源平台 |
| `source_file_name` | 文本 | batch_input.raw_resume.ingestion_meta.original_file_name | 原始文件名 |

### AI 决策主字段（13个字段）

| 飞书字段名 | 类型 | 数据来源 | 说明 |
|-----------|------|---------|------|
| `rank` | 数字 | final_output.rank | 排名（1-N） |
| `total_score` | 数字 | final_output.total_score | 综合评分（保留2位小数） |
| `decision` | 文本 | final_output.decision | strong_yes/yes/maybe/no |
| `priority` | 文本 | final_output.priority | A/B/C |
| `action_timing` | 文本 | final_output.action_timing | today/this_week/optional |
| `should_contact` | 复选框 | final_output.action.should_contact | true/false |
| `core_judgement` | 文本 | final_output.core_judgement | 核心判断文本 |
| `reasons` | 文本 | final_output.reasons[] | 数组→每项一行 |
| `risks` | 文本 | final_output.risks[] | 数组→每项一行 |
| `verification_question` | 文本 | final_output.action.verification_question | 核实问题 |
| `hook_message` | 文本 | final_output.action.hook_message | 钩子消息 |
| `message_template` | 文本 | final_output.action.message_template | 联系话术模板 |

### 7维评分（10个字段）

| 飞书字段名 | 类型 | 数据来源 | 说明 |
|-----------|------|---------|------|
| `hard_skill_match` | 数字 | structured_score.dimension_scores.hard_skill_match | 硬技能匹配 |
| `experience_depth` | 数字 | structured_score.dimension_scores.experience_depth | 经验深度 |
| `innovation_potential` | 数字 | structured_score.dimension_scores.innovation_potential | 创新潜力 |
| `execution_goal_breakdown` | 数字 | structured_score.dimension_scores.execution_goal_breakdown | 执行拆解 |
| `team_fit` | 数字 | structured_score.dimension_scores.team_fit | 团队适配 |
| `willingness` | 数字 | structured_score.dimension_scores.willingness | 接受意愿 |
| `stability` | 数字 | structured_score.dimension_scores.stability | 履历稳定性 |
| `template_id` | 文本 | structured_score.template_id | 评分模板ID |
| `weighted_total` | 数字 | structured_score.weighted_total | 加权总分 |
| `dimension_evidence_summary` | 文本 | structured_score.dimension_evidence（7维拼接） | 证据摘要，每维一行 |

### 质量与身份（4个字段）

| 飞书字段名 | 类型 | 数据来源 | 说明 |
|-----------|------|---------|------|
| `has_identity_conflict` | 复选框 | identity_meta.has_conflict | 是否有身份冲突 |
| `identity_resolution` | 文本 | identity_meta.resolution | 冲突解决方案 |
| `conflict_fields` | 文本 | identity_meta.conflict_fields[] | 冲突字段列表 |
| `quality_note` | 文本 | 空字符串（预留） | 质量备注 |

### 人工跟进字段（8个字段，本轮表结构预留，脚本不覆盖）

| 飞书字段名 | 类型 | 写入规则 |
|-----------|------|---------|
| `follow_up_status` | 文本 | 脚本不写入，HR手动填写 |
| `hr_owner` | 文本 | 脚本不写入，HR手动填写 |
| `hr_comment` | 文本 | 脚本不写入，HR手动填写 |
| `interview_result` | 文本 | 脚本不写入，HR手动填写 |
| `reject_reason` | 文本 | 脚本不写入，HR手动填写 |
| `manual_priority` | 文本 | 脚本不写入，HR手动填写 |
| `manual_override_note` | 文本 | 脚本不写入，HR手动填写 |
| `final_outcome` | 文本 | 脚本不写入，HR手动填写 |

---

## 四、数组字段处理规则

以下字段在写入前会将数组转为适合表格展示的文本格式：

| 字段名 | 转换规则 | 示例 |
|--------|---------|------|
| `reasons` | 每项一行，用 `\n` 连接 | "第1条原因\n第2条原因\n第3条原因" |
| `risks` | 每项一行，用 `\n` 连接 | "风险1\n风险2" |
| `top_candidate_names` | A级候选人逗号分隔 | "邢威峰, 李蓓" |
| `conflict_fields` | 每项一行 | "name\nemail" |
| `dimension_evidence_summary` | 每维一行，格式 `[维度名] 内容` | "[hard_skill_match] 5年产品经验..." |

---

## 五、写入规则

### 幂等性保证

- **Runs 表**：`run_id` 唯一，同一 run_id 重复写入会产生重复记录
  - 当前版本未做 UPSERT，需要 HR 自行去重或手动管理
- **Candidates 表**：按 `run_id + candidate_id` 联合唯一
  - 同一候选人不同 run 允许保留多条记录（不合并历史）

### 人工字段保护

以下字段在写入时设为空字符串 `""`，不会覆盖历史数据：
- `follow_up_status`、`hr_owner`、`hr_comment`、`interview_result`
- `reject_reason`、`manual_priority`、`manual_override_note`、`final_outcome`

### 字段类型注意事项

| 字段类型 | 飞书 type 值 | 写入格式 |
|---------|------------|---------|
| 文本 | 1 | 直接字符串 |
| 数字 | 2 | Number（浮点） |
| 单选 | 3 | 字符串（选项名） |
| 多选 | 4 | 字符串数组 `["A","B"]` |
| 日期 | 5 | 毫秒时间戳（整数） |
| 复选框 | 7 | Boolean（true/false） |

---

## 六、飞书多维表格配置信息

| 项目 | 值 |
|------|-----|
| App Token | `AINFbZLOQaSo6rslOeZc95RTnPb` |
| App 名称 | TalentFlow Results |
| App URL | https://ucn43sn4odey.feishu.cn/base/AINFbZLOQaSo6rslOeZc95RTnPb |
| Runs 表 ID | `tbl5gnhs4x8iAJon` |
| Candidates 表 ID | `tblGKQ2DFMrJ2Cqd` |

---

*最后更新：2026-03-24*
