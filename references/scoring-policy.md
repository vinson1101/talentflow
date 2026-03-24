# 招聘评分政策 - 7维评分体系

> 本文档定义 HuntMind 招聘决策系统的 7 维评分标准。每个维度 0-100 分，模板权重决定最终总分。

---

## 核心原则：宁缺毋滥

**最重要的原则：不要为了"有输出"而强行推荐。**

- 每批简历可以不推荐任何人（`decision` 全为 `no` 或 `maybe`）
- 不是每批都必须有 A 类候选人
- 分数不代表"非选不可"，只代表"匹配程度"
- HR 期望"这批简历质量一般，先不推"——这是**有效输出**，不是系统失败

> ⚠️ **禁止**：因为"这批没人可选"就降低标准，或强行凑出推荐理由。

---

## 1. hard_skill_match

**定义**：候选人与 JD 核心要求的直接匹配度。

**重点看**：
- must_have 是否直接满足
- 是否有相近岗位经历
- 是否有相近产品类型 / 行业 / 业务场景
- 是否承担过对应职责

---

## 2. experience_depth

**定义**：相关方向上的经验深度，不等于简单年限。

**重点看**：
- 年限
- 项目复杂度
- 责任范围
- 是否完整负责过需求-设计-推进-上线链路
- 是否做过高复杂度协同

---

## 3. innovation_potential

**定义**：在模糊问题、新场景、探索性任务中的产品判断与学习迁移能力。

**重点看**：
- 0-1 / 探索型经历
- 主动发现问题、提出方案
- 独立思考痕迹
- 学习与迁移能力

---

## 4. execution_goal_breakdown

**定义**：把抽象目标拆成可执行方案并推进落地的能力。

**重点看**：
- 需求拆解
- PRD / 原型 / 流程设计
- 跨团队推进
- 上线推进与迭代优化
- 推动结果而不是只写文档

---

## 5. team_fit

**定义**：进入现有团队后的协作适配度。

**重点看**：
- 跨部门协作
- 沟通与培训能力
- 组织配合感
- 工作方式是否适合团队

---

## 6. willingness

**定义**：候选人现实推进可能性与岗位接受意愿。

**重点看**：
- 岗位方向一致性
- 地点匹配
- 薪资区间是否大体可接受
- 行业 / 职业路径连续性
- 是否存在明显转化障碍

---

## 7. stability

**定义**：履历连续性与组织稳定性风险。

**重点看**：
- 最近 3-5 年跳槽频率
- 单段任职时长
- 是否连续短停
- 是否存在合理成长路径

**补充规则**：
- "5 年不超过 2 家公司"可作为高分参考信号
- 但不能作为硬性一票否决
- 需保留合理例外（创业、裁员、公司关闭、业务调整等）

---

## 评分 gate（快速决策门控）

### A 类 gate（不满足则不进 A）
- `hard_skill_match < 50` → 不能进入 A
- `willingness < 40` → 不能进入 A
- senior 模板下 `experience_depth < 50` → 不能进入 A

### no 建议 gate（满足以下组合倾向 no）
- `weighted_total < 45` 且 `hard_skill_match < 45` 且 `willingness < 40`

### maybe 建议
- 总分中段，存在一两个关键待验证点

---

## 责任边界：模型判断 vs 脚本算分

### HuntMind（模型）负责
- 对每个维度给出 **0-100 的原始分数**
- 对每个维度写出 **简短判断依据**（evidence）
- 负责 `structured_score.dimension_scores` 和 `structured_score.dimension_evidence`
- 决定 `decision`（strong_yes / yes / maybe / no）
- 给出判断理由（reasons）和风险（risks）

### TalentFlow 脚本负责
- 根据 JD 标题和候选人角色**选择模板**（`b2b_product_general` / `senior_product_complex` / 等）
- 应用**行业修正**（如医疗行业 +hard_skill_match / +experience_depth）
- 用模板权重**重算 weighted_total**，覆盖模型原始 `total_score`
- 从 `structured_score` **映射生成 legacy `score_breakdown`**
- 执行 **gate 检查**（hard_skill / willingness / experience_depth 门槛）
- 决定 **priority**（A/B/C）和 **action_timing**（today / this_week / optional）
- 执行质量守门（identity conflict / decision-action 一致性 / fallback ratio）

### 模型输出要求
HuntMind 输出的 `structured_score` 必须包含：

| 字段 | 说明 |
|------|------|
| `dimension_scores` | 7 个维度的原始分数（0-100），缺失则脚本填 0 |
| `dimension_evidence` | 7 个维度的简短依据字符串，允许空 |
| `template_id` | 模板 ID（参考 `configs/scoring_templates.yaml`，脚本会覆盖） |

### 脚本算分流程
1. **选择模板**：JD 标题命中 → 候选人角色命中 → `default_template`
2. **行业修正**：检测 JD/company_context 中的医疗关键词，应用 healthcare 调整
3. **重算总分**：`weighted_total = Σ(dimension_score × 归一化权重)`
4. **回填 legacy**：`score_breakdown` = 脚本自动映射（不再信任模型原始值）
5. **Gate 检查**：不满足 A-gate 的维度直接降级 priority

### 模板与权重原则
- 权重和必须等于 100
- 不同岗位模板权重不同（高级岗加重经验/硬技能，校招减经验、加重潜力）
- 行业修正为加减法，不改变权重结构
- 行业修正示例：医疗岗 +hard_skill +experience / 创新岗 +innovation_potential

### 禁止事项
- 脚本不得修改 `dimension_scores` 的原始值（只用来算加权总分）
- `score_breakdown` 不再是主评分真相，仅为 legacy 兼容层
- 模型不得省略 `structured_score` 任意维度（缺失由脚本补 0，不抛错）

### rank / total_score 占位策略
- 模型继续输出 `rank` 和 `total_score` 作为**占位值**
- runner 在 sanitize 阶段执行：
  - **`total_score` 由脚本重算的 `weighted_total` 完全覆盖**，模型原始值不参与最终计算
  - **`rank` 由 runner 按重算后的 `total_score` 降序重新排列**（1=最高分）
- validate 阶段**不**因 rank/total_score 占位而报错，脚本负责最终收敛
- 后续可演进为：模型不输出 rank/total_score，runner 完全接管
