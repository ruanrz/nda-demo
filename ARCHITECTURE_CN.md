# AI 法律助手 — 技术架构

## 1. 设计目标

基于 Playbook 驱动的 NDA 合同审查，实现**外科手术式精准红线**：最小化编辑、保留原文语言、杜绝幻觉条款。

---

## 2. 审查流水线

单次审查发起 **1–3 次串行 LLM 调用**（外加本地确定性步骤），每次调用承担不同职责并使用不同模型：

```
合同文本 + Playbook 规则
        │
        ▼
┌───────────────────────────────────────────┐
│  Step 0  合同结构解析             (本地)   │
│  基于正则的条款分段。                      │
│  识别 Section / Clause / Sub-clause       │
│  三级层次结构。零延迟、零 token 消耗。     │
└───────────────────┬───────────────────────┘
                    │  结构化条款列表
                    ▼
┌───────────────────────────────────────────┐
│  Step 1  统一分析               (LLM)      │
│  模型：由预设决定                          │
│                                            │
│  输入：完整合同 + 全部 Playbook Markdown   │
│  方法：逐规则结构化推理                    │
│        LOCATE → ASSESS → CLASSIFY          │
│        → PLAN → VERIFY                     │
│  输出：每条规则的 —                        │
│    • 匹配条款（精确引用）                  │
│    • 合规判定：GREEN / YELLOW / RED        │
│    • 简短理由（1–3 条要点）                │
│    • 修改计划：                            │
│        find_text（精确子串）               │
│        replace_with（使用 exact_wording）  │
└───────────────────┬───────────────────────┘
                    │  修改计划列表
                    ▼
┌───────────────────────────────────────────┐
│  Step 2  执行修改                (本地*)   │
│                                            │
│  输入：原文 + Step 1 的修改计划            │
│  方法：确定性的 find → replace 文本替换    │
│  输出：                                    │
│    • final_text（完整修改后合同）          │
│    • 逐项修改 diff                         │
│    • 验证结果（计划数 vs 实际执行数）      │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│  Step 3  Issues List              (LLM)    │
│  （可选，模型由预设决定）                    │
│                                            │
│  输入：分析结果 + 修改结果                  │
│  输出：                                    │
│    • 问题清单（P0/P1/P2 分级）             │
│    • 风险概述                              │
│    • 合规率评分（%）                       │
└───────────────────┬───────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   HTML 红线     Word .docx    Issues 报告
```

**为什么用 2 次调用而非 1 次：** 将分析与执行分离，Step 1 专注于*推理*（哪个条款、哪里不合规、怎么改），Step 2 专注于*精确执行*（逐字文本替换，不做任何创造性发挥）。这种"先规划再行动"的模式在 LLM 评测中始终优于单次端到端生成。

**\*关于 Step 2：** 如果修改计划真的是一组精确的 `find_text → replace_with` 操作，那么执行最好在本地完成，以获得确定性、速度与成本优势。只有当你允许上下文敏感编辑（例如相对标题插入、格式感知修改、多段跨区间编辑）时，才需要模型参与执行阶段。

---

## 3. 模型路由

`LLMClient` 按任务类型自动选择模型，提供两套预设：

### 质量优先（准确率优先于成本时推荐）

| 任务 | 模型 | 选型理由 |
|------|------|---------|
| `analysis` | **o3**（或当前可用最强推理模型） | 最强多步法律推理能力；YELLOW/RED 误判率最低 |
| `execution` | **本地 find/replace** + o3 兜底 | 确定性执行优先；仅当精确匹配失败时回退到模型 |
| `summary` | gpt-4o | 比 mini 更好的综合分析和风险表述 |
| `validation` | gpt-4o | 能捕捉"计划 vs 实际"之间的微妙偏差 |

### 成本优化（高吞吐量生产环境默认）

| 任务 | 模型 | 选型理由 |
|------|------|---------|
| `analysis` | gpt-4o | 推理能力好，成本约为 o3 的 1/5 |
| `execution` | **本地 find/replace** + gpt-4o 兜底 | 同样本地优先策略；兜底使用更轻量模型 |
| `summary` | gpt-4o-mini | 分类任务，mini 足够且成本仅 1/10 |
| `validation` | gpt-4o-mini | 二元正确性校验 |

路由表是一个普通字典，支持逐调用或全局覆盖。客户端兼容 `OPENAI_API_BASE` 环境变量，可对接 Azure OpenAI 或任何 OpenAI 兼容端点。

> **切换方式：** 设置环境变量 `MODEL_PRESET=quality`，或在 Streamlit UI 侧边栏选择预设。质量预设的单次审查成本约为成本优化预设的 5–8 倍，但可显著降低误判率和条款遗漏。

---

## 4. Playbook 体系

### 4.1 格式

每个 Playbook 是一个独立的 Markdown 文件，含 YAML frontmatter：

```markdown
---
id: "4"
title: Compelled Disclosure
type: conditional
priority: P0
---

# 强制披露条款

## Rule Summary
确保当接收方或其代表被法律要求披露保密信息时...

## Rules
### Rule 6.2 — 通知义务修改
- **Type:** conditional
- **Trigger:** 当对方要求接收方在强制披露前发出通知时...
...
```

**Markdown 正文会被原样注入 LLM prompt。** 模型看到的规则与人类在文件中读到的完全一致——没有 JSON 序列化的信息损耗，没有 schema 转换。

