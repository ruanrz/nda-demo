# NDA Demo 修复计划

> 基于客户反馈、目标文档对比、代码审查的综合修复方案。
> 日期：2026-03-02

---

## 一、客户反馈问题汇总

| # | 客户原话 | 问题本质 |
|---|---------|---------|
| 1 | "修改意见都没有体现"（Representatives Before/After） | Checklist 类规则分析了但执行未落地 |
| 2 | "修改应该直接在 whether furnished before on after the date hereof 改，而不是前面硬加一个 on or after the date hereof" | Rule 2 执行策略是"插入"而非"替换"，导致与原文矛盾 |
| 3 | "直接矛盾了" | 新旧表述同时出现，语义冲突 |
| 4 | "这里也是，硬塞的，没有自动读取已有文本" | LLM 没有理解上下文就盲插文本 |
| 5 | "然后剩下的都没有改" | 大量应改条款未被触及 |

---

## 二、根因分析

### BUG-1：LLM Fallback 回退覆盖 bug（确定性数据丢失）

**严重等级：P0**

**位置：** `unified_review.py` 第 229-241 行

**现象：** 当本地 find/replace 部分成功、部分失败时，LLM fallback 会：
1. 传入 `contract_text`（原始文本），**丢弃本地已成功的修改**
2. 传入 `mods_for_prompt`（全部修改），**不是只传失败的部分**

```python
# 当前代码（有 bug）
exec_result = client.call_json(
    task_type="execution",
    system_prompt=EXECUTION_SYSTEM_PROMPT,
    user_prompt=EXECUTION_USER_PROMPT.format(
        modifications_json=json.dumps(mods_for_prompt, ...),  # ← 全部修改
        original_text=contract_text,                           # ← 原始文本
    ),
)
```

**后果：** 假设本地成功了 3 条、失败了 2 条，LLM 拿着原文重新执行全部 5 条，本地已成功的 3 条被覆盖。最终结果不可控。

**修复方案：**
```python
# 修复后
exec_result = client.call_json(
    task_type="execution",
    system_prompt=EXECUTION_SYSTEM_PROMPT,
    user_prompt=EXECUTION_USER_PROMPT.format(
        modifications_json=json.dumps(failed, ...),  # ← 只传失败的
        original_text=local_text,                      # ← 用本地已修改的文本
    ),
)
# 同时合并 applied 列表
result["modifications"] = applied + exec_result.get("modifications_applied", [])
```

**工作量：** ~10 行代码

---

### BUG-2：Rule 2 的规则类型导致"硬塞"矛盾

**严重等级：P0**

**位置：** `playbooks/02-transaction-restriction.md`

**现象：** Rule 2 定义为 `add_text` 类型，要求在 "to the Recipient" 后插入 "in connection with the Transaction on or after the date hereof"。但当原文已包含 "whether furnished before or after the date hereof" 时，LLM 按 `add_text` 的指令在前面插入了新文本，原文冲突短语仍保留，形成：

> ...on or after the date hereof...whether furnished before or after the date hereof...

两个时间限定同时存在，直接矛盾。

**根因：** Playbook 规则类型标注为 `add_text`（只插入），但实际场景需要 `replace`（替换冲突内容）。Analysis prompt 虽有 VERIFY 步骤，但 LLM 倾向于遵守 `add_text` 类型约束而非自行判断是否需要替换。

**修复方案：** 修改 playbook 规则，将 Rule 2 升级为 context-aware 替换策略：

```markdown
## Rules

### Rule: rule_2 — Restrict definition scope of 'Confidential Information'

- **Type:** replace
- **Trigger:** When a Confidential Information definition clause exists
- **Action:** Ensure definition is restricted to information provided
  "in connection with the Transaction on or after the date hereof"

#### Execution Strategy

1. **首选：替换冲突短语**
   - 若原文包含 "whether furnished before or after the date hereof"，
     则将该短语替换为 "on or after the date hereof"
   - find: "whether furnished before or after the date hereof"
   - replace: "on or after the date hereof"

2. **备选：定向插入**（仅当上述短语不存在时）
   - 在 "to the Recipient" 或 "to the Receiving Party" 之后插入
     "in connection with the Transaction on or after the date hereof"

#### Constraints

- `[CRITICAL]` 不得在保留 "before or after" 的同时插入 "on or after"
- `[CRITICAL]` 如原文有时间限定短语，必须替换而非叠加
- `[PROHIBITED]` 不得在 "information" 之后插入
```

