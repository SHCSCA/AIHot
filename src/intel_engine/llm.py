from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from intel_engine.settings import Settings


class ModelScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    relevance_score: float = Field(ge=0, le=100)
    impact_score: float = Field(ge=0, le=100)
    novelty_score: float = Field(ge=0, le=100)
    actionability_score: float = Field(ge=0, le=100)
    credibility_score: float = Field(ge=0, le=100)
    summary_cn: str
    title_cn: str | None = None
    reason: str
    seller_action_level: str | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(Protocol):
    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        ...


class FakeLLMProvider:
    def __init__(self, score: ModelScore):
        self.score = score

    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        return self.score


class OpenAIModelProvider:
    def __init__(self, *, model: str, timeout_seconds: int, client: Any | None = None):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client

    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        client = self.client or _build_openai_client(timeout_seconds=self.timeout_seconds)
        response = client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": "Return a structured intelligence score. Do not decide whether the item is selected.",
                },
                {"role": "user", "content": str(payload)},
            ],
            text_format=ModelScore,
        )
        parsed = response.output_parsed
        if not isinstance(parsed, ModelScore):
            raise RuntimeError("OpenAI response did not match ModelScore schema")
        return parsed


class DeepSeekModelProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        timeout_seconds: int,
        base_url: str = "https://api.deepseek.com",
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek.")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")
        self.client = client

    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是情报平台的信息评分器。只输出合法 JSON，不要输出 Markdown。"
                        "JSON 必须匹配字段：category, relevance_score, impact_score, novelty_score, "
                        "actionability_score, credibility_score, summary_cn, title_cn, reason, "
                        "seller_action_level, raw_json。"
                        "只做多维评分、中文标题、中文摘要和推荐理由，不要决定 selected。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self._post_chat_completion(request_body, headers)
        response.raise_for_status()
        response_json = response.json()
        content = _extract_chat_content(response_json)
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek response was not valid JSON.") from exc
        if not isinstance(parsed_content, dict):
            raise RuntimeError("DeepSeek response JSON must be an object.")
        parsed_content = _normalize_model_score_payload(parsed_content)

        score = ModelScore.model_validate(parsed_content)
        raw_json = dict(score.raw_json)
        raw_json.update(
            {
                "provider": "deepseek",
                "model": self.model,
                "responseId": response_json.get("id"),
                "usage": response_json.get("usage"),
            }
        )
        return score.model_copy(update={"raw_json": raw_json})

    def _post_chat_completion(self, request_body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        url = f"{self.base_url}/chat/completions"
        if self.client is not None:
            return self.client.post(url, headers=headers, json=request_body, timeout=self.timeout_seconds)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, headers=headers, json=request_body)


class LLMEnricher:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def enrich(self, payload: dict[str, Any]) -> ModelScore:
        return self.provider.score_item(payload)


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    resolved_settings = settings or Settings()
    if resolved_settings.llm_provider == "fake":
        return FakeLLMProvider(default_fake_model_score())
    if resolved_settings.llm_provider == "openai":
        return OpenAIModelProvider(
            model=resolved_settings.llm_model,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
        )
    if resolved_settings.llm_provider == "deepseek":
        model = resolved_settings.llm_model
        if model == "fake-default":
            model = "deepseek-v4-flash"
        return DeepSeekModelProvider(
            model=model,
            api_key=resolved_settings.deepseek_api_key,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
            base_url=resolved_settings.deepseek_base_url,
        )
    raise ValueError(f"Unsupported LLM provider: {resolved_settings.llm_provider}")


def default_fake_model_score() -> ModelScore:
    return ModelScore(
        category="general",
        relevance_score=75,
        impact_score=75,
        novelty_score=70,
        actionability_score=70,
        credibility_score=80,
        summary_cn="Fake provider 生成的摘要。",
        title_cn=None,
        reason="Fake provider 仅用于稳定测试和本地流水线验证。",
        seller_action_level="review",
        raw_json={"provider": "fake", "model": "fake-default"},
    )


def _build_openai_client(*, timeout_seconds: int):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK is not installed. Install the optional OpenAI dependency before use.") from exc
    return OpenAI(timeout=timeout_seconds)


def _extract_chat_content(response_json: dict[str, Any]) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("DeepSeek response did not include choices[0].message.content.") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("DeepSeek response content was empty.")
    return content


def _normalize_model_score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    raw_json = normalized.get("raw_json")
    if raw_json is None:
        normalized["raw_json"] = {}
    elif isinstance(raw_json, str):
        normalized["raw_json"] = {"modelOutput": raw_json}
    elif not isinstance(raw_json, dict):
        normalized["raw_json"] = {"modelOutput": str(raw_json)}
    return normalized