### 4.2 规则类型

五种规则类型，各有不同的语义约束：

| 类型 | 触发 → 动作 | LLM 执行行为 |
|------|------------|-------------|
| **add_text** | 检测到关键词 → 在指定位置插入精确文本 | 找到触发词，插入 exact_wording，严格遵守 `insert_position` |
| **checklist** | 条款存在 → 验证所有必要元素是否齐全 | 枚举已有 vs 必需元素，只补充缺失项 |
| **conditional** | 评估 N 个条件 → 条件满足时执行修改 | 逐条件对照合同文本判断，根据结果分支 |
| **simplify** | 检测到冗余表述 → 精简为最小形式 | 保留指定措辞，删除指定措辞 |
| **replace** | 检测到问题措辞 → 替换为首选措辞 | 直接 find/replace，保持前后语法完整 |

### 4.3 偏差分级

每个规则匹配结果使用三级分类（采纳自 [Anthropic 开源法律插件](https://github.com/anthropics/knowledge-work-plugins/tree/main/legal)的方法论）：

| 等级 | 含义 | 后续动作 |
|------|------|---------|
| **GREEN** | 条款符合 Playbook | 不修改 |
| **YELLOW** | 偏差在可修复范围内（P1） | 生成定向红线修改 |
| **RED** | 关键缺失或直接违反 Playbook（P0） | 生成红线修改 + 标记需升级处理 |

---

## 5. Prompt 工程

### 5.1 分析 Prompt — 结构化推理

分析阶段的 system prompt 对每条规则强制执行五步结构化推理：

```
1. LOCATE   — 这条规则指向合同的哪个条款？（精确引用）
2. ASSESS   — 该条款是否合规？差距是什么？
3. CLASSIFY — GREEN / YELLOW / RED
4. PLAN     — 最小化修改：find_text → replace_with，精确定位
5. VERIFY   — 修改后语法和语义是否仍然正确？
```

为保证“可审计”而不依赖模型内部隐式推理，输出应以**证据优先**（精确引用）为主，并附带简短、非敏感的 `rationale`（1–3 条要点）以及可执行的修改计划。

### 5.2 执行 Prompt — 确定性替换

执行阶段的 prompt 刻意收紧约束：

- 精确执行每一条计划中的修改
- find_text → replace_with：直接文本替换
- **不得**进行计划之外的任何改动
- 未修改部分必须**逐字符保持原样**
- 输出**完整**合同文本

这种分离防止了"创造性漂移"——当模型被要求在一次调用中同时分析和编辑时，往往会自行发明改进。

### 5.3 审查模式

两种 prompt 变体改变模型的分析立场：

| 模式 | system prompt 效果 |
|------|-------------------|
| **己方合同（Own Paper）** | 关注 Playbook 合规性。保护性但非对抗性。 |
| **对方合同（Counterparty）** | 标记单边条款、缺失保护、非市场惯例条款。Issues List 着重强调对我方的风险。 |

---

## 6. 输出生成

### 6.1 Word 红线文档

使用 `python-docx` + `diff_match_patch` 生成带原生 Word 审阅修订（`<w:ins>/<w:del>`）的 `.docx`：

| Diff 操作 | 渲染方式 |
|-----------|---------|
| `DIFF_EQUAL` | 黑色，常规字体 |
| `DIFF_DELETE` | 红色，删除线 |
| `DIFF_INSERT` | 红色，加粗，单下划线 |

文档输出包含：
- 所有修改统一使用原生 Word 审阅修订（`<w:ins>/<w:del>`）；
- 当审阅元数据无法表达“修改原因”时，为对应修改附加简短评论；
- Issues List 表格（按严重性着色）。

### 6.2 Issues List

结构化 JSON 数组，每项包含：

```
id, severity (P0/P1/P2), category, title, description,
clause_reference, current_language, recommended_action,
status (resolved/needs_review/informational), playbook_rule
```

外加 `executive_summary`（风险概述）和 `compliance_score`（合规率百分比）。

---

## 7. 关键设计决策

| 决策 | 技术理由 |
|------|---------|
| **Markdown Playbook 而非 JSON** | LLM 原生理解 Markdown；文件可直接人工编辑；git diff 可读性好。与 Anthropic 插件架构理念一致。 |
| **2-call 流水线而非 1-call** | 分析与执行分离防止创造性漂移。每次调用的 system prompt 职责单一、约束清晰。 |
| **双预设路由：质量优先 vs 成本优化** | 质量预设用 o3 做分析（最强推理、最低误判）+ 本地执行；成本预设用 gpt-4o/mini。通过 `MODEL_PRESET` 环境变量切换。 |
| **本地正则解析合同结构而非 LLM** | 正则分段即时且确定性。为 LLM 提供结构提示而不消耗 token。 |
| **GREEN/YELLOW/RED 分级** | 业界标准的偏差分诊体系（Anthropic `/review-contract`、Dioptra 及大多数企业法务团队通用）。输出即可执行。 |
| **exact_wording 强制逐字使用** | Playbook 规则携带 `exact_wording` 字段。prompt 中反复强调"CHARACTER-FOR-CHARACTER"。这是防止过度编辑的最关键约束。 |
| **对方合同模式作为 prompt 变体** | 同一流水线，不同 system instruction。避免代码重复，同时从根本上改变分析立场。 |
