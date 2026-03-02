# AI 法律助手 - MVP Demo (Minimalist Redlining)

## 项目简介

本 Demo 旨在展示 AI 法律助手的核心价值：**“Strict Playbook”下的“Minimalist Redlining”（最小化红线修订）**。

为了消除用户（尤其是严谨的律师）对 AI“过度修改”或“产生幻觉”的顾虑，本 Demo 采用了透明化的**“控制层 -> 执行层”**设计：
1.  **控制层 (Control Layer)**：左侧面板。用户明确指定规则（如：管辖地必须是香港）。
2.  **执行层 (Redlining)**：右侧面板。AI 严格遵循规则，仅对违规部分进行红线修订，绝不随意润色或重写。

## 目录结构

```text
nda_demo/
├── demo_app.py          # 核心演示程序 (Streamlit)
├── requirements.txt     # 依赖库列表
├── sample_contract.txt  # 示例文本 (备用)
└── README.md            # 本说明文档
```

## 快速开始

### 1. 安装依赖

确保已安装 Python 3.8+，然后在终端运行：

```bash
pip install -r requirements.txt
```

### 2. 运行 Demo

```bash
streamlit run demo_app.py
```

## 演示剧本 (Script)

**场景**：向对 AI 准确性存疑的客户（如法务总监）演示。

### 第一阶段：建立信任 (The Setup)
*   **话术**：“李律师，我知道您最担心 AI 自作聪明，把原本严谨的条款改得面目全非。”
*   **操作**：
    *   启动 Demo。
    *   指着左侧 **[Control Layer]** 面板。
    *   **话术**：“所以我们的 MVP 版本不追求‘创意’，而是追求‘服从’。请看左边，这里是您的 Playbook（审查标准）。只有在这里勾选了规则，AI 才会执行。”

### 第二阶段：展示控制力 (The Control)
*   **操作**：
    *   在左侧面板将 **[Required Jurisdiction]** 选为 **"Hong Kong"**。
    *   将 **[Confidentiality Term]** 选为 **"5 Years"**。
    *   **话术**：“比如这个合同，原本写的是纽约管辖，保密期 1 年。现在我们设定规则：管辖地必须是香港，保密期必须是 5 年。”

### 第三阶段：见证最小化修订 (The Result)
*   **操作**：
    *   点击 **[🚀 Run Compliance Check]** 按钮。
    *   等待几秒，指着右侧生成的红线结果。
*   **话术**：“请看右边。AI 没有重写整段话，它只是精确地把 'New York' 划掉，改成了 'Hong Kong'；把 '1 year' 改成了 '5 Years'。”
*   **重点强调**：“这就是我们承诺的 **Minimalist Redlining**。它像一个最听话的初级律师，严格只改您让它改的地方，绝不多动一个标点符号。”

### 第四阶段：查看思考过程 (The Logic)
*   **操作**：
    *   指着红线下方的小字（AI Reasoning）。
    *   **话术**：“而且，每一处修改它都会告诉您原因：‘检测到纽约管辖，根据您的 Playbook 规则 3，已修正为香港’。全程透明，可追溯。”