**工作量：** 修改 1 个 playbook 文件

---

### BUG-3：Checklist 类规则执行不落地（Representatives）

**严重等级：P0**

**位置：** `unified_prompts.py` Analysis prompt + `unified_review.py` `_local_find_replace`

**现象：** UI 中展示了 Representatives 的 Before/After 示例，但正文未被修改。

**根因链：**
1. Analysis prompt 对 checklist 类规则的 `find_text` 指导不足。LLM 通常给出整个 Representatives 定义段落作为 `find_text`，但由于空格、标点、换行的微小差异，本地 exact match 失败
2. 失败后进入 LLM fallback，又因 BUG-1 的回退覆盖问题，结果更不可控
3. 即使 LLM fallback 成功，checklist 的"逐元素补充"策略也容易遗漏——LLM 倾向于做最小插入而非段落级重写

**修复方案（分两步）：**

**步骤 A — 改进 `_local_find_replace` 的匹配鲁棒性：**

```python
import re

def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace sequences to single space, strip edges."""
    return re.sub(r'\s+', ' ', text).strip()

def _local_find_replace(text, modifications):
    applied, failed = [], []
    current = text
    for mod in modifications:
        find = mod.get("find_text", "")
        replace = mod.get("replace_with", "")
        if not find:
            failed.append(mod)
            continue
        # 先尝试精确匹配
        if find in current:
            current = current.replace(find, replace, 1)
            applied.append(...)
        else:
            # 尝试空白归一化匹配
            norm_find = _normalize_whitespace(find)
            norm_current = _normalize_whitespace(current)
            if norm_find in norm_current:
                # 在原文中定位实际位置并替换
                idx = norm_current.index(norm_find)
                # 将归一化后的位置映射回原文...
                current = _replace_by_normalized_match(current, find, replace)
                applied.append(...)
            else:
                failed.append(mod)
    return current, applied, failed
```

**步骤 B — 在 Analysis prompt 中，对 checklist 类型增加执行指导：**

在 `ANALYSIS_SYSTEM_PROMPT` 的 `═══ RULE TYPES ═══` 部分，对 `checklist` 类型补充：

```
**checklist**
Check required elements → plan to add ONLY missing ones, preserve existing.
• find_text MUST be the COMPLETE existing definition/clause text (full paragraph).
• replace_with MUST be the COMPLETE rewritten definition containing all required elements.
• Do NOT attempt word-level insertions for checklist rules — always use full-clause replacement.
```

**工作量：** 修改 `_local_find_replace` 函数 + 修改 analysis prompt

---

### BUG-4：改后无验证，Issues List "假阳性"

**严重等级：P1**

**位置：** `unified_review.py` Step 3 Issues List 生成逻辑

**现象：** Issues List 基于 Step 1 analysis 记录和 Step 2 modifications 记录生成，而非基于 `final_text` 重新审查。因此会出现：
- "resolved" 但实际正文没改对（false positive）
- 本地匹配失败静默丢弃，但 issues 仍标记为 resolved

**修复方案：** 在 Step 3 prompt 的输入中加入 `final_text`，让 LLM 对照最终文本校验修改是否真正落地：

```python
# unified_review.py Step 3
issues_result = client.call_json(
    task_type="summary",
    system_prompt=ISSUES_LIST_SYSTEM_PROMPT,
    user_prompt=ISSUES_LIST_USER_PROMPT.format(
        analysis_json=json.dumps(result["analysis"], ...),
        modifications_json=json.dumps(result["modifications"], ...),
        final_text=result["final_text"],  # ← 新增
        mode_context=mode_ctx,
    ),
)
```

同时修改 `ISSUES_LIST_USER_PROMPT`：

```
═══ FINAL CONTRACT TEXT ═══
{final_text}
═══ END FINAL TEXT ═══

CRITICAL VERIFICATION:
- For each issue marked "resolved", verify the fix is ACTUALLY present in the final text.
- If a planned modification is NOT reflected in the final text, mark status as "needs_review".
- Do NOT mark an issue as "resolved" unless you can quote the corrected text from the final contract.
```

**工作量：** 修改 prompt 模板 + 传参

---

### BUG-5：Playbook 覆盖面不足

**严重等级：P2（架构层面，非 bug）**

**现象：** 目标文件 `Sample NDA -A-1.docx` 是完整的协商修改稿，包含大量条款新增和全段重写。当前 playbook 仅有 6 条规则，覆盖面远不及目标文档。

