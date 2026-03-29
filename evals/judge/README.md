# Judge

Judge 只做一件事：

> 比较某次真实运行产出的 `final_output.json` 和 `human_labels.json` 的差异。

Judge 不再负责：

- 调用 HuntMind
- 重跑 runner
- 内置 fixture 造样本
- 把历史运行产物当成校准集的一部分

## 目录职责

- `evals/calibration_set/`：固定测试输入与人工真值
- `runs/`：某次真实运行结果
- `evals/judge/`：比较脚本
- `evals/results/<run_id>/`：Judge 产出的 compare / summary / report

## 校准集最小结构

```text
evals/calibration_set/<batch_id>/
  batch_input.json
  human_labels.json
  notes.md   # 可选
```

## 运行方式

```bash
python -m evals.judge.run_judge --config evals/judge/config.json --run-dir runs/<run_id>
```

`run-dir` 下优先按当前真实主链路寻找：

```text
runs/<run_id>/final_output.json
```

如果以后运行结果改成按 batch 落盘，Judge 也兼容：

```text
runs/<run_id>/<batch_id>/final_output.json
```

## 默认支持的 4 类测试

- `product`
- `frontend_dev`
- `blockchain_lead`
- `sales_director`

这些 suite 都必须有正式 calibration batch。Judge 不再 fallback 到脚本内置 fixture。

## 输出结果

结果默认写到：

```text
evals/results/<tag>/
```

每个 batch 会产出：

- `compare.json`
- `summary.json`

全局会产出：

- `report.json`

## Judge 只比较结果

Judge 比较的是：

- 某次真实运行产出的 `final_output.json`
- `evals/calibration_set/<batch_id>/human_labels.json`

它不比较过程，也不要求某次历史 `huntmind_output.json` 成为评估资产。
