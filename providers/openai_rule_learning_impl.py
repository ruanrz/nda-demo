# -*- coding: utf-8 -*-
"""
规则学习 Provider（OpenAI）

提供三个核心函数（分离预处理与运行时）：

【预处理阶段 - 单独调用一次】
1. parse_playbook_to_rules: 将文本 playbook 解析为结构化 JSON 规则（预处理）
   - 支持保存到文件，供后续重复使用
   - 只需在 playbook 变更时调用

【运行时阶段 - 每次审查合同时调用】
2. search_playbook_matches: 使用已解析的规则，在文本中搜索匹配内容
3. apply_playbook_modifications: 根据已解析的规则修改文本

所有函数都调用 OpenAI API。
"""

import os
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, asdict
from openai import OpenAI

# =============================================================================
# 日志配置
# =============================================================================
# 创建 logger
logger = logging.getLogger("rule_learning_provider")
logger.setLevel(logging.DEBUG)

# 如果没有处理器，添加默认处理器
if not logger.handlers:
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(console_handler)
    
    # 尝试添加文件处理器
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"rule_learning_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
            "%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(file_handler)
        logger.debug(f"日志文件: {log_file}")
    except Exception as e:
        logger.warning(f"无法创建日志文件: {e}")



# 导入 prompt 模板
from prompts import (
    format_parse_playbook_prompt,
    format_search_matches_prompt,
    format_apply_modifications_prompt,
    # checklist 类型规则的 prompt
    format_search_checklist_matches_prompt,
    format_apply_checklist_modifications_prompt,
    format_parse_playbook_enhanced_prompt,
    # conditional 类型规则的 prompt
    format_search_conditional_matches_prompt,
    format_apply_conditional_modifications_prompt,
    # 学习相关的 prompt
    format_extract_rules_from_diff_prompt,
    format_search_learned_rules_matches_prompt,
    format_apply_learned_rules_prompt,
)


# =============================================================================
# 配置
# =============================================================================
# OpenAI API 配置
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# 默认规则存储目录
DEFAULT_RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "parsed_rules")

# 学习规则存储目录
LEARNED_RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "learned_rules")
LEARNED_RULES_FILE = os.path.join(LEARNED_RULES_DIR, "learned_rules.json")


# =============================================================================
# 输出 Schema 定义（使用 dataclass 便于类型检查和序列化）
# =============================================================================

@dataclass
class PlaybookRule:
    """
    单条 Playbook 规则的结构
    
    Attributes:
        id: 规则唯一标识符
        title: 规则标题/名称
        trigger: 触发条件描述
        action: 修改动作描述
        constraints: 注意事项列表
        example: 修改前后示例
        priority: 规则优先级 (P0/P1/P2)
    """
    id: str
    title: str
    trigger: str
    action: str
    constraints: List[str]
    example: Optional[Dict[str, str]]
    priority: str


@dataclass
class ParsedPlaybook:
    """
    已解析的 Playbook 结构（用于预处理结果的存储和加载）
    
    Schema:
    {
        "playbook_id": "唯一标识符",
        "playbook_name": "Playbook 名称",
        "rules": [...],
        "metadata": {...},
        "parsed_at": "解析时间",
        "source_hash": "原始文本的哈希值（用于检测变更）"
    }
    """
    playbook_id: str
    playbook_name: str
    rules: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    parsed_at: str
    source_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedPlaybook":
        """从字典创建实例"""
        return cls(
            playbook_id=data.get("playbook_id", ""),
            playbook_name=data.get("playbook_name", ""),
            rules=data.get("rules", []),
            metadata=data.get("metadata", {}),
            parsed_at=data.get("parsed_at", ""),
            source_hash=data.get("source_hash", "")
        )


@dataclass
class SearchMatchesResult:
    """
    search_playbook_matches 函数的输出结构
    
    Schema:
    {
        "matches": [
            {
                "rule_id": "rule_1",
                "rule_title": "规则标题",
                "matched_text": "匹配到的文本",
                "match_type": "exact",
                "similarity_score": 0.95,
                "location": {
                    "paragraph_index": 1,
                    "context": "上下文文本"
                },
                "needs_modification": true,
                "modification_reason": "修改原因"
            }
        ],
        "summary": {
            "total_rules": 5,
            "matched_rules": 3,
            "rules_needing_modification": 2
        }
    }
    """
    matches: List[Dict[str, Any]]
    summary: Dict[str, Any]
    raw_response: str


@dataclass
class ApplyModificationsResult:
    """
    apply_playbook_modifications 函数的输出结构
    
    Schema:
    {
        "modifications": [
            {
                "rule_id": "rule_1",
                "original_text": "原始文本",
                "modified_text": "修改后文本",
                "modification_type": "insert",
                "explanation": "修改说明"
            }
        ],
        "final_text": "完整的修改后文本",
        "summary": {
            "total_modifications": 2,
            "rules_applied": ["rule_1", "rule_2"],
            "unchanged_reason": null
        }
    }
    """
    modifications: List[Dict[str, Any]]
    final_text: str
    summary: Dict[str, Any]
    raw_response: str


# =============================================================================
# 辅助函数
# =============================================================================