**说明：** 这不是 pipeline bug，而是 playbook 规则集的覆盖范围限制。即使修复上述所有 bug，也只能在现有 6 条规则范围内做到精确修改，无法自动达到目标文档的全部改动。

**改善方向：**
- 从目标文档对比中学习规则（使用现有 Rule Learning 功能）
- 扩展 playbook 规则集覆盖更多条款
- 这属于产品功能扩展而非 bug 修复

---

## 三、修复优先级与实施清单

### P0（必须立即修复，阻塞演示效果）

| 序号 | 修复项 | 文件 | 改动规模 | 验收标准 |
|------|-------|------|---------|---------|
| P0-1 | LLM fallback 用 local_text + 只传 failed | `unified_review.py` L229-273 | ~10 行 | Fallback 后 local 已成功的修改不丢失 |
| P0-2 | Rule 2 从 add_text 改为 replace（含冲突检测） | `playbooks/02-transaction-restriction.md` | 重写 Rules 段 | "on or after" 与 "before or after" 不再同时出现 |
| P0-3 | Checklist 规则改为整段替换策略 | `unified_prompts.py` ANALYSIS_SYSTEM_PROMPT | 增加 ~5 行提示 | Representatives 定义被完整替换 |

### P1（显著提升质量和稳定性）

| 序号 | 修复项 | 文件 | 改动规模 | 验收标准 |
|------|-------|------|---------|---------|
| P1-1 | 本地匹配空白归一化 | `unified_review.py` `_local_find_replace` | ~30 行 | 空格/换行差异不导致匹配失败 |
| P1-2 | Issues List 改后验证（传入 final_text） | `unified_prompts.py` + `unified_review.py` | ~15 行 | 未实际落地的修改不标 resolved |
| P1-3 | Analysis prompt 增加冲突检测指导 | `unified_prompts.py` ANALYSIS_SYSTEM_PROMPT | 增加 ~8 行提示 | LLM 在 PLAN 阶段检测上下文冲突 |

### P2（体验优化）

| 序号 | 修复项 | 文件 | 改动规模 |
|------|-------|------|---------|
| P2-1 | Issues List 增加三态标记 (planned/applied/verified) | `unified_prompts.py` | 改 prompt |
| P2-2 | UI 区分 "Playbook 示例" vs "本次实际已应用修改" | `demo_app.py` | ~20 行 |

---

## 四、修复的具体代码变更

### 4.1 unified_review.py — BUG-1 修复

**文件：** `providers/unified_review.py`
**行范围：** 229-273

**变更说明：** LLM fallback 分支改为：
1. `original_text` 传 `local_text`（本地已修改版本）
2. `modifications_json` 只传 `failed`（本地未匹配到的修改）
3. 合并 `applied`（本地成功）+ LLM 返回的修改列表

```python
# ── 修复后的 fallback 分支 ──
else:
    logger.info(f"Falling back to LLM for {len(failed)} unresolved modifications")
    _progress("execution", f"LLM fallback for {len(failed)} modifications…")
    exec_result = client.call_json(
        task_type="execution",
        system_prompt=EXECUTION_SYSTEM_PROMPT,
        user_prompt=EXECUTION_USER_PROMPT.format(
            modifications_json=json.dumps(failed, ensure_ascii=False, indent=2),
            original_text=local_text,  # 基于本地已修改的文本
        ),
        temperature=0.0,
        max_tokens=8192,
    )

    llm_mods = exec_result.get("modifications_applied", [])
    result["modifications"] = applied + llm_mods  # 合并本地成功 + LLM 补充
    result["final_text"] = exec_result.get("final_text", local_text)
```

### 4.2 unified_review.py — _local_find_replace 空白归一化

**文件：** `providers/unified_review.py`
**行范围：** 343-379

**变更说明：** 精确匹配失败后，尝试空白归一化匹配。

```python
import re

def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def _local_find_replace(text, modifications):
    applied, failed = [], []
    current = text

    for mod in modifications:
        find = mod.get("find_text", "")
        replace = mod.get("replace_with", "")
        if not find:
            failed.append(mod)
            continue

        if find in current:
            current = current.replace(find, replace, 1)
            applied.append({...})
            continue

        # 空白归一化 fallback
        norm_find = _normalize(find)
        norm_cur = _normalize(current)
        if norm_find and norm_find in norm_cur:
            # 用正则构建弹性匹配 pattern
            escaped_words = [re.escape(w) for w in norm_find.split()]
            flex_pattern = r'\s+'.join(escaped_words)
            match = re.search(flex_pattern, current)
            if match:
                current = current[:match.start()] + replace + current[match.end():]
                applied.append({...})
                continue

        failed.append(mod)

    return current, applied, failed
```

