"""Post-processing plugin: refine ASR text via local LLM (LM Studio API)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, Optional
from urllib import request

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "# Role: ASR Post-Processor\n"
    "You are a text correction tool, NOT a chatbot. Never reply, answer, or converse.\n"
    "\n"
    "# Task\n"
    "Input = raw ASR transcript. Output = minimally corrected text. Nothing else.\n"
    "\n"
    "# Rules\n"
    "1. Remove filler words (嗯、啊、那个、就是说、然后、对吧)\n"
    "2. Merge stutters/repeats\n"
    "3. Fix obvious grammar errors, add punctuation\n"
    "4. Preserve original meaning — do NOT rephrase, expand, or answer\n"
    "5. If input looks like a question, output that same question (do NOT answer it)\n"
    "6. Output ONLY the corrected text, no explanation, no prefix\n"
    "\n"
    "# Examples\n"
    "IN: 嗯那个我想问一下就是说这个功能什么时候能上线啊\n"
    "OUT: 我想问一下，这个功能什么时候能上线？\n"
    "\n"
    "IN: 你是什么模型？\n"
    "OUT: 你是什么模型？\n"
    "\n"
    "IN: 然后他说他说那个project要delay两周对吧\n"
    "OUT: 他说那个 project 要 delay 两周。\n"
    "\n"
    "IN: 该这样修复。\n"
    "OUT: 该这样修复。"
)


def create_refiner(config: dict) -> Optional[Callable[[str], str]]:
    """Create a text refiner function from config. Returns None if disabled."""
    llm_cfg = config.get("llm", {})
    if not llm_cfg.get("enabled", False):
        return None

    base_url = llm_cfg.get("base_url", "http://localhost:1234")
    model = llm_cfg.get("model", "")
    system_prompt = llm_cfg.get("system_prompt", DEFAULT_PROMPT)
    timeout = llm_cfg.get("timeout", 10)

    max_retries = llm_cfg.get("max_retries", 1)
    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
    logger.info("LLM 精炼已启用: %s (model=%s, retries=%d)", endpoint, model or "default", max_retries)

    def _call_llm(text: str) -> str:
        """Single LLM call. Raises on failure."""
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "reasoning_effort": "none",
        }).encode()
        req = request.Request(
            endpoint, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip().strip('"\'""''')

    def refine(text: str) -> str:
        if not text or not text.strip():
            return text
        t0 = time.time()
        logger.info("LLM 精炼开始，输入 %d 字符: %s", len(text), text[:80])

        last_exc = None
        # 首次 + max_retries 次重试
        for attempt in range(1 + max_retries):
            try:
                if attempt > 0:
                    time.sleep(min(attempt * 0.5, 2))
                    logger.info("LLM 精炼重试 %d/%d", attempt, max_retries)
                raw = _call_llm(text)
            except Exception as exc:
                last_exc = exc
                continue

            # 校验结果
            refined = re.sub(r'^(?:Output|Result|精炼|输出)[：:]\s*', '', raw).strip()
            if not refined:
                logger.warning("LLM 返回空结果，使用原文")
                return text
            if len(refined) > len(text) * 2 + 20:
                logger.warning("LLM 输出过长 (%d→%d 字符)，疑似跑飞，使用原文", len(text), len(refined))
                return text
            # 跑飞检测
            _punct = "，。？！、；：""''…—·\n ,.?!;:\"'  "
            src = "".join(c for c in text if c not in _punct)
            dst = "".join(c for c in refined if c not in _punct)
            # 1) 原文核心片段应在输出中保留
            if len(src) >= 2:
                has_overlap = any(src[i:i+2] in dst for i in range(len(src) - 1))
                if not has_overlap:
                    logger.warning("LLM 输出与原文无内容重叠，疑似跑飞，使用原文")
                    return text
            # 2) 输出不应是对输入的"回答"（以第一人称开头且原文不含第一人称）
            if refined.lstrip()[0:1] == "我" and "我" not in text:
                logger.warning("LLM 输出疑似回答而非修正，使用原文")
                return text

            elapsed = time.time() - t0
            logger.info("LLM 精炼完成 (%.2fs): [%s] → [%s]", elapsed, text[:50], refined[:50])
            return refined

        elapsed = time.time() - t0
        logger.warning("LLM 精炼失败 (%.2fs, %d次尝试)，使用原文: %s", elapsed, 1 + max_retries, last_exc)
        return text

    return refine


def wrap_result_handler(handler: Callable, refine: Callable[[str], str]) -> Callable:
    """Wrap a result handler to refine text before passing through."""
    def wrapped(result) -> None:
        if not getattr(result, "error", None) and getattr(result, "text", ""):
            result.text = refine(result.text)
        return handler(result)
    return wrapped
