# Evals / Calibration Set 说明

`evals/` 只负责保存 **固定测试输入** 和 **人工真值**，用于对齐 HuntMind 的 shortlist / 建联决策。

Judge 的目标只有一个：

> 比较某次真实运行产出的 `final_output.json` 和 `human_labels.json` 的差异。

它不是线上主链路，也不是历史运行结果仓库。

---

## 一、现在只保留什么

每个 calibration batch 只需要：

```text
evals/
  calibration_set/
    <batch_id>/
      batch_input.json
      human_labels.json
      notes.md   # 可选
```

说明：

- `batch_input.json`：固定测试输入（JD + 测试简历）
- `human_labels.json`：人工真值
- `notes.md`：边界说明，可选

如果某些目录里历史上还留有 `huntmind_output.json`、`final_output.json`、`expected_summary.json` 等文件，当前 Judge 可以忽略它们；这些不再被视为 calibration set 的必需资产。

---

## 二、Judge 比较什么

Judge 比较的是：

- `runs/<run_id>/<batch_id>/final_output.json`
- `evals/calibration_set/<batch_id>/human_labels.json`

也就是说：

- HuntMind 先真实跑完一轮
- runner 在主链路里完成守门
- Judge 再对这次真实结果做比较

Judge 不再负责：

- 调用 HuntMind
- 重跑 runner
- 生成历史 `huntmind_output` 模板
- 内置 fixture 代替正式 batch

---

## 三、为什么 batch 里还保留测试简历

因为回测的最终目标是 **对齐固定测试样本**。

所以 calibration batch 里保留：

- JD
- 测试简历

是合理的。

乱的不是“测试简历还在”，而是“运行结果和真值集混在一起”。

---

## 四、推荐目录职责

```text
evals/
  calibration_set/   # 固定测试输入 + 人工真值
  judge/             # 纯比较脚本
  results/           # Judge 比较结果（运行产物）

runs/
  <run_id>/
    <batch_id>/
      final_output.json
      huntmind_output.json
      owner_summary.md
```

其中：

- `evals/calibration_set/` 是真值集
- `runs/` 是每次真实运行结果
- `evals/results/` 是 Judge 比较结果

---

## 五、当前校准目标

HuntMind 当前阶段校准的不是“谁最后会入职”，而是：

1. 该不该联系
2. 谁该优先联系
3. 不联系 / 降级的主因是否合理

因此，`human_labels.json` 评的是 **shortlist / 建联决策**，不是最终录用结果。

---

## 六、一句话总结

`evals/` 的作用很简单：

> 保存固定测试输入和人工真值，让 Judge 去比较这次真实运行结果和人类判断的差距。
