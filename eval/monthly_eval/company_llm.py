"""{{COMPANY}} API judge model adapter for DeepEval.

Wraps the {{COMPANY}} LLM gateway (OpenAI-compatible chat completions) as a
DeepEvalBaseLLM so DeepEval/Ragas metrics can use it as the judge.
No external paid API is used — only {{COMPANY}} (COMPANY_API_KEY).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Tuple, Union

import requests
from deepeval.models import DeepEvalBaseLLM


def _load_env() -> dict:
    """Load KEY=VALUE pairs from ~/.openclaw/.env into a dict (no mutation of os.environ)."""
    env = {}
    path = os.path.expanduser("~/.openclaw/.env")
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


class CompanyLLM(DeepEvalBaseLLM):
    """DeepEval judge backed by the {{COMPANY}} LLM gateway."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        base_url: str = "https://llm.example.com/v1/chat/completions",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        env = _load_env()
        self.api_key = env.get("COMPANY_API_KEY") or os.environ.get("COMPANY_API_KEY")
        if not self.api_key:
            raise RuntimeError("COMPANY_API_KEY not found in ~/.openclaw/.env or env")

    def get_model_name(self) -> str:
        return f"company/{self.model}"

    def _chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        resp = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def generate(
        self, prompt: str, schema: Optional[Any] = None
    ) -> Union[str, Any]:
        """DeepEval calls generate(prompt, schema=schema)."""
        messages = [{"role": "user", "content": prompt}]
        raw = self._chat(messages)
        if schema is not None:
            parsed = self._try_parse_schema(raw, schema)
            if parsed is not None:
                return parsed
        return raw

    def _try_parse_schema(self, raw: str, schema: Any) -> Optional[Any]:
        """Attempt to coerce the raw string into the requested pydantic schema."""
        try:
            import pydantic

            if isinstance(schema, type) and issubclass(schema, pydantic.BaseModel):
                # Strip markdown fences if present
                cleaned = raw.strip()
                fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
                if fence:
                    cleaned = fence.group(1).strip()
                # Find first { ... } block
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1 and end > start:
                    cleaned = cleaned[start : end + 1]
                data = json.loads(cleaned)
                return schema.model_validate(data)
        except Exception:
            return None
        return None

    async def a_generate(self, prompt: str, schema: Optional[Any] = None) -> str:
        return self.generate(prompt, schema=schema)

    def load_model(self, *args, **kwargs):
        return self
