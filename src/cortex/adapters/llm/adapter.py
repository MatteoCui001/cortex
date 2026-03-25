"""
LLM adapter for metadata extraction via OpenRouter-compatible API.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import httpx

from cortex.adapters.llm.classifier import (
    CLASSIFY_PROMPT,
    STANCE_PARSE_PROMPT,
    parse_classification,
)
from cortex.domain.ports import LLMPort
from cortex.domain.stance import parse_user_stance

EXTRACT_PROMPT = """Analyze the following content and extract structured metadata.
Return ONLY valid JSON with these fields:
- summary: 2-3 sentence summary in the same language as the content
- tags: list of 3-5 lowercase tags
- entities: list of {{type, name}} where type is one of: company, person, technology, concept, fund
- thesis_links: list of matching thesis names from this list: {thesis_list}
- confidence: float 0.0-1.0 indicating how confident/well-supported the content's claims are
- event_type: one of: article, meeting, note, thesis, chat

Content:
{content}"""


def _ssl_verify() -> bool:
    """Check CORTEX_SSL_VERIFY env var (default True)."""
    val = os.environ.get("CORTEX_SSL_VERIFY", "1").lower()
    return val not in ("0", "false", "no")


class OpenRouterLLM(LLMPort):
    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-haiku-4.5",
        base_url: str = "https://openrouter.ai/api/v1",
        chat_endpoint: str = "/chat/completions",
        thesis_list: Optional[list[str]] = None,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._chat_endpoint = chat_endpoint
        self._thesis_list = thesis_list or []

    async def extract_metadata(self, content: str) -> dict:
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = EXTRACT_PROMPT.format(
            content=truncated,
            thesis_list=", ".join(self._thesis_list) or "(none defined yet)",
        )
        response = await self._chat(prompt)
        return _parse_json(response)

    async def classify_three_dimensions(self, content: str) -> dict:
        """Classify content along source, nature, temporality dimensions."""
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = CLASSIFY_PROMPT.format(content=truncated)
        response = await self._chat(prompt)
        return parse_classification(response)

    async def parse_stance_llm(self, annotation: str) -> str:
        """Use LLM to parse ambiguous user stance annotation."""
        # Try fast pattern matching first
        fast = parse_user_stance(annotation)
        if fast:
            return fast
        # Fall back to LLM
        prompt = STANCE_PARSE_PROMPT.format(annotation=annotation)
        response = await self._chat(prompt)
        response = response.strip().lower()
        if response in ("agree", "disagree", "uncertain", "skip"):
            return response
        return "uncertain"

    async def summarize(self, content: str, max_length: int = 200) -> str:
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = (
            f"Summarize the following in {max_length} characters or less,"
            f" in the same language as the content:\n\n{truncated}"
        )
        return await self._chat(prompt)

    async def chat(self, prompt: str) -> str:
        return await self._chat(prompt)

    async def _chat(self, prompt: str) -> str:
        verify = _ssl_verify()
        async with httpx.AsyncClient(timeout=60, verify=verify) as client:
            resp = await client.post(
                f"{self._base_url}{self._chat_endpoint}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Return empty defaults
    return {
        "summary": "",
        "tags": [],
        "entities": [],
        "thesis_links": [],
        "confidence": 0.5,
        "event_type": "note",
    }
