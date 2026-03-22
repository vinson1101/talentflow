# TalentFlow - 招聘 Skill / Pipeline

> TalentFlow 是 HuntMind 等上层 bot 的招聘 skill，不是 AI 员工本体。

---

## 项目定位

TalentFlow 的职责很简单：

1. 读取本地目录 / 外部目录中的简历
2. 解析 PDF / 文本并标准化候选人信息
3. 构建并校验 `batch_input`
4. 将 `batch_input` 交给外部 bot 的 decision handler
5. 对 bot 返回结果做结构化后处理并落盘

**TalentFlow 不是招聘 agent。**
**TalentFlow 不负责模型接入，不负责 API key，不负责 base_url，不负责“选脑子”。**

这些都属于上层 bot（如 HuntMind / OpenClaw bot / Claude Code bot）。

---

## 正确边界

### 上层 bot 负责
- 决策主体身份
- 模型选择（GLM / Gemini / Claude / OpenAI 等）
- API 配置与调用
- system prompt / memory / context
- 招聘判断

### TalentFlow 负责
- 简历读取
- 解析与标准化
- batch_input 构建
- runner 后处理
- final_output / final_report / owner_summary / run_meta 落盘

一句话：

**HuntMind 是 AI 招聘员工。TalentFlow 是它的招聘 skill。**

---

## 当前主接口

### Python 接口

```python
from pipelines.process_local_folder import process_local_folder

result = process_local_folder(
    folder_path="./resumes",
    jd_data=jd_data,
    decision_handler=bot_decide,
    bot_name="huntmind",
)
```

其中 `bot_decide(batch_input) -> str` 由外部 bot 提供。
返回值必须是 runner 可消费的 JSON 文本。

### CLI 接口

```bash
python pipelines/process_local_folder.py ./resumes --jd ./jd.json
```

这时 TalentFlow 只会：
- 读取简历
- 生成 `batch_input.json`
- 生成 `run_meta.json`

不会自己调用模型。

如果你要让 CLI 直接跑完整闭环，可以显式传入 bot 提供的 handler：

```bash
python pipelines/process_local_folder.py ./resumes \
  --jd ./jd.json \
  --decision-handler your_bot_module:decide \
  --bot-name huntmind
```

---

## 为什么这样设计

因为 skill 不应该反客为主。

如果 TalentFlow 自己去：
- 读 `openclaw.json`
- 管 API key
- 选择模型
- 直接发 chat/completions

那它就不再是 skill，而是在偷偷长成另一个 bot。

这会直接破坏产品边界。

所以 TalentFlow 现在只接收一个外部 decision handler，
其余关于“脑子”的事情，全部交回给 bot 自己。

---

## 输出产物

运行目录仍然保留这些产物：

- `candidates/`
- `batch_input.json`
- `run_meta.json`
- `final_output.json`（仅在提供 decision handler 时生成）
- `quality_meta.json`（仅在提供 decision handler 时生成）
- `final_report.md`（仅在提供 decision handler 时生成）
- `owner_summary.md`（仅在提供 decision handler 时生成）

---

## 状态字段

`run_meta.json` 中当前重点记录：

- `status`：`no_files` / `prepared_only` / `completed`
- `decision_owner`
- `decision_handler`

这样就能区分：
- 这次只是 skill 做准备
- 还是已经由外部 bot 完成判断

---

## 结论

TalentFlow 现在的目标不是“变成 AI 招聘员工”。
它的目标是：

**成为一个干净、可复用、专为招聘场景服务的 skill / pipeline。**

而 AI 员工本体，始终应该是 HuntMind。
