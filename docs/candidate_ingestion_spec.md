# HuntMind Candidate Ingestion Spec v0.1

## 目标

把任意渠道的简历文件，稳定转换成符合 `input.schema.json` 的 `candidates[]`。

适用来源：
- 飞书机器人
- 钉钉机器人
- 网页上传
- 本地目录
- 其他具备文件读取能力的 channel

---

## 核心原则

1. 决策层只接受标准化后的 candidate object。
2. 渠道差异只存在于"拿文件"阶段。
3. 简历读入层的唯一职责是：
   - 获取文本
   - 标准化
   - 映射字段
4. 不在 ingestion 层过度做复杂判断。
5. 不把失败简历静默吞掉。

---

## 输入对象

读入层接收的原始文件对象，应至少包含以下信息：

```json
{
  "source_platform": "feishu|dingtalk|upload|local",
  "file_id": "string",
  "file_name": "string",
  "file_path": "string",
  "file_url": "string",
  "folder_id": "string",
  "channel": "string",
  "mime_type": "string"
}
```

**说明**：
- 不同渠道字段来源可以不同
- 但进入 ingestion 层时，应尽量映射成统一文件对象
- `file_path`、`file_url`、`folder_id`、`channel`、`mime_type` 可按实际情况为空或缺失

---

## 标准输出对象

每份进入 Agent 的 candidate 至少必须具备：

```json
{
  "id": "string",
  "name": "string",
  "raw_resume": "string"
}
```

其余字段为增强项：

```json
{
  "current_salary": "string",
  "expected_salary": "string",
  "current_status": "active|passive|not_looking",
  "location": "string",
  "extra_info": "string",
  "source": {
    "platform": "string",
    "channel": "string",
    "file_id": "string",
    "file_name": "string",
    "folder_id": "string",
    "file_url": "string"
  },
  "ingestion_meta": {
    "parse_status": "string",
    "parse_method": "string",
    "text_length": 12345,
    "is_truncated": false
  }
}
```

---

## 字段生成规则

### 1. id

**优先级**：
1. 平台文件唯一 ID
2. 文件 token / media_id / file_id
3. source + file_name + content_hash

**建议格式**：
- `feishu_<file_id>`
- `dingtalk_<file_id>`
- `upload_<hash>`

**要求**：
- 同一份简历重复读入时尽量稳定
- 可用于日志追踪和结果回写

---

### 2. name

**优先级**：
1. 文件名提取
2. 简历正文前部提取
3. 回退为文件名 stem

第一版建议默认从文件名提取，不做复杂 NLP。

---

### 3. raw_resume

**要求**：
- 尽量完整
- 尽量干净
- 保持原始顺序
- 适合大模型直接消费

**最小处理步骤**：
1. PDF / DOC / DOCX 转文本
2. 去除空字符和明显乱码
3. 合并连续空行
4. 去除明显重复页眉页脚
5. 超长时截断

---

### 4. current_salary / expected_salary / current_status / location

**规则**：
- 能稳定提取再填
- 不能稳定提取时允许缺失
- 不要为了填字段强行猜测

---

### 5. extra_info

用于放补充说明，例如：
- 来源渠道
- 文件名
- 解析状态
- 是否截断
- 页数或文本长度信息

---

### 6. source

用于记录来源追踪信息，例如：
- 平台
- channel
- 文件 ID
- 文件名
- 文件夹 ID
- 文件 URL

该字段用于日志、结果回写、来源追溯，不参与核心决策。

---

### 7. ingestion_meta

用于记录读入元信息，例如：
- `parse_status`
- `parse_method`
- `text_length`
- `is_truncated`

该字段用于调试、质量监控、排障。

---

## 失败处理规则

读入失败对象不得进入 `candidates[]`。

必须在 ingestion 层内部记录失败信息：

```json
{
  "file_name": "xxx.pdf",
  "status": "failed",
  "reason": "pdf text empty"
}
```

建议至少保留以下失败信息：
- `file_id`
- `file_name`
- `status`
- `reason`

---

## 推荐流水线

```
source adapter
  -> file objects
  -> text parser
  -> candidate normalizer
  -> input.schema payload
  -> HuntMind agent
```

---

## 当前版本边界

v0.1 暂不处理：
- OCR 兜底
- 候选人多文件合并
- 中英文简历去重
- 复杂字段抽取
- 结构化工作经历建模

当前版本目标只有一个：
**保证任意来源简历，可以稳定进入 HuntMind 决策层。**
