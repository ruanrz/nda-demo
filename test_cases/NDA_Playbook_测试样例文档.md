# NDA Playbook 规则测试样例文档

> 基于真实NDA合同的完整测试样例集  
> 创建日期：2026-01-08  
> 更新日期：2026-01-09  
> 规则总数：6 | 测试样例总数：34

---

## 目录

1. [规则1: Qualify 'trade secret' legally](#规则1-qualify-trade-secret-legally)
2. [规则2: Post-signing transaction-related information](#规则2-post-signing-transaction-related-information)
3. [规则3: Definition of Representatives - Checklist](#规则3-definition-of-representatives---checklist)
4. [规则4: Compelled Disclosure](#规则4-compelled-disclosure)
5. [规则5: Third Party Source Exception](#规则5-third-party-source-exception)
6. [规则6: Independent Development Exception](#规则6-independent-development-exception)
7. [测试覆盖统计](#测试覆盖统计)

---

## 规则1: Qualify 'trade secret' legally

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 简单添加 (simple_add) |
| 触发条件 | 当文本中出现 'trade secret' 时 |
| 执行动作 | 在 'trade secret' 后添加 '(as defined by applicable law)' |
| 优先级 | P1 |

### 测试样例

#### TC1-01: 基本场景 - 单个 trade secret

**输入：**
```
The party shall not disclose any trade secret.
```

**预期输出：**
```
The party shall not disclose any trade secret (as defined by applicable law).
```

**预期动作：** 添加 '(as defined by applicable law)'

---

#### TC1-02: 真实合同 - 保密信息定义中的 trade secret

**来源：** Sample NDA

**输入：**
```
"Confidential Information" will mean any and all technical, non-public, and 
non-technical information provided by the Company to the Recipient, which may 
include without limitation information regarding: (a) patent and patent 
applications; (b) trade secrets; and (c) proprietary and confidential 
information, ideas, techniques, sketches, drawings, works of authorship, 
models, inventions, know-how, processes.
```

**预期输出：**
```
"Confidential Information" will mean any and all technical, non-public, and 
non-technical information provided by the Company to the Recipient, which may 
include without limitation information regarding: (a) patent and patent 
applications; (b) trade secrets (as defined by applicable law); and (c) 
proprietary and confidential information, ideas, techniques, sketches, 
drawings, works of authorship, models, inventions, know-how, processes.
```

**预期动作：** 在 'trade secrets' 后添加 '(as defined by applicable law)'

---

#### TC1-03: 多个 trade secret 出现

**输入：**
```
The Recipient agrees to protect all trade secret information. Any trade secret 
disclosed under this Agreement shall be treated as confidential.
```

**预期输出：**
```
The Recipient agrees to protect all trade secret (as defined by applicable law) 
information. Any trade secret (as defined by applicable law) disclosed under 
this Agreement shall be treated as confidential.
```

**预期动作：** 每个 'trade secret' 后都添加定义说明

---

#### TC1-04: 已有定义 - 不重复添加

**输入：**
```
The party shall not disclose any trade secret (as defined by applicable law).
```

**预期输出：**
```
The party shall not disclose any trade secret (as defined by applicable law).
```

**预期动作：** 已有定义，不修改

---

#### TC1-05: 无 trade secret - 规则不触发

**输入：**
```
The Recipient agrees to keep all confidential information secret and not 
disclose it to any third party.
```

**预期输出：**
```
The Recipient agrees to keep all confidential information secret and not 
disclose it to any third party.
```

**预期动作：** 无 trade secret，规则不触发

---

## 规则2: Post-signing transaction-related information

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 添加文本 (add_text) |
| 触发条件 | 当文档中存在保密信息定义条款时 |
| 执行动作 | 在 'to the Recipient' 或 'to the Receiving Party' 之后添加限定语 |
| 添加内容 | `in connection with the Transaction on or after the date hereof` |
| 优先级 | P0 |

### 关键约束

- **【关键】** 必须插入在 'to the Recipient' 或 'to the Receiving Party' 之后
- **【禁止】** 不能插入在 'information' 之后，这会导致语义错误

### 测试样例

#### TC2-01: 真实合同 - 标准保密信息定义

**来源：** Sample NDA

**输入：**
```
"Confidential Information" will mean any and all technical, non-public, and 
non-technical information provided by the Company to the Recipient, which may 
include without limitation information regarding: (a) patent and patent 
applications; (b) trade secrets; and (c) proprietary and confidential information.
```

**预期输出：**
```
"Confidential Information" will mean any and all technical, non-public, and 
non-technical information provided by the Company to the Recipient in connection 
with the Transaction on or after the date hereof, which may include without 
limitation information regarding: (a) patent and patent applications; (b) trade 
secrets; and (c) proprietary and confidential information.
```

**预期动作：** 在 'to the Recipient' 后添加时间和交易限定

---

#### TC2-02: 使用 Receiving Party 术语

**输入：**
```
"Confidential Information" means any information disclosed by the Disclosing 
Party to the Receiving Party, whether orally or in writing.
```

**预期输出：**
```
"Confidential Information" means any information disclosed by the Disclosing 
Party to the Receiving Party in connection with the Transaction on or after 
the date hereof, whether orally or in writing.
```

**预期动作：** 在 'to the Receiving Party' 后添加限定

---

#### TC2-03: 真实合同 - Evaluation Material 定义

**来源：** Sample NDA

**输入：**
```
All such information furnished to you and your Representatives (as defined below) 
either before or after the date of this agreement, together with analyses, 
compilations, studies, summaries, extracts or other documents or records prepared 
by you or your Representatives which contain or otherwise reflect or are generated 
from such information, are collectively referred to herein as the "Evaluation Material."
```

**预期输出：**
```
All such information furnished to you and your Representatives (as defined below) 
by or on behalf of the Company in connection with the Business Relationship on or 
after the date of this agreement, together with the portions of analyses, compilations, 
studies, summaries, extracts or other documents or records prepared by you or your 
Representatives which contain such information, are collectively referred to herein 
as the "Evaluation Material."
```

**预期动作：** 添加交易和时间限定，删除 'before or'

---

#### TC2-04: 已有限定 - 不重复添加

**输入：**
```
"Confidential Information" means any information provided by the Company to the 
Recipient in connection with the Transaction on or after the date hereof, 
including all technical data.
```

**预期输出：**
```
"Confidential Information" means any information provided by the Company to the 
Recipient in connection with the Transaction on or after the date hereof, 
including all technical data.
```

**预期动作：** 已有限定，不修改

---

#### TC2-05: 错误位置检测 - 无接收方描述

**输入：**
```
"Confidential Information" means any information that is proprietary to the Company.
```

**预期输出：**
```
"Confidential Information" means any information that is proprietary to the Company.
```

**预期动作：** 无 'to the Recipient' 结构，需要判断是否适用

> **备注：** 此场景需要确认：是否只在有明确接收方描述时才添加

---

## 规则3: Definition of Representatives - Checklist

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 清单检查 (checklist) |
| 触发条件 | 当文档中存在 Representatives 定义条款时 |
| 执行动作 | 确保定义包含所有必要的代表类型和限定语 |
| 优先级 | P1 |

### 必需元素清单

| 序号 | 必需元素 |
|------|----------|
| 1 | affiliates |
| 2 | directors |
| 3 | officers |
| 4 | employees |
| 5 | professional advisors |
| 6 | actual or potential debt or financing sources |
| 7 | consultants |
| 8 | agents |

### 必需限定语

```
such parties actually receiving Confidential Information from Recipient or at its direction
```

### 关键约束

- 如果现有条款包含更多的当事方类型，**不要删除**
- 当事方的列出顺序可以不同

### 测试样例

#### TC3-01: 最简定义 - 缺少多个元素

**输入：**
```
"Representatives" means the Recipient's directors, officers and employees.
```

**缺失元素：** affiliates, professional advisors, actual or potential debt or financing sources, consultants, agents

**缺失限定语：** 是

**预期动作：** 补充缺失的代表类型和限定语

---

#### TC3-02: 真实合同 - 较完整但缺少部分元素

**来源：** Sample NDA

**输入：**
```
you may disclose the Evaluation Material or portions thereof to those of your 
directors, officers, employees, members, financial advisors and consultants 
(collectively, the "Representatives") who need to know such information for 
the purpose of evaluating the Business Relationship.
```

**缺失元素：** affiliates, actual or potential debt or financing sources, agents

**缺失限定语：** 是

**预期动作：** 补充 affiliates, financing sources, agents 和限定语

---

#### TC3-03: 真实合同修改后 - 扩展版定义（完整）

**来源：** Sample NDA（修改后）

**输入：**
```
you may disclose the Evaluation Material or portions thereof to those of your 
affiliates and affiliated funds and your and their respective directors, officers, 
employees, members, partners, insurers, potential financing sources, advisors 
(including, but not limited to, legal counsel, accountants, financial advisors 
and consultants) and their respective representatives (those of the foregoing 
who actually receive Evaluation Material from you or at your direction, collectively, 
the "Representatives") who need to know such information for the purpose of 
evaluating the Business Relationship.
```

**缺失元素：** 无

**缺失限定语：** 否

**预期动作：** 已完整，无需修改

> **备注：** 包含了所有必要元素且有限定语

---

#### TC3-04: 有额外元素 - 保留不删除

**输入：**
```
"Representatives" means the Recipient's affiliates, directors, officers, employees, 
professional advisors, actual or potential debt or financing sources, consultants, 
agents, accountants, and legal counsel (such parties actually receiving Confidential 
Information from Recipient or at its direction).
```

**缺失元素：** 无

**缺失限定语：** 否

**额外元素：** accountants, legal counsel

**预期动作：** 已完整且有额外元素，保留所有元素不删除

---

#### TC3-05: 无 Representatives 定义 - 规则不触发

**输入：**
```
The Recipient agrees to keep all Confidential Information strictly confidential 
and shall not disclose such information to any third party without prior written consent.
```

**预期动作：** 无 Representatives 定义条款，规则不触发

---

## 规则4: Compelled Disclosure

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 条件判断 (conditional) |
| 触发条件 | 当文档中存在强制披露相关条款时 |
| 执行动作 | 根据现有条款的特征，决定是否添加监管审查例外条款 |
| 优先级 | P1 |

### 条件检查

| 条件ID | 检查内容 |
|--------|----------|
| cond_1 | 是否同时覆盖 Recipient 和 its Representatives |
| cond_2 | 是否包含法律强制披露的基本情形 (law, regulation, order and legal process) |
| cond_3 | 是否存在通知要求 |

### 条件动作

| 条件 | 动作 |
|------|------|
| cond_1 = false | 补充 'and its Representatives' |
| cond_2 = false | 补充法律强制披露条款 |
| cond_3 = true | 添加监管审查例外条款 |
| cond_3 = false | **不添加**监管审查例外条款 |

### 监管审查例外条款内容

```
Notwithstanding the foregoing, Confidential Information may be disclosed, and no 
notice as referenced above is required to be provided, pursuant to requests for 
information in connection with routine supervisory examinations by regulatory 
authorities with the jurisdiction over you or your Representatives and not directed 
at the disclosing party or the Potential Transaction; provided that you or your 
Representatives, as applicable, inform any such authority of the confidential nature 
of the information disclosed to them and to keep such information confidential in 
accordance with such authority's policies and procedures.
```

### 测试样例

#### TC4-01: 真实合同原文 - 完整强制披露条款

**来源：** Sample NDA

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| cond_1 | ✅ true | "you or any of your Representatives" 同时覆盖 |
| cond_2 | ✅ true | 包含 deposition, interrogatory, subpoena 等 |
| cond_3 | ✅ true | "provide the Company with written notice" |

**输入：**
```
You shall be responsible for any breach of the terms of this agreement by your 
Representatives. If you or any of your Representatives is required (by deposition, 
interrogatory, request for documents, subpoena, civil investigative demand or 
similar process) to disclose any of the Evaluation Material, you shall provide 
the Company with written notice of such requirement as soon as practicable after 
learning of it, shall furnish only that portion of the Evaluation Material which 
you are advised by written opinion of counsel is legally required and only in the 
manner legally required, and shall exercise best efforts to obtain assurance that 
confidential treatment will be accorded such Evaluation Material. In addition, you 
acknowledge that the Company may also take steps as it deems necessary to obtain 
such assurance.
```

**预期动作：** 添加监管审查例外条款

**预期输出：**
```
You shall be responsible for any breach of the terms of this agreement by your 
Representatives. If you or any of your Representatives is required (by deposition, 
interrogatory, request for documents, subpoena, civil investigative demand or 
similar process) to disclose any of the Evaluation Material, you shall provide 
the Company with written notice of such requirement as soon as practicable after 
learning of it, shall furnish only that portion of the Evaluation Material which 
you are advised by written opinion of counsel is legally required and only in the 
manner legally required, and shall exercise best efforts to obtain assurance that 
confidential treatment will be accorded such Evaluation Material. In addition, you 
acknowledge that the Company may also take steps as it deems necessary to obtain 
such assurance. Notwithstanding the foregoing, Confidential Information may be 
disclosed, and no notice as referenced above is required to be provided, pursuant 
to requests for information in connection with routine supervisory examinations by 
regulatory authorities with the jurisdiction over you or your Representatives and 
not directed at the disclosing party or the Potential Transaction; provided that 
you or your Representatives, as applicable, inform any such authority of the 
confidential nature of the information disclosed to them and to keep such 
information confidential in accordance with such authority's policies and procedures.
```

---

#### TC4-02: 真实合同修改后 - 条款被完全删除

**来源：** Sample NDA（修改后）

**条件判断：** 强制披露条款不存在

**输入：**
```
You shall be responsible for any breach of this agreement that are applicable to 
Representatives by your Representatives, except for any Representative that (i) 
enters into a separate agreement in a form similar to this agreement in substance 
for the benefit of the Company or (ii) executes a separate confidentiality agreement 
with the Company relating to the possible transaction.
```

**预期动作：** 规则不触发（无强制披露条款）

**预期输出：**
```
You shall be responsible for any breach of this agreement that are applicable to 
Representatives by your Representatives, except for any Representative that (i) 
enters into a separate agreement in a form similar to this agreement in substance 
for the benefit of the Company or (ii) executes a separate confidentiality agreement 
with the Company relating to the possible transaction.
```

> 输入输出相同，因为规则不触发

---

#### TC4-03: 仅覆盖接收方，无 Representatives

**条件判断：**
| 条件 | 结果 |
|------|------|
| cond_1 | ❌ false |
| cond_2 | ✅ true |
| cond_3 | ✅ true |

**输入：**
```
If you are required (by deposition, interrogatory, request for documents, subpoena, 
civil investigative demand or similar process) to disclose any of the Evaluation 
Material, you shall provide the Company with written notice of such requirement 
as soon as practicable after learning of it.
```

**预期动作：** 补充覆盖 Representatives + 添加监管审查例外条款

**预期输出：**
```
If you or any of your Representatives are required (by deposition, interrogatory, 
request for documents, subpoena, civil investigative demand or similar process) 
to disclose any of the Evaluation Material, you shall provide the Company with 
written notice of such requirement as soon as practicable after learning of it. 
Notwithstanding the foregoing, Confidential Information may be disclosed, and no 
notice as referenced above is required to be provided, pursuant to requests for 
information in connection with routine supervisory examinations by regulatory 
authorities with the jurisdiction over you or your Representatives and not directed 
at the disclosing party or the Potential Transaction; provided that you or your 
Representatives, as applicable, inform any such authority of the confidential nature 
of the information disclosed to them and to keep such information confidential in 
accordance with such authority's policies and procedures.
```

---

#### TC4-04: 简化法律情形 - 仅 'required by law'

**条件判断：**
| 条件 | 结果 |
|------|------|
| cond_1 | ✅ true |
| cond_2 | ❌ false |
| cond_3 | ✅ true |

**输入：**
```
If you or any of your Representatives is required by law to disclose any of the 
Evaluation Material, you shall provide the Company with written notice of such 
requirement as soon as practicable.
```

**预期动作：** 补充完整法律情形 + 添加监管审查例外条款

**预期输出：**
```
If you or any of your Representatives is requested or required by law, regulation, 
order and legal process to disclose any of the Evaluation Material, you shall 
provide the Company with written notice of such requirement as soon as practicable. 
Notwithstanding the foregoing, Confidential Information may be disclosed, and no 
notice as referenced above is required to be provided, pursuant to requests for 
information in connection with routine supervisory examinations by regulatory 
authorities with the jurisdiction over you or your Representatives and not directed 
at the disclosing party or the Potential Transaction; provided that you or your 
Representatives, as applicable, inform any such authority of the confidential nature 
of the information disclosed to them and to keep such information confidential in 
accordance with such authority's policies and procedures.
```

---

#### TC4-05: 无通知要求 - 不添加监管例外

**条件判断：**
| 条件 | 结果 |
|------|------|
| cond_1 | ✅ true |
| cond_2 | ✅ true |
| cond_3 | ❌ false |

**输入：**
```
If you or any of your Representatives is required (by deposition, interrogatory, 
request for documents, subpoena, civil investigative demand or similar process) 
to disclose any of the Evaluation Material, such disclosure shall not constitute 
a breach of this agreement.
```

**预期动作：** 不添加监管审查例外条款（无通知要求）

**预期输出：**
```
If you or any of your Representatives is required (by deposition, interrogatory, 
request for documents, subpoena, civil investigative demand or similar process) 
to disclose any of the Evaluation Material, such disclosure shall not constitute 
a breach of this agreement.
```

> **关键测试：** 验证当 cond_3=false 时，系统不应添加监管审查例外条款。输入输出相同。

---

#### TC4-06: 使用 Recipient 术语

**条件判断：**
| 条件 | 结果 |
|------|------|
| cond_1 | ✅ true |
| cond_2 | ✅ true |
| cond_3 | ✅ true |

**输入：**
```
If the Recipient or its Representatives is requested or required by law, regulation, 
order and legal process to disclose any Confidential Information, the Recipient shall 
provide prior written notice to the Disclosing Party promptly upon becoming aware of 
such requirement.
```

**预期动作：** 添加监管审查例外条款

**预期输出：**
```
If the Recipient or its Representatives is requested or required by law, regulation, 
order and legal process to disclose any Confidential Information, the Recipient shall 
provide prior written notice to the Disclosing Party promptly upon becoming aware of 
such requirement. Notwithstanding the foregoing, Confidential Information may be 
disclosed, and no notice as referenced above is required to be provided, pursuant to 
requests for information in connection with routine supervisory examinations by 
regulatory authorities with the jurisdiction over you or your Representatives and 
not directed at the disclosing party or the Potential Transaction; provided that 
you or your Representatives, as applicable, inform any such authority of the 
confidential nature of the information disclosed to them and to keep such 
information confidential in accordance with such authority's policies and procedures.
```

---

#### TC4-07: 全部缺失 - 最简条款

**条件判断：**
| 条件 | 结果 |
|------|------|
| cond_1 | ❌ false |
| cond_2 | ❌ false |
| cond_3 | ❌ false |

**输入：**
```
The Recipient may disclose Confidential Information if required by law.
```

**预期动作：** 
1. 补充覆盖 Representatives
2. 补充完整法律情形
3. 不添加监管审查例外条款（无通知要求）

**预期输出：**
```
The Recipient or its Representatives may disclose Confidential Information if 
requested or required by law, regulation, order and legal process.
```

> 注意：因为 cond_3=false（无通知要求），所以不添加监管审查例外条款

---

## 规则5: Third Party Source Exception

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 条件判断 (conditional) |
| 触发条件 | 当文档中存在第三方来源信息的例外条款时 |
| 执行动作 | 确保第三方来源例外条款满足三个必要条件 |
| 优先级 | P1 |

### 必要条件

如果现有条款包含"第三方未违反保密义务"的限制语，则必须满足以下三个条件：

| 条件ID | 检查内容 | 必需元素 |
|--------|----------|----------|
| sub_cond_1 | 接收方知情限制 | "was not known by you or your Representatives" |
| sub_cond_2 | 保密义务对象 | "obligations owed to the Company" |
| sub_cond_3 | 信息相关性 | "with respect to such information" |

### 标准条款格式

```
becomes available to you or your Representatives from a source other than the 
Company; [provided that the source of such information was not known by you or 
your Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information]
```

### 测试样例

#### TC5-01: 标准完整条款 - 满足所有条件

**输入：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information.
```

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| sub_cond_1 | ✅ true | 包含 "was not known by you or your Representatives" |
| sub_cond_2 | ✅ true | 包含 "obligations owed to the Company" |
| sub_cond_3 | ✅ true | 包含 "with respect to such information" |

**预期动作：** 已完整，无需修改

**预期输出：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information.
```

---

#### TC5-02: 简化条款 - 无第三方限制语

**输入：**
```
(d) information received from a third party.
```

**条件判断：** 无第三方限制语，不触发条件检查

**预期动作：** 不主动添加限制语（如果现有NDA没有提供此类限制，则不要插入）

**预期输出：**
```
(d) becomes available to you or your Representatives from a source other than the Company.
```

> **备注：** 确保措辞改为标准格式 "from a source other than the Company"，但不添加限制语

---

#### TC5-03: 缺少知情限制 - sub_cond_1 不满足

**输入：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information did not breach any 
confidentiality obligations owed to the Company with respect to such information.
```

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| sub_cond_1 | ❌ false | 缺少 "was not known by you or your Representatives" |
| sub_cond_2 | ✅ true | 包含 "obligations owed to the Company" |
| sub_cond_3 | ✅ true | 包含 "with respect to such information" |

**预期动作：** 补充知情限制条件

**预期输出：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information.
```

---

#### TC5-04: 缺少公司对象 - sub_cond_2 不满足

**输入：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations.
```

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| sub_cond_1 | ✅ true | 包含知情限制 |
| sub_cond_2 | ❌ false | 缺少 "owed to the Company" |
| sub_cond_3 | ❌ false | 缺少 "with respect to such information" |

**预期动作：** 补充 "owed to the Company with respect to such information"

**预期输出：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information.
```

---

#### TC5-05: 缺少信息相关性 - sub_cond_3 不满足

**输入：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company.
```

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| sub_cond_1 | ✅ true | 包含知情限制 |
| sub_cond_2 | ✅ true | 包含 "owed to the Company" |
| sub_cond_3 | ❌ false | 缺少 "with respect to such information" |

**预期动作：** 补充 "with respect to such information"

**预期输出：**
```
(d) becomes available to you or your Representatives from a source other than the 
Company; provided that the source of such information was not known by you or your 
Representatives to have made the disclosure in violation of any confidentiality 
obligations owed to the Company with respect to such information.
```

---

#### TC5-06: 真实合同样本 - 使用 Disclosing Party 术语

**来源：** Sample NDA

**输入：**
```
(c) is received by the Receiving Party from a third party without breach of 
any obligation of confidentiality.
```

**条件判断：**
| 条件 | 结果 | 原因 |
|------|------|------|
| sub_cond_1 | ❌ false | 缺少知情限制 |
| sub_cond_2 | ❌ false | 未指明义务对象 |
| sub_cond_3 | ❌ false | 缺少信息相关性 |

**预期动作：** 重写为标准格式，补充所有三个条件

**预期输出：**
```
(c) becomes available to the Receiving Party or its Representatives from a source 
other than the Disclosing Party; provided that the source of such information was 
not known by the Receiving Party or its Representatives to have made the disclosure 
in violation of any confidentiality obligations owed to the Disclosing Party with 
respect to such information.
```

---

## 规则6: Independent Development Exception

### 规则说明

| 属性 | 内容 |
|------|------|
| 规则类型 | 简化 (simplify) |
| 触发条件 | 当文档中存在独立开发信息的例外条款时 |
| 执行动作 | 简化限制语，只保留必要的限制词 |
| 优先级 | P1 |

### 简化规则

| 类型 | 内容 |
|------|------|
| 保留词 | "without use of", "without reference to" |
| 删除词 | "based upon", "reliance on", "derived from" |
| 原则 | 限制越少越好 |

### 标准条款格式

```
was or is independently developed by or for you or your Representatives without 
use of Confidential Information
```

### 测试样例

#### TC6-01: 标准完整条款 - 已符合要求

**输入：**
```
(e) was or is independently developed by or for you or your Representatives 
without use of Confidential Information.
```

**预期动作：** 已符合要求，无需修改

**预期输出：**
```
(e) was or is independently developed by or for you or your Representatives 
without use of Confidential Information.
```

---

#### TC6-02: 包含多余限制词 - 需要简化

**输入：**
```
(e) information independently developed without use of, reference to, or based 
upon Confidential Information.
```

**分析：**
- "without use of" - ✅ 保留
- "reference to" - ✅ 保留（可选）
- "based upon" - ❌ 删除

**预期动作：** 删除 "based upon"，重写为标准格式

**预期输出：**
```
(e) was or is independently developed by or for you or your Representatives 
without use of Confidential Information.
```

> **备注：** 按照"限制越少越好"原则，只保留 "without use of"

---

#### TC6-03: 包含更多限制词 - 大幅简化

**输入：**
```
(e) was independently developed by you without use of, reference to, reliance on, 
or derived from any Confidential Information.
```

**分析：**
- "without use of" - ✅ 保留
- "reference to" - ✅ 可保留
- "reliance on" - ❌ 删除
- "derived from" - ❌ 删除

**预期动作：** 删除多余限制词，补充 "your Representatives"

**预期输出：**
```
(e) was or is independently developed by or for you or your Representatives 
without use of Confidential Information.
```

---

#### TC6-04: 仅覆盖接收方 - 需补充 Representatives

**输入：**
```
(e) was independently developed by the Recipient without use of Confidential 
Information.
```

**分析：** 缺少 "or its Representatives"

**预期动作：** 补充 "or its Representatives"

**预期输出：**
```
(e) was or is independently developed by or for the Recipient or its Representatives 
without use of Confidential Information.
```

---

#### TC6-05: 使用 "without reference to" 作为唯一限制

**输入：**
```
(e) was independently developed by you or your Representatives without reference 
to Confidential Information.
```

**分析：** "without reference to" 是可接受的限制词

**预期动作：** 可接受，但建议使用更标准的 "without use of"

**预期输出（建议）：**
```
(e) was or is independently developed by or for you or your Representatives 
without use of Confidential Information.
```

**预期输出（可接受）：**
```
(e) was or is independently developed by or for you or your Representatives 
without reference to Confidential Information.
```

---

#### TC6-06: 真实合同样本 - 复杂条款

**来源：** Sample NDA

**输入：**
```
(d) is developed by the Receiving Party independently and without use of or 
reference to, or reliance upon, any Confidential Information disclosed by the 
Disclosing Party.
```

**分析：**
- "without use of" - ✅ 保留
- "reference to" - ✅ 可保留
- "reliance upon" - ❌ 删除

**预期动作：** 简化为标准格式

**预期输出：**
```
(d) was or is independently developed by or for the Receiving Party or its 
Representatives without use of Confidential Information.
```

---

## 测试覆盖统计

### 按规则统计

| 规则 | 测试用例数 | 覆盖场景 |
|------|-----------|----------|
| Rule 1 | 5 | 单个、多个、已有、无触发、真实合同 |
| Rule 2 | 5 | 标准、Receiving Party、Evaluation Material、已有、无结构 |
| Rule 3 | 5 | 最简、部分缺失、完整、额外元素、无定义 |
| Rule 4 | 7 | 8种条件组合 |
| Rule 5 | 6 | 完整条款、无限制语、缺少知情、缺少对象、缺少相关性、真实合同 |
| Rule 6 | 6 | 标准条款、多余限制词、大幅简化、缺少代表、替代限制词、真实合同 |
| **总计** | **34** | - |

### 规则4条件覆盖矩阵

| 测试ID | cond_1 | cond_2 | cond_3 | 预期动作 |
|--------|--------|--------|--------|----------|
| TC4-01 | ✅ | ✅ | ✅ | 添加监管例外 |
| TC4-02 | - | - | - | 规则不触发 |
| TC4-03 | ❌ | ✅ | ✅ | 补充 + 添加例外 |
| TC4-04 | ✅ | ❌ | ✅ | 补充 + 添加例外 |
| TC4-05 | ✅ | ✅ | ❌ | 不添加例外 |
| TC4-06 | ✅ | ✅ | ✅ | 添加例外 |
| TC4-07 | ❌ | ❌ | ❌ | 补充两项，不加例外 |

### 规则5条件覆盖矩阵

| 测试ID | sub_cond_1 | sub_cond_2 | sub_cond_3 | 预期动作 |
|--------|------------|------------|------------|----------|
| TC5-01 | ✅ | ✅ | ✅ | 无需修改 |
| TC5-02 | - | - | - | 无限制语，仅改措辞 |
| TC5-03 | ❌ | ✅ | ✅ | 补充知情限制 |
| TC5-04 | ✅ | ❌ | ❌ | 补充对象和相关性 |
| TC5-05 | ✅ | ✅ | ❌ | 补充信息相关性 |
| TC5-06 | ❌ | ❌ | ❌ | 重写为标准格式 |

### 规则6简化场景覆盖

| 测试ID | 输入限制词 | 预期处理 |
|--------|-----------|----------|
| TC6-01 | without use of | 无需修改 |
| TC6-02 | without use of, reference to, based upon | 删除 based upon |
| TC6-03 | without use of, reference to, reliance on, derived from | 删除多余词 |
| TC6-04 | without use of（仅接收方） | 补充 Representatives |
| TC6-05 | without reference to | 可接受，建议改为 without use of |
| TC6-06 | without use of, reference to, reliance upon | 简化为标准格式 |

### 边界情况覆盖

| 类型 | 覆盖的测试用例 |
|------|---------------|
| 已存在目标内容 | TC1-04, TC2-04, TC5-01, TC6-01 |
| 规则不触发 | TC1-05, TC2-05, TC3-05, TC4-02 |
| 真实合同样本 | TC1-02, TC2-01, TC2-03, TC3-02, TC3-03, TC4-01, TC4-02, TC5-06, TC6-06 |
| 多实例处理 | TC1-03 |
| 额外内容保留 | TC3-04 |
| 条款简化处理 | TC6-02, TC6-03, TC6-05, TC6-06 |
| 补充 Representatives | TC5-06, TC6-04 |

---

## 附录：数据来源

本测试文档中的真实合同样例来源于：
- `/Users/zrr/Downloads/法律助手测试数据/` 目录下的 Sample NDA 文档
- `/nda_demo/learned_rules/learned_rules.json` 中记录的实际修改案例
