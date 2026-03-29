# sales_director_batch_001

本批用于校准销售总监岗位的 shortlist / 建联决策。

## 当前状态
- 这是从 judge 现有 fixture 落盘出的正式 calibration batch。
- 目的不是扩样本，而是让 judge 读取 `calibration_set`，不再走代码内置 fixture。

## 重点观察
- `low_fit + high_willingness` 不得被抬成高推进
- `hard_mismatch` 保护应保持稳定
