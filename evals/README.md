# Evals / Calibration Set 说明

本目录用于存放 HuntMind 的离线评估与校准样本。

它不是线上主链路的一部分，也不是最终录用结果库。这里的核心目标只有一个：

> 校准 HuntMind 在“是否值得建联 / 谁该优先建联 / 为什么不该建联”上的决策一致性与相对准确性。

---

## 一、目录定位

本目录里的样本，主要用于：

1. Calibration
   - 对比 HuntMind 输出与人工参考判断
   - 观察 `decision / priority / match_fit / recruitability / mismatch_type` 是否稳定
2. Regression
   - 在修改 SOUL 决策原则、模板规则、runner 收敛逻辑后
   - 检查关键 case 是否被改坏
3. Error Review
   - 沉淀高价值错例
   - 重点看错推、错杀、错路由、`recruitability != willingness` 失守

---

## 二、当前校准目标

HuntMind 当前阶段校准的不是“谁最后会入职”，而是：

1. 该不该联系
2. 谁该优先联系
3. 不联系 / 降级的主因对不对

因此，本目录是 shortlist / 建联决策校准集，而不是最终录用真值集。

---

## 三、推荐目录结构

```text
evals/
  calibration_set/
    product_manager_batch_001/
      jd.json
      candidates.json
      human_labels.json
      notes.md
      expected_summary.json
```

如果仍保留历史命名 `golden_set/` 也可以，但语义上应理解为：这里存放的是 HuntMind 的建联决策校准样本，不是最终录用标准答案。

---

## 四、每个 batch 的文件职责

### 1. `jd.json`

存放该 batch 对应的结构化 JD。

建议字段至少包括：

- `title`
- `must_have`
- `nice_to_have`
- `salary_range`
- `base_location`
- `seniority_level`
- `language_requirements`
- `eligibility_constraints`
- `travel_or_relocation`
- `domain_tags`
- `company_context`

说明：

- 这里放的是用于评估的标准 JD 输入
- 不要求由 `jd_parser.py` 自动生成
- 可以由人工整理，也可以由 HuntMind 先整理后存入

### 2. `candidates.json`

存放该 batch 的标准化候选人列表。

每个候选人建议至少包含：

- `id`
- `name`
- `raw_resume`

可选补充：

- `location`
- `current_salary`
- `expected_salary`
- `extra_info`

说明：

- 这里存放的是用于跑批评估的候选人输入
- 尽量保持与主链路 `batch_input` 所需对象一致

### 3. `human_labels.json`

这是最核心的文件。它存放的是人工参考判断，也就是当前 batch 的校准真值。

每个候选人建议至少标注：

- `candidate_id`
- `should_contact`
- `priority`
- `decision`
- `match_fit`
- `recruitability`
- `mismatch_type`
- `primary_reason`
- `comment`

推荐枚举：

- `priority`: `A / B / C / N`
- `decision`: `strong_yes / yes / maybe / no`
- `match_fit`: `high / medium / low`
- `recruitability`: `high / medium / low`
- `mismatch_type`: `none / recoverable / hard_mismatch`
- `primary_reason`:
  - `fit_and_reachable`
  - `low_match_fit`
  - `low_recruitability`
  - `hard_mismatch`
  - `recoverable_but_uncertain`
  - `insufficient_info`
  - `other`

### 4. `notes.md`

存放该 batch 的说明与边界样本备注。

建议写清楚：

- 该 batch 对应什么类型 JD
- 本批重点观察什么风险
- 哪些候选人是故意放进来的边界 case
- 哪些 case 用于验证错路由 / 低可达 / 高意愿误抬升等问题

### 5. `expected_summary.json`

存放这一批样本的批次级期望结果。

建议包含：

- `expected_top_contact_ids`
- `expected_no_contact_ids`
- `risk_focus`

这个文件不是逐候选人真值，而是该 batch 的整体期望摘要。

---

## 五、如何建立一个新 batch

1. 选定一个真实 JD
2. 准备 5 到 10 份候选人
3. 整理出 `jd.json` 与 `candidates.json`
4. 人工标注 `human_labels.json`
5. 补 `notes.md`
6. 补 `expected_summary.json`

建议先由你独立标一遍，再由合伙人复核，只讨论分歧样本。

---

## 六、推荐优先建设的 batch

1. `product_manager_batch_001`
2. `generic_titles_batch_001`
3. `ops_manager_batch_001`
4. `sales_director_batch_001`
5. `rd_engineer_batch_001`

其中 `generic_titles_batch_001` 重点覆盖：

- 项目经理
- 负责人
- 经理
- director
- head

---

## 七、每次规则修改后怎么使用这些 batch

当以下内容发生变化时：

- SOUL 决策原则
- decision policy
- scoring templates
- runner 决策收敛逻辑
- mismatch / recruitability 规则

应使用校准集进行离线对比。

固定 batch 样本，用当前版本 HuntMind + runner 重跑，再和 `human_labels.json` 对比。

优先看这 6 个指标：

1. `should_contact` 一致率
2. `priority` 一致率
3. Top-N 命中率
4. 误推率
5. 错杀率
6. `primary_reason` 一致率

建议回测结果落到：

```text
evals/
  results/
    YYYY-MM-DD_commit/
      batch_id/
        model_output.json
        final_output.json
        compare.json
        summary.md
```

---

## 八、当前最值得盯的错误类型

1. 错推
2. 错杀
3. 错路由
4. `recruitability != willingness` 失守
5. `hard_mismatch` 保护失效

---

## 九、当前阶段不要做的事

1. 不要把校准集做成最终录用结果集
2. 不要一开始就追求大规模样本
3. 不要先校准细颗粒度分数
4. 不要把所有 case 都塞进同一个 batch
5. 不要让 `jd_parser.py` 承担 JD 主语义提取责任

---

## 十、一句话总结

本目录的作用是：用一批可复跑、可对照、可校准的 JD + 候选人样本，持续校准 HuntMind 的建联决策质量。
