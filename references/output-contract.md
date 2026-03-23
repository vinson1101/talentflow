# 输出契约（Output Contract）

本文件定义 HuntMind 在招聘决策阶段输出结果必须满足的结构约束。

## 基本要求

- 输出必须是一个合法 JSON object
- 不允许输出 Markdown、解释、前后缀或额外文本
- 所有字段必须符合既定输出结构
- 不允许遗漏 required 字段

## 顶层字段

输出必须包含：
- `overall_diagnosis`
- `top_recommendations`
- `batch_advice`

## recommendation 字段要求

每个 recommendation 必须包含：
- `candidate_id`
- `rank`
- `total_score`
- `decision`
- `priority`
- `action_timing`
- `core_judgement`
- `reasons`
- `risks`
- `structured_score`
- `score_breakdown`
- `action`

## action 字段要求

每个 `action` 必须包含：
- `should_contact`
- `hook_message`
- `verification_question`
- `message_template`
- `deep_questions`

## decision 合法枚举

`decision` 只能是：
- `strong_yes`
- `yes`
- `maybe`
- `no`

## rank / score 规则

- `rank` 必须从 1 开始递增
- `rank=1` 表示当前批次最值得优先联系的人
- `total_score` 使用 0-100 分

---

## structured_score（主评分结构）

**，以后以本结构为准，旧 score_breakdown 仅作兼容层。**

`structured_score` 包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `template_id` | string | 命中的模板 ID |
| `dimension_scores` | object | 7 个维度的原始分数，0-100 |
| `dimension_evidence` | object | 7 个维度的简短依据 |
| `weight_snapshot` | object | 实际使用的权重（模板+修正后） |
| `weighted_total` | float | 脚本重算的加权总分 |

### dimension_scores 维度定义

| 维度 | 说明 |
|------|------|
| `hard_skill_match` | 与 JD 核心要求的直接匹配度 |
| `experience_depth` | 相关经验的深度，不等于年限 |
| `innovation_potential` | 模糊问题中的判断与迁移能力 |
| `execution_goal_breakdown` | 目标拆解与落地推进能力 |
| `team_fit` | 团队协作适配度 |
| `willingness` | 岗位接受意愿与现实可行性 |
| `stability` | 履历连续性与稳定性风险 |

### dimension_evidence 要求

每个维度的 evidence 必须是简短字符串，描述该维度的主要判断依据。

### 示例

```json
{
  "structured_score": {
    "template_id": "senior_product_complex",
    "dimension_scores": {
      "hard_skill_match": 86,
      "experience_depth": 84,
      "innovation_potential": 72,
      "execution_goal_breakdown": 80,
      "team_fit": 70,
      "willingness": 78,
      "stability": 68
    },
    "dimension_evidence": {
      "hard_skill_match": "具备B端和医疗相关产品经历，与JD must-have直接相关",
      "experience_depth": "有5年以上产品经验，并参与多端产品完整落地",
      "innovation_potential": "有一定产品判断，但0-1探索证据一般",
      "execution_goal_breakdown": "有评审、路线图、跨团队推进和版本管理经验",
      "team_fit": "具备培训新人和协同经验",
      "willingness": "岗位方向连续，地点与行业大体匹配",
      "stability": "近几年履历基本连续，但存在一段较短经历需确认"
    },
    "weight_snapshot": {
      "hard_skill_match": 30,
      "experience_depth": 25,
      "innovation_potential": 15,
      "execution_goal_breakdown": 15,
      "team_fit": 5,
      "willingness": 5,
      "stability": 5
    },
    "weighted_total": 80.4
  }
}
```

---

## score_breakdown（Legacy 兼容层）

**本字段为兼容层，由 runner 在 sanitize 阶段自动从 structured_score 映射生成。模型无需直接输出此字段。**

legacy 映射关系：

| Legacy 字段 | 来源 |
|-------------|------|
| `hard_skill` | hard_skill_match |
| `experience` | experience_depth |
| `stability` | stability |
| `potential` | (innovation_potential + execution_goal_breakdown) / 2 |
| `conversion` | willingness * 0.7 + team_fit * 0.3 |

---

## 结构 vs 守门

本文件定义语言层约束；
真正的结构合法性与字段完整性，必须再由脚本校验：
- `scripts/validate_model_output.py`
- `scripts/quality_gate.py`