def get_openai_client() -> Optional[OpenAI]:
    """
    获取 OpenAI API 客户端
    
    使用 OpenAI SDK 调用。
    需要设置环境变量：
        - OPENAI_API_KEY: API 密钥
        - OPENAI_API_BASE: API 基础 URL（可选）
        - OPENAI_MODEL: 模型名称（可选）
    
    Returns:
        OpenAI: 配置好的客户端实例，或 None（如果配置缺失）
    """
    logger.debug(f"初始化 OpenAI 客户端: base_url={OPENAI_API_BASE}, model={OPENAI_MODEL}")
    api_key = OPENAI_API_KEY
    if not api_key:
        logger.error("未配置 OpenAI API Key")
        raise ValueError(
            "未配置 OpenAI API Key，请设置环境变量 OPENAI_API_KEY"
        )
    
    logger.debug(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    kwargs = {"api_key": api_key}
    if OPENAI_API_BASE:
        kwargs["base_url"] = OPENAI_API_BASE
    return OpenAI(**kwargs)


def call_openai_api(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    json_mode: bool = True
) -> str:
    """
    调用 OpenAI API
    
    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 温度参数，控制随机性（0-1）
        max_tokens: 最大输出 token 数
        json_mode: 是否启用 JSON 输出模式
        
    Returns:
        str: API 响应内容
        
    Raises:
        Exception: API 调用失败时抛出异常
    """
    logger.info("=" * 40)
    logger.info("调用 OpenAI API")
    logger.debug(f"参数: temperature={temperature}, max_tokens={max_tokens}, json_mode={json_mode}")
    logger.debug(f"System Prompt 长度: {len(system_prompt)} 字符")
    logger.debug(f"User Prompt 长度: {len(user_prompt)} 字符")
    logger.debug(f"System Prompt 前200字符: {system_prompt[:200]}...")
    logger.debug(f"User Prompt 前200字符: {user_prompt[:200]}...")
    
    start_time = datetime.now()
    
    client = get_openai_client()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    kwargs = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    
    # OpenAI JSON 模式
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    def _extract_error_param(error_text: str) -> Optional[str]:
        patterns = [
            r"param['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
            r"Unsupported parameter:\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in patterns:
            m = re.search(pattern, error_text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _create_with_compat(initial_kwargs: Dict[str, Any]):
        current_kwargs = dict(initial_kwargs)
        for attempt in range(4):
            try:
                return client.chat.completions.create(**current_kwargs)
            except Exception as e:
                if attempt == 3:
                    raise

                error_text = str(e)
                error_lower = error_text.lower()
                bad_param = _extract_error_param(error_text)
                changed = False

                if bad_param == "temperature" or (
                    "temperature" in error_lower and "unsupported" in error_lower
                ):
                    if "temperature" in current_kwargs:
                        current_kwargs.pop("temperature", None)
                        changed = True

                elif bad_param == "max_tokens" or (
                    "max_tokens" in error_lower and "unsupported" in error_lower
                ):
                    if "max_tokens" in current_kwargs:
                        current_kwargs.pop("max_tokens", None)
                        current_kwargs["max_completion_tokens"] = max_tokens
                        changed = True

                elif bad_param == "max_completion_tokens" or (
                    "max_completion_tokens" in error_lower and "unsupported" in error_lower
                ):
                    if "max_completion_tokens" in current_kwargs:
                        current_kwargs.pop("max_completion_tokens", None)
                        current_kwargs["max_tokens"] = max_tokens
                        changed = True

                elif bad_param == "response_format" and "response_format" in current_kwargs:
                    current_kwargs.pop("response_format", None)
                    changed = True

                if not changed:
                    raise

                logger.warning(f"参数不兼容，自动重试（移除/切换参数: {bad_param or 'unknown'}）")

        raise RuntimeError("Unexpected retry loop exit in call_openai_api")

    try:
        logger.info("发送请求到 OpenAI API...")
        response = _create_with_compat(kwargs)
        
        duration = (datetime.now() - start_time).total_seconds()
        content = response.choices[0].message.content
        
        logger.info(f"✅ API 响应成功，耗时 {duration:.2f}s")
        logger.info(f"响应长度: {len(content)} 字符")
        
        # 记录 token 使用情况（如果有）
        if hasattr(response, 'usage') and response.usage:
            logger.info(f"Token 使用: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
        
        # 打印完整的大模型回答
        logger.info("-" * 40)
        logger.info("【大模型回答开始】")
        # 按行打印，方便查看
        for line in content.split('\n'):
            logger.info(f"  {line}")
        logger.info("【大模型回答结束】")
        logger.info("-" * 40)
        
        # 同时在控制台打印（使用 print 确保可见）
        print("\n" + "=" * 60)
        print("【OpenAI 大模型回答】")
        print("=" * 60)
        print(content)
        print("=" * 60 + "\n")
        
        logger.info("=" * 40)
        return content
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ API 调用失败，耗时 {duration:.2f}s")
        logger.exception(f"错误详情: {e}")
        raise


# Backward-compatible aliases (legacy imports may still reference these names).
get_doubao_client = get_openai_client
call_doubao_api = call_openai_api


def safe_json_parse(content: str) -> Dict[str, Any]:
    """
    安全地解析 JSON 响应
    
    Args:
        content: JSON 字符串
        
    Returns:
        dict: 解析后的字典，解析失败返回空字典
    """
    logger.debug(f"解析 JSON 响应，长度: {len(content)} 字符")
    try:
        # 尝试直接解析
        result = json.loads(content)
        logger.debug(f"✅ JSON 解析成功，键: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 直接解析失败: {e}")
        # 尝试提取 JSON 块（处理 markdown 代码块包裹的情况）
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                logger.debug("✅ 从代码块中提取 JSON 成功")
                return result
            except json.JSONDecodeError as e2:
                logger.warning(f"从代码块提取 JSON 也失败: {e2}")
        logger.error("❌ JSON 解析完全失败，返回空字典")
        logger.debug(f"原始内容: {content[:200]}...")
        return {}


def compute_text_hash(text: str) -> str:
    """
    计算文本的哈希值，用于检测 playbook 是否变更
    
    Args:
        text: 输入文本
        
    Returns:
        str: 文本的 MD5 哈希值
    """
    import hashlib
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def generate_playbook_id(name: str) -> str:
    """
    根据名称生成 playbook ID
    
    Args:
        name: Playbook 名称
        
    Returns:
        str: 生成的 ID
    """
    import re
    # 移除特殊字符，转换为小写，用下划线连接
    clean_name = re.sub(r'[^\w\s]', '', name).strip().lower()
    clean_name = re.sub(r'\s+', '_', clean_name)
    return clean_name or f"playbook_{datetime.now().strftime('%Y%m%d%H%M%S')}"


# =============================================================================
# 预处理函数：parse_playbook_to_rules（独立步骤）
# =============================================================================

def parse_playbook_to_rules(
    playbook_text: str,
    playbook_name: str = "default",
    save_path: Optional[str] = None,
    auto_save: bool = True
) -> ParsedPlaybook:
    """
    【预处理步骤】将文本形式的 Playbook 解析为结构化的 JSON 规则
    
    这是一个独立的预处理步骤，只需在以下情况调用：
    - 首次导入新的 Playbook 时
    - Playbook 内容发生变更时
    
    解析结果会被保存到文件，后续可直接加载使用，无需重复解析。
    
    【业务逻辑】
    1. 接收用户提供的自然语言 Playbook 文本
    2. 调用大模型理解文本语义
    3. 提取触发条件、修改动作、注意事项等关键信息
    4. 输出标准化的 JSON 规则结构
    5. 可选：自动保存到文件供后续使用
    
    【输出 Schema】
    {
        "playbook_id": "my_nda_rules",
        "playbook_name": "我的NDA规则",
        "rules": [
            {
                "id": "rule_1",                    // 规则唯一标识符
                "title": "商业秘密限定",            // 规则标题
                "trigger": "当文本中出现'商业秘密'时",  // 触发条件
                "action": "添加'（依据适用法律定义）'", // 修改动作
                "constraints": [                   // 注意事项
                    "不改变原有定义",
                    "保持措辞一致性"
                ],
                "example": {                       // 示例（可选）
                    "before": "商业秘密",
                    "after": "商业秘密（依据适用法律定义）"
                },
                "priority": "P0"                   // 优先级
            }
        ],
        "metadata": {
            "document_type": "NDA",                // 适用文档类型
            "total_rules": 5                       // 规则总数
        },
        "parsed_at": "2026-01-05T12:00:00",       // 解析时间
        "source_hash": "abc123..."                 // 原文哈希（用于检测变更）
    }
    
    Args:
        playbook_text: 自然语言形式的 Playbook 文本
        playbook_name: Playbook 名称（用于标识和生成文件名）
        save_path: 保存路径（可选，默认自动生成）
        auto_save: 是否自动保存解析结果（默认 True）
        
    Returns:
        ParsedPlaybook: 包含解析后规则的结果对象
        
    Raises:
        ValueError: 输入文本为空时
        Exception: API 调用失败时
        
    Example:
        >>> # 预处理步骤：只需执行一次
        >>> playbook_text = '''
        ... 规则1：如果看到"商业秘密"，需要添加"（依据适用法律定义）"
        ... 规则2：保密信息定义需要限定为"与本交易相关且在签署日期当日或之后"
        ... '''
        >>> parsed = parse_playbook_to_rules(
        ...     playbook_text, 
        ...     playbook_name="我的NDA规则",
        ...     auto_save=True
        ... )
        >>> print(f"已保存 {len(parsed.rules)} 条规则")
        
        >>> # 后续使用：直接加载已解析的规则
        >>> rules = load_parsed_playbook("我的NDA规则")
    """
    logger.info("=" * 60)
    logger.info("【parse_playbook_to_rules】开始解析 Playbook")
    logger.info(f"Playbook 名称: {playbook_name}")
    logger.info(f"文本长度: {len(playbook_text)} 字符")
    logger.info(f"自动保存: {auto_save}")
    
    if not playbook_text or not playbook_text.strip():
        logger.error("Playbook 文本为空")
        raise ValueError("Playbook 文本不能为空")
    
    # 打印原始 Playbook 文本
    print("\n" + "-" * 40)
    print("【输入的 Playbook 文本】")
    print("-" * 40)
    print(playbook_text)
    print("-" * 40 + "\n")
    
    # 1. 计算原文哈希（用于后续检测变更）
    source_hash = compute_text_hash(playbook_text)
    logger.debug(f"文本哈希: {source_hash}")
    
    # 2. 生成 playbook ID
    playbook_id = generate_playbook_id(playbook_name)
    logger.debug(f"生成 Playbook ID: {playbook_id}")
    
    # 3. 获取格式化的 prompt
    system_prompt, user_prompt = format_parse_playbook_prompt(playbook_text)
    logger.info("已生成 Prompt")
    logger.debug(f"System Prompt: {system_prompt[:200]}...")
    
    # 4. 调用大模型 API
    logger.info("调用大模型解析 Playbook...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,  # 低温度确保输出稳定
        max_tokens=2000,
        json_mode=True
    )
    
    # 5. 解析 JSON 响应
    logger.info("解析 API 响应...")
    parsed = safe_json_parse(raw_response)
    
    # 6. 验证和提取数据
    rules = parsed.get("rules", [])
    metadata = parsed.get("metadata", {
        "document_type": "未知",
        "total_rules": len(rules)
    })
    
    logger.info(f"解析结果: 共 {len(rules)} 条规则")
    for i, rule in enumerate(rules, 1):
        logger.info(f"  规则 {i}: {rule.get('title', '未命名')} - {rule.get('trigger', '无触发条件')}")
    
    # 确保 metadata 包含 total_rules
    if "total_rules" not in metadata:
        metadata["total_rules"] = len(rules)
    
    # 7. 创建结果对象
    result = ParsedPlaybook(
        playbook_id=playbook_id,
        playbook_name=playbook_name,
        rules=rules,
        metadata=metadata,
        parsed_at=datetime.now().isoformat(),
        source_hash=source_hash
    )
    
    logger.info(f"✅ Playbook 解析完成")
    logger.info("=" * 60)
    
    # 8. 自动保存（如果启用）
    if auto_save:
        save_parsed_playbook(result, save_path)
    
    return result


def save_parsed_playbook(
    parsed_playbook: ParsedPlaybook,
    save_path: Optional[str] = None
) -> str:
    """
    保存已解析的 Playbook 到文件
    
    Args:
        parsed_playbook: 已解析的 Playbook 对象
        save_path: 保存路径（可选，默认自动生成）
        
    Returns:
        str: 保存的文件路径
    """
    # 确定保存路径
    if save_path is None:
        rules_dir = Path(DEFAULT_RULES_DIR)
        rules_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(rules_dir / f"{parsed_playbook.playbook_id}.json")
    
    # 保存到文件
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_playbook.to_dict(), f, ensure_ascii=False, indent=2)
    
    return save_path


def load_parsed_playbook(
    playbook_id_or_path: str
) -> ParsedPlaybook:
    """
    加载已解析的 Playbook
    
    Args:
        playbook_id_or_path: Playbook ID 或文件路径
        
    Returns:
        ParsedPlaybook: 加载的 Playbook 对象
        
    Raises:
        FileNotFoundError: 文件不存在时
    """
    # 判断是路径还是 ID
    if os.path.isfile(playbook_id_or_path):
        file_path = playbook_id_or_path
    else:
        # 尝试在默认目录查找
        file_path = os.path.join(DEFAULT_RULES_DIR, f"{playbook_id_or_path}.json")
    
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"未找到 Playbook 文件: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return ParsedPlaybook.from_dict(data)


def list_parsed_playbooks() -> List[Dict[str, str]]:
    """
    列出所有已解析的 Playbook
    
    Returns:
        List[Dict]: 包含 playbook_id, playbook_name, parsed_at 的列表
    """
    rules_dir = Path(DEFAULT_RULES_DIR)
    if not rules_dir.exists():
        return []
    
    result = []
    for file_path in rules_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result.append({
                "playbook_id": data.get("playbook_id", file_path.stem),
                "playbook_name": data.get("playbook_name", ""),
                "parsed_at": data.get("parsed_at", ""),
                "rules_count": len(data.get("rules", []))
            })
        except Exception:
            continue
    
    return result


def check_playbook_update_needed(
    playbook_text: str,
    playbook_id: str
) -> bool:
    """
    检查 Playbook 是否需要重新解析（原文是否变更）
    
    Args:
        playbook_text: 当前的 Playbook 文本
        playbook_id: Playbook ID
        
    Returns:
        bool: 如果需要重新解析返回 True
    """
    try:
        existing = load_parsed_playbook(playbook_id)
        current_hash = compute_text_hash(playbook_text)
        return current_hash != existing.source_hash
    except FileNotFoundError:
        return True  # 文件不存在，需要解析


# =============================================================================
# 运行时函数 1: search_playbook_matches
# =============================================================================

def search_playbook_matches(
    contract_text: str,
    parsed_playbook: Union[ParsedPlaybook, List[Dict[str, Any]], str]
) -> SearchMatchesResult:
    """
    【运行时步骤】在合同文本中搜索与 Playbook 规则匹配的内容
    
    使用已解析的 Playbook 规则（预处理结果），在合同文本中进行语义搜索。
    
    【业务逻辑】
    1. 加载已解析的 Playbook 规则（支持多种输入格式）
    2. 调用大模型进行语义搜索
    3. 识别与规则关键词完全匹配或语义相似的内容
    4. 返回匹配结果及是否需要修改的建议
    
    【匹配类型】
    - exact（完全匹配）：文本中存在与规则关键词完全相同的表述
    - similar（相似表达）：文本中存在与规则关键词语义相近的表述
    
    【输出 Schema】
    {
        "matches": [
            {
                "rule_id": "rule_1",              // 匹配到的规则ID
                "rule_title": "商业秘密限定",       // 规则标题
                "matched_text": "trade secrets",  // 匹配到的文本
                "match_type": "exact",            // 匹配类型
                "similarity_score": 0.95,         // 相似度 0-1
                "location": {
                    "paragraph_index": 2,         // 段落索引
                    "context": "...前后文本..."    // 上下文
                },
                "needs_modification": true,       // 是否需要修改
                "modification_reason": "缺少法律限定语" // 修改原因
            }
        ],
        "summary": {
            "total_rules": 5,                     // 规则总数
            "matched_rules": 3,                   // 匹配的规则数
            "rules_needing_modification": 2       // 需要修改的数量
        }
    }
    
    Args:
        contract_text: 待搜索的合同文本
        parsed_playbook: 已解析的 Playbook，支持以下格式：
            - ParsedPlaybook 对象
            - 规则列表 List[Dict]
            - Playbook ID 字符串（自动加载）
        
    Returns:
        SearchMatchesResult: 包含匹配结果的对象
        
    Raises:
        ValueError: 输入参数为空时
        Exception: API 调用失败时
        
    Example:
        >>> # 使用 Playbook ID（自动加载已解析的规则）
        >>> result = search_playbook_matches(contract_text, "my_nda_rules")
        
        >>> # 使用 ParsedPlaybook 对象
        >>> parsed = load_parsed_playbook("my_nda_rules")
        >>> result = search_playbook_matches(contract_text, parsed)
        
        >>> # 使用规则列表
        >>> result = search_playbook_matches(contract_text, rules_list)
    """
    logger.info("=" * 60)
    logger.info("【search_playbook_matches】开始搜索匹配")
    logger.info(f"合同文本长度: {len(contract_text)} 字符")
    
    if not contract_text or not contract_text.strip():
        logger.error("合同文本为空")
        raise ValueError("合同文本不能为空")
    
    # 打印合同文本摘要
    print("\n" + "-" * 40)
    print("【待搜索的合同文本】")
    print("-" * 40)
    print(contract_text[:500] + "..." if len(contract_text) > 500 else contract_text)
    print("-" * 40 + "\n")
    
    # 1. 解析输入的 playbook 参数
    if isinstance(parsed_playbook, str):
        logger.info(f"从 Playbook ID 加载规则: {parsed_playbook}")
        loaded = load_parsed_playbook(parsed_playbook)
        playbook_rules = loaded.rules
    elif isinstance(parsed_playbook, ParsedPlaybook):
        logger.info("使用 ParsedPlaybook 对象")
        playbook_rules = parsed_playbook.rules
    elif isinstance(parsed_playbook, list):
        logger.info("使用规则列表")
        playbook_rules = parsed_playbook
    else:
        logger.error(f"parsed_playbook 参数格式不正确: {type(parsed_playbook)}")
        raise ValueError("parsed_playbook 参数格式不正确")
    
    logger.info(f"规则数量: {len(playbook_rules)} 条")
    
    if not playbook_rules:
        logger.error("Playbook 规则为空")
        raise ValueError("Playbook 规则不能为空")
    
    # 打印规则概要
    print("\n" + "-" * 40)
    print("【使用的 Playbook 规则】")
    print("-" * 40)
    for i, rule in enumerate(playbook_rules, 1):
        print(f"  规则 {i}: {rule.get('title', '未命名')}")
        print(f"    触发: {rule.get('trigger', '无')}")
        print(f"    动作: {rule.get('action', '无')}")
    print("-" * 40 + "\n")
    
    # 2. 将规则列表转换为 JSON 字符串
    rules_json = json.dumps(playbook_rules, ensure_ascii=False, indent=2)
    
    # 3. 获取格式化的 prompt
    system_prompt, user_prompt = format_search_matches_prompt(
        playbook_rules=rules_json,
        contract_text=contract_text
    )
    logger.info("已生成搜索 Prompt")
    
    # 4. 调用大模型 API
    logger.info("调用大模型搜索匹配...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,  # 匹配结果可能较长
        json_mode=True
    )
    
    # 5. 解析 JSON 响应
    logger.info("解析匹配结果...")
    parsed = safe_json_parse(raw_response)
    
    # 6. 提取数据
    matches = parsed.get("matches", [])
    summary = parsed.get("summary", {
        "total_rules": len(playbook_rules),
        "matched_rules": len(matches),
        "rules_needing_modification": sum(
            1 for m in matches if m.get("needs_modification", False)
        )
    })
    
    # 打印匹配结果
    logger.info(f"匹配结果: 共 {len(matches)} 处匹配")
    print("\n" + "-" * 40)
    print("【匹配结果摘要】")
    print("-" * 40)
    print(f"总规则数: {summary.get('total_rules', 0)}")
    print(f"匹配规则数: {summary.get('matched_rules', 0)}")
    print(f"需要修改数: {summary.get('rules_needing_modification', 0)}")
    for i, match in enumerate(matches, 1):
        needs_mod = "需要修改" if match.get("needs_modification") else "无需修改"
        print(f"  匹配 {i}: {match.get('rule_title', '未知')} - {needs_mod}")
        matched_text = match.get('matched_text', '') or ''
        print(f"    匹配文本: {matched_text[:50]}...")
    print("-" * 40 + "\n")
    
    logger.info("✅ 搜索匹配完成")
    logger.info("=" * 60)
    
    return SearchMatchesResult(
        matches=matches,
        summary=summary,
        raw_response=raw_response
    )


# =============================================================================
# 辅助函数: 验证和修正插入位置
# =============================================================================

def _validate_and_fix_insertion_positions(
    final_text: str,
    modifications: List[Dict[str, Any]],
    playbook_rules: List[Dict[str, Any]],
    original_text: str
) -> tuple:
    """
    验证 LLM 输出的插入位置是否正确，如果不正确则修正。
    
    关键规则：
    - "in connection with the Transaction on or after the date hereof" 
      必须插入在 "to the Recipient" 或 "to the Receiving Party" 之后
    """
    import re
    
    corrected_text = final_text
    corrected_mods = modifications
    
    # 检查是否包含需要验证位置的插入内容
    transaction_phrase = "in connection with the Transaction on or after the date hereof"
    
    if transaction_phrase.lower() in final_text.lower():
        # 检查插入位置是否正确
        # 正确模式：to the Recipient in connection with... 或 to the Receiving Party in connection with...
        correct_pattern_1 = re.compile(
            r"to\s+(the\s+)?Recipient\s+" + re.escape(transaction_phrase),
            re.IGNORECASE
        )
        correct_pattern_2 = re.compile(
            r"to\s+(the\s+)?Receiving\s+Party\s+" + re.escape(transaction_phrase),
            re.IGNORECASE
        )
        
        is_correct = correct_pattern_1.search(final_text) or correct_pattern_2.search(final_text)
        
        if not is_correct:
            logger.warning("⚠️ 检测到插入位置错误，正在修正...")
            
            # 错误模式：插入在 information 之后而不是 Recipient 之后
            # 例如：information in connection with... provided by
            wrong_pattern = re.compile(
                r"(information\s*)" + re.escape(transaction_phrase) + r"(\s*,?\s*provided)",
                re.IGNORECASE
            )
            
            if wrong_pattern.search(final_text):
                logger.info("  检测到错误模式：插入在 'information' 之后")
                # 先移除错误位置的插入
                temp_text = wrong_pattern.sub(r"\1\2", final_text)
                
                # 然后在正确位置插入
                recipient_pattern = re.compile(
                    r"(to\s+(the\s+)?Recipient)(\s*,)",
                    re.IGNORECASE
                )
                receiving_party_pattern = re.compile(
                    r"(to\s+(the\s+)?Receiving\s+Party)(\s*,)",
                    re.IGNORECASE
                )
                
                if recipient_pattern.search(temp_text):
                    corrected_text = recipient_pattern.sub(
                        r"\1 " + transaction_phrase + r"\3",
                        temp_text,
                        count=1
                    )
                    logger.info("  ✅ 已修正：插入到 'to the Recipient' 之后")
                elif receiving_party_pattern.search(temp_text):
                    corrected_text = receiving_party_pattern.sub(
                        r"\1 " + transaction_phrase + r"\3",
                        temp_text,
                        count=1
                    )
                    logger.info("  ✅ 已修正：插入到 'to the Receiving Party' 之后")
                else:
                    logger.warning("  ⚠️ 未找到合适的插入位置，保持原样")
            else:
                # 尝试其他错误模式的修正
                # 例如：没有逗号的情况
                wrong_pattern_no_comma = re.compile(
                    r"(information\s*)" + re.escape(transaction_phrase) + r"(\s+provided)",
                    re.IGNORECASE
                )
                if wrong_pattern_no_comma.search(final_text):
                    logger.info("  检测到错误模式（无逗号）：插入在 'information' 之后")
                    temp_text = wrong_pattern_no_comma.sub(r"\1\2", final_text)
                    
                    # 在正确位置插入（处理无逗号情况）
                    recipient_pattern = re.compile(
                        r"(to\s+(the\s+)?Recipient)(\s*[,\.]|\s+\w)",
                        re.IGNORECASE
                    )
                    if recipient_pattern.search(temp_text):
                        def insert_phrase(m):
                            return m.group(1) + " " + transaction_phrase + m.group(3)
                        corrected_text = recipient_pattern.sub(insert_phrase, temp_text, count=1)
                        logger.info("  ✅ 已修正：插入到 'to the Recipient' 之后")
    
    # 如果文本被修正，更新 modifications 中的相关信息
    if corrected_text != final_text:
        for mod in corrected_mods:
            if transaction_phrase.lower() in mod.get("modified_text", "").lower():
                mod["post_processed"] = True
                mod["explanation"] = (mod.get("explanation", "") + 
                    " [后处理：已修正插入位置到 'to the Recipient' 之后]")
    
    return corrected_text, corrected_mods


# =============================================================================
# 运行时函数 2: apply_playbook_modifications
# =============================================================================

def apply_playbook_modifications(
    original_text: str,
    parsed_playbook: Union[ParsedPlaybook, List[Dict[str, Any]], str],
    match_info: List[Dict[str, Any]]
) -> ApplyModificationsResult:
    """
    【运行时步骤】根据 Playbook 规则对文本进行修改
    
    使用已解析的 Playbook 规则和匹配信息，对文本进行最小化修订。
    
    【业务逻辑】
    1. 加载已解析的 Playbook 规则
    2. 根据匹配信息过滤出需要修改的项
    3. 调用大模型执行最小化修订
    4. 严格按照规则指定的方式修改，不做额外改动
    5. 输出修改详情和最终文本
    
    【修改原则】
    - 最小化修改：只改必要部分，保持原文其他内容不变
    - 严格遵循规则：只按 Playbook 规定的方式修改
    - 不添加新内容：除非规则明确要求
    - 保持一致性：修改后的表达与文档风格一致
    
    【修改类型】
    - insert：插入新内容（如添加限定语）
    - replace：替换现有内容
    - delete：删除内容
    
    【输出 Schema】
    {
        "modifications": [
            {
                "rule_id": "rule_1",                    // 应用的规则ID
                "original_text": "trade secrets",       // 原始文本
                "modified_text": "trade secrets (as defined by applicable law)",
                "modification_type": "insert",          // 修改类型
                "explanation": "添加法律限定语，明确商业秘密的法律定义范围"
            }
        ],
        "final_text": "完整的修改后文本...",            // 最终文本
        "summary": {
            "total_modifications": 2,                   // 修改总数
            "rules_applied": ["rule_1", "rule_2"],      // 应用的规则
            "unchanged_reason": null                    // 未修改原因（如有）
        }
    }
    
    Args:
        original_text: 需要修改的原始文本
        parsed_playbook: 已解析的 Playbook，支持以下格式：
            - ParsedPlaybook 对象
            - 规则列表 List[Dict]
            - Playbook ID 字符串（自动加载）
        match_info: search_playbook_matches 返回的匹配信息
        
    Returns:
        ApplyModificationsResult: 包含修改结果的对象
        
    Raises:
        ValueError: 输入参数为空时
        Exception: API 调用失败时
        
    Example:
        >>> # 完整流程
        >>> matches = search_playbook_matches(contract, "my_nda_rules")
        >>> result = apply_playbook_modifications(
        ...     contract, 
        ...     "my_nda_rules",  # 使用 playbook_id
        ...     matches.matches
        ... )
        >>> print(result.final_text)
    """
    logger.info("=" * 60)
    logger.info("【apply_playbook_modifications】开始应用修改")
    logger.info(f"原始文本长度: {len(original_text)} 字符")
    logger.info(f"匹配信息数量: {len(match_info)} 条")
    
    if not original_text or not original_text.strip():
        logger.error("原始文本为空")
        raise ValueError("原始文本不能为空")
    
    # 1. 解析输入的 playbook 参数
    if isinstance(parsed_playbook, str):
        logger.info(f"从 Playbook ID 加载规则: {parsed_playbook}")
        loaded = load_parsed_playbook(parsed_playbook)
        playbook_rules = loaded.rules
    elif isinstance(parsed_playbook, ParsedPlaybook):
        logger.info("使用 ParsedPlaybook 对象")
        playbook_rules = parsed_playbook.rules
    elif isinstance(parsed_playbook, list):
        logger.info("使用规则列表")
        playbook_rules = parsed_playbook
    else:
        logger.error(f"parsed_playbook 参数格式不正确: {type(parsed_playbook)}")
        raise ValueError("parsed_playbook 参数格式不正确")
    
    logger.info(f"规则数量: {len(playbook_rules)} 条")
    
    if not playbook_rules:
        logger.error("Playbook 规则为空")
        raise ValueError("Playbook 规则不能为空")
    
    # 2. 过滤出需要修改的匹配项
    modifications_needed = [
        m for m in match_info 
        if m.get("needs_modification", False)
    ]
    
    logger.info(f"需要修改的匹配项: {len(modifications_needed)} 处")
    
    # 如果没有需要修改的内容，直接返回原文
    if not modifications_needed:
        logger.info("无需修改，返回原文")
        print("\n" + "-" * 40)
        print("【修改结果】无需修改，所有条款已符合规则")
        print("-" * 40 + "\n")
        return ApplyModificationsResult(
            modifications=[],
            final_text=original_text,
            summary={
                "total_modifications": 0,
                "rules_applied": [],
                "unchanged_reason": "所有条款已符合 Playbook 规则，无需修改"
            },
            raw_response=""
        )
    
    # 打印需要修改的内容
    print("\n" + "-" * 40)
    print("【需要修改的匹配项】")
    print("-" * 40)
    for i, m in enumerate(modifications_needed, 1):
        print(f"  {i}. 规则: {m.get('rule_title', '未知')}")
        matched_text = m.get('matched_text', '') or ''
        print(f"     匹配: {matched_text[:50]}...")
        print(f"     原因: {m.get('modification_reason', '无')}")
    print("-" * 40 + "\n")
    
    # 3. 准备 JSON 字符串
    rules_json = json.dumps(playbook_rules, ensure_ascii=False, indent=2)
    match_json = json.dumps(modifications_needed, ensure_ascii=False, indent=2)
    
    # 4. 获取格式化的 prompt
    system_prompt, user_prompt = format_apply_modifications_prompt(
        playbook_rules=rules_json,
        match_info=match_json,
        original_text=original_text
    )
    logger.info("已生成修改 Prompt")
    
    # 5. 调用大模型 API
    logger.info("调用大模型应用修改...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,  # 低温度确保修改稳定
        max_tokens=3000,
        json_mode=True
    )
    
    # 6. 解析 JSON 响应
    logger.info("解析修改结果...")
    parsed = safe_json_parse(raw_response)
    
    # 7. 提取数据
    modifications = parsed.get("modifications", [])
    final_text = parsed.get("final_text", original_text)
    summary = parsed.get("summary", {
        "total_modifications": len(modifications),
        "rules_applied": list(set(m.get("rule_id", "") for m in modifications)),
        "unchanged_reason": None
    })
    
    # 打印修改结果
    logger.info(f"修改完成: 共 {len(modifications)} 处修改")
    print("\n" + "=" * 60)
    print("【修改结果详情】")
    print("=" * 60)
    for i, mod in enumerate(modifications, 1):
        print(f"\n修改 {i}:")
        print(f"  规则ID: {mod.get('rule_id', '未知')}")
        print(f"  修改类型: {mod.get('modification_type', '未知')}")
        print(f"  原文: {mod.get('original_text', '')}")
        print(f"  改为: {mod.get('modified_text', '')}")
        print(f"  说明: {mod.get('explanation', '无')}")
    print("\n" + "-" * 40)
    print("【修改后完整文本】")
    print("-" * 40)
    print(final_text)
    print("=" * 60 + "\n")
    
    # 8. 后处理验证：确保关键插入位置正确
    final_text, modifications = _validate_and_fix_insertion_positions(
        final_text, modifications, playbook_rules, original_text
    )
    
    logger.info("✅ 应用修改完成")
    logger.info("=" * 60)
    
    return ApplyModificationsResult(
        modifications=modifications,
        final_text=final_text,
        summary=summary,
        raw_response=raw_response
    )


# =============================================================================
# Checklist 类型规则处理函数
# =============================================================================

def search_checklist_matches(
    contract_text: str,
    checklist_rules: List[Dict[str, Any]]
) -> SearchMatchesResult:
    """
    【运行时步骤】搜索 checklist 类型规则的匹配项
    
    对于检查清单类型的规则，分析合同中是否包含所有必要元素。
    
    Args:
        contract_text: 待搜索的合同文本
        checklist_rules: checklist 类型的规则列表
        
    Returns:
        SearchMatchesResult: 包含匹配结果的对象，额外包含：
            - existing_elements: 已存在的元素
            - missing_elements: 缺失的元素
            - has_required_qualifier: 是否包含必要限定语
    """
    logger.info("=" * 60)
    logger.info("【search_checklist_matches】搜索检查清单规则匹配")
    logger.info(f"合同文本长度: {len(contract_text)} 字符")
    logger.info(f"检查清单规则数量: {len(checklist_rules)} 条")
    
    if not contract_text or not contract_text.strip():
        logger.error("合同文本为空")
        raise ValueError("合同文本不能为空")
    
    if not checklist_rules:
        logger.warning("无检查清单规则，跳过")
        return SearchMatchesResult(
            matches=[],
            summary={"total_rules": 0, "matched_clauses": 0, "rules_needing_modification": 0},
            raw_response=""
        )
    
    # 打印规则概要
    print("\n" + "-" * 40)
    print("【检查清单规则】")
    print("-" * 40)
    for i, rule in enumerate(checklist_rules, 1):
        print(f"  规则 {i}: {rule.get('title', '未命名')}")
        print(f"    必要元素: {rule.get('required_elements', [])}")
        required_qualifier = rule.get('required_qualifier', '无') or '无'
        print(f"    必要限定语: {required_qualifier[:50]}...")
    print("-" * 40 + "\n")
    
    # 将规则列表转换为 JSON 字符串
    rules_json = json.dumps(checklist_rules, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_search_checklist_matches_prompt(
        checklist_rules=rules_json,
        contract_text=contract_text
    )
    logger.info("已生成检查清单搜索 Prompt")
    
    # 调用大模型 API
    logger.info("调用大模型搜索检查清单匹配...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,
        json_mode=True
    )
    
    # 解析 JSON 响应
    logger.info("解析检查清单匹配结果...")
    parsed = safe_json_parse(raw_response)
    
    # 提取数据
    matches = parsed.get("matches", [])
    summary = parsed.get("summary", {
        "total_rules": len(checklist_rules),
        "matched_clauses": len(matches),
        "rules_needing_modification": sum(
            1 for m in matches if m.get("needs_modification", False)
        )
    })
    
    # 打印匹配结果
    logger.info(f"检查清单匹配结果: 共 {len(matches)} 处")
    print("\n" + "-" * 40)
    print("【检查清单匹配结果】")
    print("-" * 40)
    for i, match in enumerate(matches, 1):
        needs_mod = "需要修改" if match.get("needs_modification") else "无需修改"
        print(f"  匹配 {i}: {match.get('rule_title', '未知')} - {needs_mod}")
        print(f"    已有元素: {match.get('existing_elements', [])}")
        print(f"    缺失元素: {match.get('missing_elements', [])}")
        print(f"    限定语状态: {match.get('qualifier_status', '未知')}")
    print("-" * 40 + "\n")
    
    logger.info("✅ 检查清单搜索完成")
    logger.info("=" * 60)
    
    return SearchMatchesResult(
        matches=matches,
        summary=summary,
        raw_response=raw_response
    )


def apply_checklist_modifications(
    original_text: str,
    checklist_rules: List[Dict[str, Any]],
    match_info: List[Dict[str, Any]]
) -> ApplyModificationsResult:
    """
    【运行时步骤】根据 checklist 规则补充缺失的元素
    
    Args:
        original_text: 需要修改的原始文本
        checklist_rules: checklist 类型的规则列表
        match_info: search_checklist_matches 返回的匹配信息
        
    Returns:
        ApplyModificationsResult: 包含修改结果的对象
    """
    logger.info("=" * 60)
    logger.info("【apply_checklist_modifications】应用检查清单修改")
    logger.info(f"原始文本长度: {len(original_text)} 字符")
    logger.info(f"匹配信息数量: {len(match_info)} 条")
    
    if not original_text or not original_text.strip():
        logger.error("原始文本为空")
        raise ValueError("原始文本不能为空")
    
    # 过滤出需要修改的匹配项
    modifications_needed = [
        m for m in match_info 
        if m.get("needs_modification", False)
    ]
    
    logger.info(f"需要修改的匹配项: {len(modifications_needed)} 处")
    
    # 如果没有需要修改的内容，直接返回原文
    if not modifications_needed:
        logger.info("无需修改，返回原文")
        return ApplyModificationsResult(
            modifications=[],
            final_text=original_text,
            summary={
                "total_modifications": 0,
                "rules_applied": [],
                "elements_added": 0,
                "unchanged_reason": "所有条款已包含必要元素，无需修改"
            },
            raw_response=""
        )
    
    # 打印需要修改的内容
    print("\n" + "-" * 40)
    print("【需要补充的元素】")
    print("-" * 40)
    for i, m in enumerate(modifications_needed, 1):
        print(f"  {i}. 规则: {m.get('rule_title', '未知')}")
        print(f"     缺失元素: {m.get('missing_elements', [])}")
        print(f"     限定语状态: {m.get('qualifier_status', '无')}")
    print("-" * 40 + "\n")
    
    # 准备 JSON 字符串
    rules_json = json.dumps(checklist_rules, ensure_ascii=False, indent=2)
    match_json = json.dumps(modifications_needed, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_apply_checklist_modifications_prompt(
        checklist_rules=rules_json,
        match_info=match_json,
        original_text=original_text
    )
    logger.info("已生成检查清单修改 Prompt")
    
    # 调用大模型 API
    logger.info("调用大模型应用检查清单修改...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,
        json_mode=True
    )
    
    # 解析 JSON 响应
    logger.info("解析检查清单修改结果...")
    parsed = safe_json_parse(raw_response)
    
    # 提取数据
    modifications = parsed.get("modifications", [])
    final_text = parsed.get("final_text", original_text)
    summary = parsed.get("summary", {
        "total_modifications": len(modifications),
        "rules_applied": list(set(m.get("rule_id", "") for m in modifications)),
        "elements_added": sum(len(m.get("added_elements", [])) for m in modifications),
        "unchanged_reason": None
    })
    
    # 打印修改结果
    logger.info(f"检查清单修改完成: 共 {len(modifications)} 处修改")
    print("\n" + "=" * 60)
    print("【检查清单修改结果】")
    print("=" * 60)
    for i, mod in enumerate(modifications, 1):
        print(f"\n修改 {i}:")
        print(f"  规则ID: {mod.get('rule_id', '未知')}")
        print(f"  新增元素: {mod.get('added_elements', [])}")
        print(f"  新增限定语: {mod.get('added_qualifier', '无')}")
        print(f"  说明: {mod.get('explanation', '无')}")
    print("=" * 60 + "\n")
    
    logger.info("✅ 检查清单修改完成")
    logger.info("=" * 60)
    
    return ApplyModificationsResult(
        modifications=modifications,
        final_text=final_text,
        summary=summary,
        raw_response=raw_response
    )


def search_conditional_matches(
    contract_text: str,
    conditional_rules: List[Dict[str, Any]]
) -> SearchMatchesResult:
    """
    【运行时步骤】搜索 conditional 类型规则的匹配项
    
    对于条件判断类型的规则，分析合同中的相关条款，检查条件是否满足。
    
    Args:
        contract_text: 待搜索的合同文本
        conditional_rules: conditional 类型的规则列表
        
    Returns:
        SearchMatchesResult: 包含匹配结果的对象，额外包含：
            - condition_checks: 条件检查结果
            - determined_action: 确定的动作
    """
    logger.info("=" * 60)
    logger.info("【search_conditional_matches】搜索条件判断规则匹配")
    logger.info(f"合同文本长度: {len(contract_text)} 字符")
    logger.info(f"条件判断规则数量: {len(conditional_rules)} 条")
    
    if not contract_text or not contract_text.strip():
        logger.error("合同文本为空")
        raise ValueError("合同文本不能为空")
    
    if not conditional_rules:
        logger.warning("无条件判断规则，跳过")
        return SearchMatchesResult(
            matches=[],
            summary={"total_rules": 0, "matched_clauses": 0, "rules_needing_modification": 0},
            raw_response=""
        )
    
    # 打印规则概要
    print("\n" + "-" * 40)
    print("【条件判断规则】")
    print("-" * 40)
    for i, rule in enumerate(conditional_rules, 1):
        print(f"  规则 {i}: {rule.get('title', '未命名')}")
        conditions = rule.get('conditions', [])
        for j, cond in enumerate(conditions, 1):
            print(f"    条件 {j}: {cond.get('description', '无描述')}")
    print("-" * 40 + "\n")
    
    # 将规则列表转换为 JSON 字符串
    rules_json = json.dumps(conditional_rules, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_search_conditional_matches_prompt(
        conditional_rules=rules_json,
        contract_text=contract_text
    )
    logger.info("已生成条件判断搜索 Prompt")
    
    # 调用大模型 API
    logger.info("调用大模型搜索条件判断匹配...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,
        json_mode=True
    )
    
    # 解析 JSON 响应
    logger.info("解析条件判断匹配结果...")
    parsed = safe_json_parse(raw_response)
    
    # 提取数据
    matches = parsed.get("matches", [])
    summary = parsed.get("summary", {
        "total_rules": len(conditional_rules),
        "matched_clauses": len(matches),
        "rules_needing_modification": sum(
            1 for m in matches if m.get("needs_modification", False)
        )
    })
    
    # 打印匹配结果
    logger.info(f"条件判断匹配结果: 共 {len(matches)} 处")
    print("\n" + "-" * 40)
    print("【条件判断匹配结果】")
    print("-" * 40)
    for i, match in enumerate(matches, 1):
        needs_mod = "需要修改" if match.get("needs_modification") else "无需修改"
        print(f"  匹配 {i}: {match.get('rule_title', '未知')} - {needs_mod}")
        action_details = match.get("action_details", {})
        if action_details.get("should_add"):
            add_content = action_details.get('content_to_add', '') or ''
            print(f"    应添加: {add_content[:50]}...")
        else:
            print(f"    不添加原因: {action_details.get('should_not_add_reason', '无')}")
    print("-" * 40 + "\n")
    
    logger.info("✅ 条件判断搜索完成")
    logger.info("=" * 60)
    
    return SearchMatchesResult(
        matches=matches,
        summary=summary,
        raw_response=raw_response
    )


def apply_conditional_modifications(
    original_text: str,
    conditional_rules: List[Dict[str, Any]],
    match_info: List[Dict[str, Any]]
) -> ApplyModificationsResult:
    """
    【运行时步骤】根据 conditional 规则的条件分析结果应用修改
    
    Args:
        original_text: 需要修改的原始文本
        conditional_rules: conditional 类型的规则列表
        match_info: search_conditional_matches 返回的匹配信息
        
    Returns:
        ApplyModificationsResult: 包含修改结果的对象
    """
    logger.info("=" * 60)
    logger.info("【apply_conditional_modifications】应用条件判断修改")
    logger.info(f"原始文本长度: {len(original_text)} 字符")
    logger.info(f"匹配信息数量: {len(match_info)} 条")
    
    if not original_text or not original_text.strip():
        logger.error("原始文本为空")
        raise ValueError("原始文本不能为空")
    
    # 过滤出需要修改的匹配项
    modifications_needed = [
        m for m in match_info 
        if m.get("needs_modification", False)
    ]
    
    logger.info(f"需要修改的匹配项: {len(modifications_needed)} 处")
    
    # 如果没有需要修改的内容，直接返回原文
    if not modifications_needed:
        logger.info("无需修改，返回原文")
        return ApplyModificationsResult(
            modifications=[],
            final_text=original_text,
            summary={
                "total_modifications": 0,
                "rules_applied": [],
                "conditions_triggered": [],
                "unchanged_reason": "条件不满足，无需修改"
            },
            raw_response=""
        )
    
    # 打印需要修改的内容
    print("\n" + "-" * 40)
    print("【需要应用的条件判断修改】")
    print("-" * 40)
    for i, m in enumerate(modifications_needed, 1):
        print(f"  {i}. 规则: {m.get('rule_title', '未知')}")
        action_details = m.get("action_details", {})
        print(f"     动作: {m.get('determined_action', '无')}")
        content_to_add = action_details.get('content_to_add', '') or ''
        print(f"     添加内容: {content_to_add[:80]}...")
    print("-" * 40 + "\n")
    
    # 准备 JSON 字符串
    rules_json = json.dumps(conditional_rules, ensure_ascii=False, indent=2)
    match_json = json.dumps(modifications_needed, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_apply_conditional_modifications_prompt(
        conditional_rules=rules_json,
        match_info=match_json,
        original_text=original_text
    )
    logger.info("已生成条件判断修改 Prompt")
    
    # 调用大模型 API
    logger.info("调用大模型应用条件判断修改...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,
        json_mode=True
    )
    
    # 解析 JSON 响应
    logger.info("解析条件判断修改结果...")
    parsed = safe_json_parse(raw_response)
    
    # 提取数据
    modifications = parsed.get("modifications", [])
    final_text = parsed.get("final_text", original_text)
    summary = parsed.get("summary", {
        "total_modifications": len(modifications),
        "rules_applied": list(set(m.get("rule_id", "") for m in modifications)),
        "conditions_triggered": [],
        "unchanged_reason": None
    })
    
    # 打印修改结果
    logger.info(f"条件判断修改完成: 共 {len(modifications)} 处修改")
    print("\n" + "=" * 60)
    print("【条件判断修改结果】")
    print("=" * 60)
    for i, mod in enumerate(modifications, 1):
        print(f"\n修改 {i}:")
        print(f"  规则ID: {mod.get('rule_id', '未知')}")
        print(f"  修改类型: {mod.get('modification_type', '未知')}")
        print(f"  触发条件: {mod.get('condition_met', '无')}")
        print(f"  说明: {mod.get('explanation', '无')}")
    print("=" * 60 + "\n")
    
    logger.info("✅ 条件判断修改完成")
    logger.info("=" * 60)
    
    return ApplyModificationsResult(
        modifications=modifications,
        final_text=final_text,
        summary=summary,
        raw_response=raw_response
    )


def separate_rules_by_type(
    rules: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    按类型分离规则
    
    Args:
        rules: 混合类型的规则列表
        
    Returns:
        dict: {
            "add_text": [...],     # 添加文字型规则
            "checklist": [...],    # 检查清单型规则
            "conditional": [...]   # 条件判断型规则
        }
    """
    result = {
        "add_text": [],
        "checklist": [],
        "conditional": []
    }
    
    for rule in rules:
        rule_type = rule.get("type", "add_text")  # 默认为 add_text
        if rule_type == "checklist":
            result["checklist"].append(rule)
        elif rule_type == "conditional":
            result["conditional"].append(rule)
        else:
            result["add_text"].append(rule)
    
    logger.debug(f"规则分类: add_text={len(result['add_text'])}, checklist={len(result['checklist'])}, conditional={len(result['conditional'])}")
    return result


def review_contract_enhanced(
    contract_text: str,
    parsed_playbook: Union[ParsedPlaybook, List[Dict[str, Any]], str]
) -> Dict[str, Any]:
    """
    增强版合同审查函数：支持混合类型规则
    
    自动识别规则类型，分别处理 add_text、checklist 和 conditional 类型的规则。
    
    Args:
        contract_text: 合同文本
        parsed_playbook: 已解析的 Playbook（支持多种格式）
        
    Returns:
        dict: 包含匹配和修改结果的字典
        {
            "add_text_results": {...},      # add_text 规则的处理结果
            "checklist_results": {...},     # checklist 规则的处理结果
            "conditional_results": {...},   # conditional 规则的处理结果
            "combined_final_text": "...",   # 合并后的最终文本
            "summary": {...}
        }
    """
    logger.info("=" * 60)
    logger.info("【review_contract_enhanced】增强版合同审查")
    
    # 解析输入的 playbook 参数
    if isinstance(parsed_playbook, str):
        loaded = load_parsed_playbook(parsed_playbook)
        all_rules = loaded.rules
    elif isinstance(parsed_playbook, ParsedPlaybook):
        all_rules = parsed_playbook.rules
    elif isinstance(parsed_playbook, list):
        all_rules = parsed_playbook
    else:
        raise ValueError("parsed_playbook 参数格式不正确")
    
    # 按类型分离规则
    rules_by_type = separate_rules_by_type(all_rules)
    
    logger.info(f"规则分类完成: add_text={len(rules_by_type['add_text'])}, checklist={len(rules_by_type['checklist'])}, conditional={len(rules_by_type['conditional'])}")
    
    results = {
        "add_text_results": None,
        "checklist_results": None,
        "conditional_results": None,
        "combined_final_text": contract_text,
        "summary": {}
    }
    
    current_text = contract_text
    
    # 处理 add_text 类型规则
    if rules_by_type["add_text"]:
        logger.info("处理 add_text 类型规则...")
        matches = search_playbook_matches(current_text, rules_by_type["add_text"])
        modifications = apply_playbook_modifications(
            current_text,
            rules_by_type["add_text"],
            matches.matches
        )
        results["add_text_results"] = {
            "matches": matches,
            "modifications": modifications
        }
        current_text = modifications.final_text
    
    # 处理 checklist 类型规则
    if rules_by_type["checklist"]:
        logger.info("处理 checklist 类型规则...")
        matches = search_checklist_matches(current_text, rules_by_type["checklist"])
        modifications = apply_checklist_modifications(
            current_text,
            rules_by_type["checklist"],
            matches.matches
        )
        results["checklist_results"] = {
            "matches": matches,
            "modifications": modifications
        }
        current_text = modifications.final_text
    
    # 处理 conditional 类型规则
    if rules_by_type["conditional"]:
        logger.info("处理 conditional 类型规则...")
        matches = search_conditional_matches(current_text, rules_by_type["conditional"])
        modifications = apply_conditional_modifications(
            current_text,
            rules_by_type["conditional"],
            matches.matches
        )
        results["conditional_results"] = {
            "matches": matches,
            "modifications": modifications
        }
        current_text = modifications.final_text
    
    results["combined_final_text"] = current_text
    results["summary"] = {
        "total_add_text_rules": len(rules_by_type["add_text"]),
        "total_checklist_rules": len(rules_by_type["checklist"]),
        "total_conditional_rules": len(rules_by_type["conditional"]),
        "add_text_modifications": len(results["add_text_results"]["modifications"].modifications) if results["add_text_results"] else 0,
        "checklist_modifications": len(results["checklist_results"]["modifications"].modifications) if results["checklist_results"] else 0,
        "conditional_modifications": len(results["conditional_results"]["modifications"].modifications) if results["conditional_results"] else 0
    }
    
    logger.info("✅ 增强版合同审查完成")
    logger.info("=" * 60)
    
    return results


# =============================================================================
# 便捷函数
# =============================================================================

def review_contract(
    contract_text: str,
    playbook_id: str
) -> Dict[str, Any]:
    """
    便捷函数：使用已解析的 Playbook 审查合同
    
    这是运行时的便捷函数，前提是 Playbook 已经预处理并保存。
    
    Args:
        contract_text: 合同文本
        playbook_id: 已解析的 Playbook ID
        
    Returns:
        dict: 包含匹配和修改结果的字典
        {
            "matches": SearchMatchesResult,
            "modifications": ApplyModificationsResult
        }
        
    Example:
        >>> # 前置步骤（只需执行一次）
        >>> parse_playbook_to_rules(playbook_text, "my_nda_rules")
        
        >>> # 运行时使用
        >>> result = review_contract(contract_text, "my_nda_rules")
        >>> print(result["modifications"].final_text)
    """
    # Step 1: 搜索匹配
    matches = search_playbook_matches(
        contract_text=contract_text,
        parsed_playbook=playbook_id
    )
    
    # Step 2: 应用修改
    modifications = apply_playbook_modifications(
        original_text=contract_text,
        parsed_playbook=playbook_id,
        match_info=matches.matches
    )
    
    return {
        "matches": matches,
        "modifications": modifications
    }




# =============================================================================
# 从历史合同学习规则相关函数
# =============================================================================

@dataclass
class LearnedRule:
    """
    从历史合同中学习到的规则
    """
    id: str
    name: str
    type: str  # add_text, replace_text, checklist, conditional
    trigger: str
    action: str
    exact_wording: str
    insert_position: Optional[Dict[str, Any]]
    before_example: str
    after_example: str
    rationale: str
    generalizability: str
    confidence: float
    # 来源追溯
    source_case_id: str
    source_case_name: str
    learned_at: str
    # 使用统计
    times_applied: int = 0
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedRule":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", "add_text"),
            trigger=data.get("trigger", ""),
            action=data.get("action", ""),
            exact_wording=data.get("exact_wording", ""),
            insert_position=data.get("insert_position"),
            before_example=data.get("before_example", ""),
            after_example=data.get("after_example", ""),
            rationale=data.get("rationale", ""),
            generalizability=data.get("generalizability", ""),
            confidence=data.get("confidence", 0.5),
            source_case_id=data.get("source_case_id", ""),
            source_case_name=data.get("source_case_name", ""),
            learned_at=data.get("learned_at", ""),
            times_applied=data.get("times_applied", 0),
            enabled=data.get("enabled", True)
        )


@dataclass
class LearnedRulesStore:
    """
    学习规则存储结构
    """
    version: str
    rules: List[LearnedRule]
    learning_statistics: Dict[str, Any]
    last_updated: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "learning_statistics": self.learning_statistics,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedRulesStore":
        rules = [LearnedRule.from_dict(r) for r in data.get("rules", [])]
        return cls(
            version=data.get("version", "1.0"),
            rules=rules,
            learning_statistics=data.get("learning_statistics", {}),
            last_updated=data.get("last_updated", "")
        )
    
    @classmethod
    def empty(cls) -> "LearnedRulesStore":
        return cls(
            version="1.0",
            rules=[],
            learning_statistics={
                "total_cases_learned": 0,
                "total_rules_extracted": 0
            },
            last_updated=datetime.now().isoformat()
        )


def load_learned_rules() -> LearnedRulesStore:
    """
    加载学习到的规则
    
    Returns:
        LearnedRulesStore: 学习规则存储对象
    """
    logger.info("加载学习到的规则...")
    
    # 确保目录存在
    os.makedirs(LEARNED_RULES_DIR, exist_ok=True)
    
    if not os.path.exists(LEARNED_RULES_FILE):
        logger.info("学习规则文件不存在，返回空存储")
        return LearnedRulesStore.empty()
    
    try:
        with open(LEARNED_RULES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        store = LearnedRulesStore.from_dict(data)
        logger.info(f"✅ 已加载 {len(store.rules)} 条学习规则")
        return store
    except Exception as e:
        logger.error(f"加载学习规则失败: {e}")
        return LearnedRulesStore.empty()


def save_learned_rules(store: LearnedRulesStore) -> str:
    """
    保存学习到的规则
    
    Args:
        store: 学习规则存储对象
        
    Returns:
        str: 保存的文件路径
    """
    logger.info(f"保存学习规则，共 {len(store.rules)} 条...")
    
    # 确保目录存在
    os.makedirs(LEARNED_RULES_DIR, exist_ok=True)
    
    # 更新时间戳
    store.last_updated = datetime.now().isoformat()
    
    # 更新统计
    store.learning_statistics["total_rules_extracted"] = len(store.rules)
    
    with open(LEARNED_RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(store.to_dict(), f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 已保存到: {LEARNED_RULES_FILE}")
    return LEARNED_RULES_FILE


def extract_rules_from_diff(
    before_text: str,
    after_text: str,
    case_name: str = "未命名案例",
    case_id: Optional[str] = None
) -> List[LearnedRule]:
    """
    从合同修改差异中提取规则
    
    这是规则学习的核心函数：分析"修改前"和"修改后"的文本差异，
    提取可复用的修改规则。
    
    Args:
        before_text: 修改前的合同文本
        after_text: 修改后的合同文本
        case_name: 案例名称（用于来源追溯）
        case_id: 案例ID（可选，自动生成）
        
    Returns:
        List[LearnedRule]: 提取到的规则列表
    """
    logger.info("=" * 60)
    logger.info("【extract_rules_from_diff】从差异中提取规则")
    logger.info(f"案例名称: {case_name}")
    logger.info(f"修改前文本长度: {len(before_text)} 字符")
    logger.info(f"修改后文本长度: {len(after_text)} 字符")
    
    if not before_text or not after_text:
        logger.error("输入文本为空")
        raise ValueError("修改前和修改后的文本都不能为空")
    
    # 生成案例ID
    if not case_id:
        case_id = f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 打印输入摘要
    print("\n" + "-" * 40)
    print("【修改前文本摘要】")
    print("-" * 40)
    print(before_text[:500] + "..." if len(before_text) > 500 else before_text)
    print("\n" + "-" * 40)
    print("【修改后文本摘要】")
    print("-" * 40)
    print(after_text[:500] + "..." if len(after_text) > 500 else after_text)
    print("-" * 40 + "\n")
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_extract_rules_from_diff_prompt(
        before_text=before_text,
        after_text=after_text
    )
    logger.info("已生成规则提取 Prompt")
    
    # 调用大模型 API
    logger.info("调用大模型分析差异并提取规则...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=4000,  # 规则可能较长
        json_mode=True
    )
    
    # 解析 JSON 响应
    logger.info("解析提取结果...")
    parsed = safe_json_parse(raw_response)
    
    # 提取规则
    extracted_rules_raw = parsed.get("extracted_rules", [])
    summary = parsed.get("summary", {})
    
    logger.info(f"发现 {len(extracted_rules_raw)} 条可提取的规则")
    
    # 转换为 LearnedRule 对象
    learned_rules = []
    current_time = datetime.now().isoformat()
    
    for i, rule_raw in enumerate(extracted_rules_raw, 1):
        rule = LearnedRule(
            id=rule_raw.get("id", f"learned_{i}"),
            name=rule_raw.get("name", f"规则 {i}"),
            type=rule_raw.get("type", "add_text"),
            trigger=rule_raw.get("trigger", ""),
            action=rule_raw.get("action", ""),
            exact_wording=rule_raw.get("exact_wording", ""),
            insert_position=rule_raw.get("insert_position"),
            before_example=rule_raw.get("before_example", ""),
            after_example=rule_raw.get("after_example", ""),
            rationale=rule_raw.get("rationale", ""),
            generalizability=rule_raw.get("generalizability", ""),
            confidence=rule_raw.get("confidence", 0.5),
            source_case_id=case_id,
            source_case_name=case_name,
            learned_at=current_time,
            times_applied=0,
            enabled=True
        )
        learned_rules.append(rule)
        
        logger.info(f"  规则 {i}: {rule.name}")
        logger.info(f"    类型: {rule.type}")
        logger.info(f"    触发: {rule.trigger}")
        logger.info(f"    置信度: {rule.confidence}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("【规则提取结果】")
    print("=" * 60)
    print(f"发现修改总数: {summary.get('total_modifications_found', 0)}")
    print(f"可提取规则数: {summary.get('extractable_rules', 0)}")
    print(f"整体分析: {summary.get('overall_analysis', '无')}")
    for rule in learned_rules:
        print(f"\n规则: {rule.name}")
        print(f"  类型: {rule.type}")
        print(f"  触发: {rule.trigger}")
        print(f"  动作: {rule.action}")
        print(f"  精确措辞: {rule.exact_wording}")
        print(f"  置信度: {rule.confidence}")
    print("=" * 60 + "\n")
    
    logger.info("✅ 规则提取完成")
    logger.info("=" * 60)
    
    return learned_rules


def add_learned_rules(
    new_rules: List[LearnedRule],
    deduplicate: bool = True
) -> LearnedRulesStore:
    """
    添加学习到的规则到存储
    
    Args:
        new_rules: 新学习到的规则列表
        deduplicate: 是否去重（基于 exact_wording 相似度）
        
    Returns:
        LearnedRulesStore: 更新后的存储对象
    """
    logger.info(f"添加 {len(new_rules)} 条新规则...")
    
    # 加载现有规则
    store = load_learned_rules()
    
    # 添加新规则
    added_count = 0
    for rule in new_rules:
        # 简单去重：检查是否已存在相同的 exact_wording
        if deduplicate:
            duplicate = False
            for existing in store.rules:
                if existing.exact_wording and rule.exact_wording:
                    # 简单的相似度检查
                    if existing.exact_wording.lower() == rule.exact_wording.lower():
                        logger.info(f"  跳过重复规则: {rule.name}")
                        duplicate = True
                        break
            if duplicate:
                continue
        
        # 确保规则ID唯一
        existing_ids = {r.id for r in store.rules}
        if rule.id in existing_ids:
            rule.id = f"{rule.id}_{len(store.rules) + 1}"
        
        store.rules.append(rule)
        added_count += 1
        logger.info(f"  添加规则: {rule.name}")
    
    # 更新统计
    store.learning_statistics["total_rules_extracted"] = len(store.rules)
    if "total_cases_learned" not in store.learning_statistics:
        store.learning_statistics["total_cases_learned"] = 0
    store.learning_statistics["total_cases_learned"] += 1
    
    # 保存
    save_learned_rules(store)
    
    logger.info(f"✅ 成功添加 {added_count} 条规则，当前共 {len(store.rules)} 条")
    
    return store


def learn_from_contract_diff(
    before_text: str,
    after_text: str,
    case_name: str = "未命名案例",
    auto_save: bool = True
) -> Dict[str, Any]:
    """
    从合同修改差异中学习规则（完整流程）
    
    这是对外暴露的主要函数，完成从差异分析到规则存储的完整流程。
    
    Args:
        before_text: 修改前的合同文本
        after_text: 修改后的合同文本
        case_name: 案例名称
        auto_save: 是否自动保存到存储
        
    Returns:
        dict: {
            "extracted_rules": List[LearnedRule],  # 提取到的规则
            "saved": bool,                          # 是否已保存
            "store": LearnedRulesStore              # 更新后的存储
        }
    """
    logger.info("=" * 60)
    logger.info("【learn_from_contract_diff】开始学习流程")
    
    # Step 1: 提取规则
    extracted_rules = extract_rules_from_diff(
        before_text=before_text,
        after_text=after_text,
        case_name=case_name
    )
    
    # Step 2: 保存规则（如果启用）
    if auto_save and extracted_rules:
        store = add_learned_rules(extracted_rules)
    else:
        store = load_learned_rules()
    
    logger.info("✅ 学习流程完成")
    logger.info("=" * 60)
    
    return {
        "extracted_rules": extracted_rules,
        "saved": auto_save and bool(extracted_rules),
        "store": store
    }


def search_learned_rules_matches(
    contract_text: str,
    learned_rules: Optional[List[LearnedRule]] = None
) -> SearchMatchesResult:
    """
    在合同中搜索可以应用学习规则的位置
    
    Args:
        contract_text: 新合同文本
        learned_rules: 学习到的规则列表（可选，默认从存储加载）
        
    Returns:
        SearchMatchesResult: 匹配结果
    """
    logger.info("=" * 60)
    logger.info("【search_learned_rules_matches】搜索学习规则匹配")
    
    # 加载规则
    if learned_rules is None:
        store = load_learned_rules()
        learned_rules = [r for r in store.rules if r.enabled]
    
    if not learned_rules:
        logger.warning("没有可用的学习规则")
        return SearchMatchesResult(
            matches=[],
            summary={"total_learned_rules": 0, "matched_rules": 0, "rules_needing_modification": 0},
            raw_response=""
        )
    
    logger.info(f"合同文本长度: {len(contract_text)} 字符")
    logger.info(f"学习规则数量: {len(learned_rules)} 条")
    
    # 将规则转换为JSON
    rules_for_api = []
    for rule in learned_rules:
        rules_for_api.append({
            "id": rule.id,
            "name": rule.name,
            "type": rule.type,
            "trigger": rule.trigger,
            "action": rule.action,
            "exact_wording": rule.exact_wording,
            "insert_position": rule.insert_position,
            "source_case_name": rule.source_case_name
        })
    
    rules_json = json.dumps(rules_for_api, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_search_learned_rules_matches_prompt(
        learned_rules=rules_json,
        contract_text=contract_text
    )
    
    # 调用大模型 API
    logger.info("调用大模型搜索学习规则匹配...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=3000,
        json_mode=True
    )
    
    # 解析响应
    parsed = safe_json_parse(raw_response)
    matches = parsed.get("matches", [])
    summary = parsed.get("summary", {})
    
    logger.info(f"匹配结果: {len(matches)} 处")
    logger.info("✅ 学习规则匹配搜索完成")
    logger.info("=" * 60)
    
    return SearchMatchesResult(
        matches=matches,
        summary=summary,
        raw_response=raw_response
    )


def apply_learned_rules(
    contract_text: str,
    match_info: List[Dict[str, Any]],
    learned_rules: Optional[List[LearnedRule]] = None
) -> ApplyModificationsResult:
    """
    应用学习到的规则修改合同
    
    Args:
        contract_text: 合同文本
        match_info: 匹配信息
        learned_rules: 学习到的规则列表（可选）
        
    Returns:
        ApplyModificationsResult: 修改结果
    """
    logger.info("=" * 60)
    logger.info("【apply_learned_rules】应用学习规则")
    
    # 加载规则
    if learned_rules is None:
        store = load_learned_rules()
        learned_rules = [r for r in store.rules if r.enabled]
    
    # 过滤需要修改的匹配项
    modifications_needed = [m for m in match_info if m.get("needs_modification", False)]
    
    if not modifications_needed:
        logger.info("无需修改，返回原文")
        return ApplyModificationsResult(
            modifications=[],
            final_text=contract_text,
            summary={"total_modifications": 0, "rules_applied": [], "unchanged_reason": "所有条款已符合学习规则"},
            raw_response=""
        )
    
    # 准备API调用
    rules_for_api = []
    for rule in learned_rules:
        rules_for_api.append({
            "id": rule.id,
            "name": rule.name,
            "type": rule.type,
            "trigger": rule.trigger,
            "action": rule.action,
            "exact_wording": rule.exact_wording,
            "insert_position": rule.insert_position,
            "source_case_name": rule.source_case_name
        })
    
    rules_json = json.dumps(rules_for_api, ensure_ascii=False, indent=2)
    match_json = json.dumps(modifications_needed, ensure_ascii=False, indent=2)
    
    # 获取格式化的 prompt
    system_prompt, user_prompt = format_apply_learned_rules_prompt(
        learned_rules=rules_json,
        match_info=match_json,
        contract_text=contract_text
    )
    
    # 调用大模型 API
    logger.info("调用大模型应用学习规则...")
    raw_response = call_openai_api(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=4000,
        json_mode=True
    )
    
    # 解析响应
    parsed = safe_json_parse(raw_response)
    modifications = parsed.get("modifications", [])
    final_text = parsed.get("final_text", contract_text)
    summary = parsed.get("summary", {})
    
    # 更新规则使用统计
    store = load_learned_rules()
    applied_rule_ids = {m.get("rule_id") for m in modifications}
    for rule in store.rules:
        if rule.id in applied_rule_ids:
            rule.times_applied += 1
    save_learned_rules(store)
    
    logger.info(f"修改完成: {len(modifications)} 处")
    logger.info("✅ 学习规则应用完成")
    logger.info("=" * 60)
    
    return ApplyModificationsResult(
        modifications=modifications,
        final_text=final_text,
        summary=summary,
        raw_response=raw_response
    )


def review_contract_with_learned_rules(
    contract_text: str,
    include_preset_rules: bool = True,
    preset_playbook: Optional[Union[ParsedPlaybook, List[Dict], str]] = None
) -> Dict[str, Any]:
    """
    使用学习规则审查合同（可同时使用预设规则）
    
    Args:
        contract_text: 合同文本
        include_preset_rules: 是否同时使用预设规则
        preset_playbook: 预设Playbook（可选）
        
    Returns:
        dict: {
            "learned_results": {...},    # 学习规则的审查结果
            "preset_results": {...},     # 预设规则的审查结果（如果启用）
            "combined_final_text": "...", # 合并后的最终文本
            "summary": {...}
        }
    """
    logger.info("=" * 60)
    logger.info("【review_contract_with_learned_rules】使用学习规则审查合同")
    logger.info(f"是否包含预设规则: {include_preset_rules}")
    
    results = {
        "learned_results": None,
        "preset_results": None,
        "combined_final_text": contract_text,
        "summary": {}
    }
    
    current_text = contract_text
    
    # 1. 应用预设规则（如果启用）
    if include_preset_rules and preset_playbook:
        logger.info("首先应用预设规则...")
        preset_result = review_contract_enhanced(current_text, preset_playbook)
        results["preset_results"] = preset_result
        current_text = preset_result.get("combined_final_text", current_text)
    
    # 2. 应用学习规则
    logger.info("应用学习规则...")
    store = load_learned_rules()
    enabled_rules = [r for r in store.rules if r.enabled]
    
    if enabled_rules:
        # 搜索匹配
        matches = search_learned_rules_matches(current_text, enabled_rules)
        
        # 应用修改
        modifications = apply_learned_rules(
            current_text,
            matches.matches,
            enabled_rules
        )
        
        results["learned_results"] = {
            "matches": matches,
            "modifications": modifications
        }
        current_text = modifications.final_text
    else:
        logger.info("没有启用的学习规则")
        results["learned_results"] = {
            "matches": SearchMatchesResult([], {}, ""),
            "modifications": ApplyModificationsResult([], current_text, {}, "")
        }
    
    results["combined_final_text"] = current_text
    results["summary"] = {
        "learned_rules_count": len(enabled_rules),
        "learned_modifications": len(results["learned_results"]["modifications"].modifications) if results["learned_results"] else 0,
        "preset_modifications": sum([
            len(results["preset_results"].get("add_text_results", {}).get("modifications", ApplyModificationsResult([], "", {}, "")).modifications) if results["preset_results"] else 0,
            len(results["preset_results"].get("checklist_results", {}).get("modifications", ApplyModificationsResult([], "", {}, "")).modifications) if results["preset_results"] else 0,
            len(results["preset_results"].get("conditional_results", {}).get("modifications", ApplyModificationsResult([], "", {}, "")).modifications) if results["preset_results"] else 0
        ])
    }
    
    logger.info("✅ 审查完成")
    logger.info("=" * 60)
    
    return results


def get_learned_rules_stats() -> Dict[str, Any]:
    """
    获取学习规则的统计信息
    
    Returns:
        dict: 统计信息
    """
    store = load_learned_rules()
    
    # 按类型统计
    type_counts = {}
    for rule in store.rules:
        rule_type = rule.type
        type_counts[rule_type] = type_counts.get(rule_type, 0) + 1
    
    # 按来源统计
    source_counts = {}
    for rule in store.rules:
        source = rule.source_case_name
        source_counts[source] = source_counts.get(source, 0) + 1
    
    # 置信度分布
    high_conf = sum(1 for r in store.rules if r.confidence >= 0.8)
    medium_conf = sum(1 for r in store.rules if 0.5 <= r.confidence < 0.8)
    low_conf = sum(1 for r in store.rules if r.confidence < 0.5)
    
    return {
        "total_rules": len(store.rules),
        "enabled_rules": sum(1 for r in store.rules if r.enabled),
        "total_applications": sum(r.times_applied for r in store.rules),
        "type_distribution": type_counts,
        "source_distribution": source_counts,
        "confidence_distribution": {
            "high (>=0.8)": high_conf,
            "medium (0.5-0.8)": medium_conf,
            "low (<0.5)": low_conf
        },
        "learning_statistics": store.learning_statistics,
        "last_updated": store.last_updated
    }


if __name__ == "__main__":
    playbook_json_path = "/Users/zrr/projects/法律ai助手/nda_demo/playbook_mapping.json"
    with open(playbook_json_path, "r") as f:
        playbook_json = json.load(f)

    final_playbook_json = []
    
    for display_rule in playbook_json["display_rules"]:
        playbook_text = display_rule["rule"]
        
        # 如果原始配置中已有 exact_wording，优先使用
        original_exact_wording = display_rule.get("exact_wording", "")
        
        print(f"\n{'='*60}")
        print(f"处理规则: {display_rule.get('usr_playbook', '')}")
        print(f"规则文本: {playbook_text}")
        print(f"原始 exact_wording: {original_exact_wording}")
        print(f"{'='*60}")
        
        result = parse_playbook_to_rules(playbook_text, auto_save=False)
        
        # 将 ParsedPlaybook 对象转换为字典，并与原有 display_rule 合并
        result_dict = result.to_dict()
        merged = {**display_rule, **result_dict}
        
        # 确保每条规则都有 exact_wording 字段
        # 优先使用原始配置中的 exact_wording
        for rule in merged.get("rules", []):
            if original_exact_wording and not rule.get("exact_wording"):
                rule["exact_wording"] = original_exact_wording
                print(f"  - 规则 {rule.get('id')}: 使用原始 exact_wording = '{original_exact_wording}'")
            elif rule.get("exact_wording"):
                print(f"  - 规则 {rule.get('id')}: AI 解析的 exact_wording = '{rule.get('exact_wording')}'")
            else:
                print(f"  - 规则 {rule.get('id')}: 警告！没有 exact_wording")
        
        final_playbook_json.append(merged)
    
    # 保存到新文件
    new_playbook_json_path = playbook_json_path.replace(".json", "_final.json")
    with open(new_playbook_json_path, "w") as f:
        json.dump(final_playbook_json, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"已保存到: {new_playbook_json_path}")
    print(f"{'='*60}")


        
    # result = process_contract_with_playbook(contract_text, playbook_text)
    # print(result