### 4.3 playbooks/02-transaction-restriction.md — Rule 2 修复

**变更说明：** 从盲目插入改为优先替换冲突短语，仅在不存在冲突时才做定向插入。

完整替换文件的 `## Rules` 段，增加 `#### Execution Strategy` 小节（见上方 BUG-2 修复方案）。

### 4.4 unified_prompts.py — Checklist 执行指导

**文件：** `providers/unified_prompts.py`
**行范围：** 39-43（ANALYSIS_SYSTEM_PROMPT 的 checklist 段）

**变更说明：** 强化 checklist 类型的 find_text/replace_with 要求。

在 `**checklist**` 段后追加：

```
IMPORTANT for checklist rules:
- find_text MUST be the COMPLETE existing clause/definition text (full paragraph, not a fragment).
- replace_with MUST be the COMPLETE rewritten clause containing ALL required elements.
- Do NOT attempt word-level or phrase-level insertions for checklist rules.
- Always use full-clause replacement to avoid partial edits that miss elements.
```

### 4.5 unified_prompts.py — Analysis prompt 冲突检测

**文件：** `providers/unified_prompts.py`
**行范围：** 73-75（VERIFY 步骤）

**变更说明：** 在 VERIFY 步骤中增加冲突检测要求。

```
  5. VERIFY  – Will grammar and meaning remain correct after the change?
     - CHECK: Does the replacement/insertion contradict any EXISTING text in the same clause?
     - CHECK: If inserting a time restriction ("on or after"), does the clause already contain
       a DIFFERENT time restriction ("before or after")? If yes, use REPLACE instead of INSERT.
     - If a conflict is detected, adjust the plan: use find_text to capture the conflicting
       phrase and replace_with to substitute it (not append alongside it).
```

### 4.6 unified_prompts.py — Issues List 验证

**文件：** `providers/unified_prompts.py`
**行范围：** 207-244（ISSUES_LIST_USER_PROMPT）

**变更说明：** 增加 `{final_text}` 输入和验证指令。

在 `═══ END MODIFICATIONS ═══` 之后、`{mode_context}` 之前追加：

```
═══ FINAL CONTRACT TEXT (for verification) ═══
{final_text}
═══ END FINAL TEXT ═══

CRITICAL VERIFICATION REQUIREMENT:
- For each issue you mark as "resolved", you MUST verify that the fix is actually present
  in the FINAL CONTRACT TEXT above. Quote the corrected text as evidence.
- If a planned modification does NOT appear in the final text, set status = "needs_review",
  NOT "resolved".
- An issue is only "resolved" if you can find the corrected language in the final text.
```

---

## 五、验收测试

修复完成后，使用 `Sample NDA -A-1 (ori).docx` 作为输入，验证以下场景：

| 测试项 | 预期结果 | 通过标准 |
|-------|---------|---------|
| Rule 2 时间限定 | "before or after" 被替换为 "on or after"，不出现两者同时存在 | final_text 中无 "whether furnished before or after" |
| Rule 3 Representatives | 定义段被完整替换，包含所有 8 个 required elements + qualifier | final_text 包含 "affiliates", "professional advisors", "financing sources", "consultants", "agents" |
| Local 成功项不丢失 | 本地匹配成功的修改在 LLM fallback 后仍保留 | 对比 final_text 确认 trade secret qualifier 仍存在 |
| Issues List 准确性 | 未实际落地的修改不标 resolved | 任何标 resolved 的 issue 都能在 final_text 中找到对应修改 |
| 无语义矛盾 | 最终文本无自相矛盾的表述 | 人工审读无逻辑冲突 |

---

## 六、局限性说明

即使完成上述所有修复，当前系统与目标文档 `Sample NDA -A-1.docx` 仍会有差距，因为：

1. **Playbook 覆盖面限制：** 当前仅 6 条规则，目标文档的修改远超此范围
2. **条款新增能力缺失：** 当前 pipeline 只能修改已有条款，无法从零新增完整条款
3. **格式保留限制：** .docx 解析为纯文本后丢失格式信息，输出的 redline 文档格式与原文不同

这些属于产品功能扩展范畴，不在本次 bug 修复范围内。
