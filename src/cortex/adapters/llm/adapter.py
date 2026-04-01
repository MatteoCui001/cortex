"""
LLM adapter for metadata extraction via OpenRouter-compatible API.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from cortex.domain.ports import LLMPort
from cortex.domain.stance import parse_user_stance
from cortex.adapters.llm.classifier import (
    CLASSIFY_PROMPT,
    STANCE_PARSE_PROMPT,
    parse_classification,
)

EXTRACT_PROMPT = """You are a knowledge ingestion gatekeeper for a VC investor's personal knowledge system.
Your job is to decide whether content is worth ingesting, and if so, extract structured metadata.

DECISION RULES:
- SKIP tool configurations, prompt templates, plugin settings, system instructions, boilerplate
  Examples to skip: "Translate to Chinese", "Make shorter", "Rewrite as tweet", "Generate table of contents"
- SKIP Obsidian system files: daily note templates, dashboard views, dataview queries, folder indexes,
  file listings, plugin configs, CSS snippets, canvas files, weekly/monthly review templates
  Examples to skip: "## Tasks", "dataview TABLE", "file.name", "cssclass:", "Weekly Dashboard", "Daily Log Template"
- SKIP content that is purely structural with no knowledge: table of contents, navigation pages,
  index files that only list other files, empty templates with only headings
- KEEP all substantive knowledge: articles, meeting notes, research, observations, opinions, deal info
- KEEP short user notes — even a few words like "蛮酷下周IC" or "光伏银浆成本降30%" are high-value fleeting thoughts
- KEEP anything related to: companies, investments, technologies, industry trends, people, deals
- When in doubt about SUBSTANTIVE content, KEEP — but when the content is clearly a template/system file, SKIP

Return ONLY valid JSON. If the content should be skipped:
{{"skip": true, "skip_reason": "brief explanation"}}

If the content should be kept, return:
{{"skip": false, "summary": "2-3 sentence summary in the SAME LANGUAGE as the content", "tags": ["3-5 lowercase tags"], "entities": [{{"type": "company|person|technology|concept|fund", "name": "entity name"}}], "thesis_links": ["matching thesis names from: {thesis_list}"], "confidence": 0.0-1.0, "event_type": "article|meeting|note|thesis|chat", "relevance": 0.0-1.0}}

The "relevance" field measures how relevant this content is to the user's investment focus areas.

Content:
{content}"""


THESIS_IMPACT_PROMPT = """You are an investment research analyst. Assess whether the following event supports, contradicts, or is neutral to the given thesis.

Thesis: {thesis_text}
Thesis stance: {thesis_stance}

Event summary: {event_summary}
Event content: {event_content}

Return ONLY valid JSON with these fields:
- impact: one of "supports", "contradicts", "neutral"
- confidence_delta: float 0.0-1.0 indicating how strongly this evidence affects the thesis (0.0 = irrelevant, 1.0 = very strong evidence)
- rationale: one sentence explaining your assessment"""


GENERATE_THESES_PROMPT = """You are an investment research analyst helping a VC investor formulate investment theses.

Given a set of recent events/notes about the theme "{theme}", generate 1-3 specific, opinionated, falsifiable investment theses.

Rules:
- Each thesis must be a SPECIFIC CLAIM or PREDICTION, not just a topic label
- Include timeframes where possible (e.g., "by 2027", "in the next 18 months")
- Include a clear directional stance (bullish/bearish/specific prediction)
- Write in the SAME LANGUAGE as the input content
- Each thesis should be independently falsifiable — you could later say "this was right" or "this was wrong"

BAD examples (too vague, just topic labels):
- "AI Native 应用" ← this is a theme, not a thesis
- "新能源" ← this is a sector, not a thesis
- "Open Source Commercialization" ← no claim here

GOOD examples (specific, falsifiable claims):
- "AI agent基建（支付、身份、安全等）将会是26年的重点"
- "光伏去银化将在2027年推到全行业"
- "Open source AI models will commoditize inference, making the application layer the primary value capture point by 2026"

IMPORTANT — Do NOT generate theses that overlap with these EXISTING ones:
{existing_theses}

Events under theme "{theme}":
{events_text}

Return ONLY valid JSON array:
[{{"text": "the thesis statement", "stance": "bullish|bearish|neutral", "rationale": "1-2 sentence explanation of why this thesis is worth tracking"}}]"""


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
        thesis = ", ".join(self._thesis_list) or "(none defined yet)"
        # Use string concatenation to avoid .format() breaking on {/} in content
        prompt = (
            EXTRACT_PROMPT.replace("{thesis_list}", thesis)
            .replace("{content}", truncated)
        )
        response = await self._chat(prompt)
        result = _parse_json(response)
        # Normalize skip field
        if result.get("skip") is True:
            return {"skip": True, "skip_reason": result.get("skip_reason", "")}
        result["skip"] = False
        return result

    async def classify_three_dimensions(self, content: str) -> dict:
        """Classify content along source, nature, temporality dimensions."""
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = CLASSIFY_PROMPT.replace("{content}", truncated)
        response = await self._chat(prompt)
        return parse_classification(response)

    async def parse_stance_llm(self, annotation: str) -> str:
        """Use LLM to parse ambiguous user stance annotation."""
        # Try fast pattern matching first
        fast = parse_user_stance(annotation)
        if fast:
            return fast
        # Fall back to LLM
        prompt = STANCE_PARSE_PROMPT.replace("{annotation}", annotation)
        response = await self._chat(prompt)
        response = response.strip().lower()
        if response in ("agree", "disagree", "uncertain", "skip"):
            return response
        return "uncertain"

    async def summarize(self, content: str, max_length: int = 200) -> str:
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = f"Summarize the following in {max_length} characters or less, in the same language as the content:\n\n{truncated}"
        return await self._chat(prompt)

    async def assess_thesis_impact(
        self, event_content: str, event_summary: str, thesis_text: str, thesis_stance: str,
    ) -> dict:
        truncated = event_content[:3000] if len(event_content) > 3000 else event_content
        prompt = THESIS_IMPACT_PROMPT.replace(
            "{thesis_text}", thesis_text
        ).replace(
            "{thesis_stance}", thesis_stance
        ).replace(
            "{event_summary}", event_summary
        ).replace(
            "{event_content}", truncated
        )
        response = await self._chat(prompt)
        parsed = _parse_json(response)
        impact = parsed.get("impact", "neutral")
        if impact not in ("supports", "contradicts", "neutral"):
            impact = "neutral"
        delta = float(parsed.get("confidence_delta", 0.0))
        delta = max(0.0, min(1.0, delta))
        return {
            "impact": impact,
            "confidence_delta": delta,
            "rationale": parsed.get("rationale", ""),
        }

    async def generate_theses(self, theme: str, events_text: str,
                              existing_theses: list[str] | None = None) -> list[dict]:
        """Generate investment theses from events under a theme."""
        existing_str = "\n".join(f"- {t}" for t in (existing_theses or []))
        if not existing_str:
            existing_str = "(none yet)"
        prompt = (
            GENERATE_THESES_PROMPT
            .replace("{theme}", theme)
            .replace("{events_text}", events_text[:6000])
            .replace("{existing_theses}", existing_str)
        )
        response = await self._chat(prompt)
        parsed = _parse_json(response)
        # Handle both single dict and list
        if isinstance(parsed, dict):
            if parsed.get("text"):
                return [parsed]
            return []
        if isinstance(parsed, list):
            return [t for t in parsed if isinstance(t, dict) and t.get("text")]
        return []

    async def chat(self, prompt: str) -> str:
        return await self._chat(prompt)

    async def _chat(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=90) as client:
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