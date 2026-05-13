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
    confidence_score: float | None = Field(default=None, ge=0, le=100)
    tags: list[str] = Field(default_factory=list)
    event_type: str | None = None
    key_facts: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    raw_json: dict[str, Any] = Field(default_factory=dict)


class ScreeningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screen_status: str
    screen_bucket: str
    relevance_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    category: str
    title_cn: str
    summary_cn: str
    tags: list[str] = Field(default_factory=list)
    reason_code: str
    reason_cn: str
    raw_json: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(Protocol):
    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        ...


class ScreeningProvider(Protocol):
    def screen_item(self, payload: dict[str, Any]) -> ScreeningResult:
        ...


class FakeLLMProvider:
    def __init__(self, score: ModelScore):
        self.score = score

    def score_item(self, payload: dict[str, Any]) -> ModelScore:
        return self.score


class FakeScreeningProvider:
    def __init__(self, result: ScreeningResult | None = None):
        self.result = result or default_fake_screening_result()

    def screen_item(self, payload: dict[str, Any]) -> ScreeningResult:
        channel = payload.get("channel")
        category = self.result.category
        if channel == "amazon" and category not in {"policy", "account_health", "fba_logistics", "ads_ppc", "listing_seo", "fees_margin", "product_research", "tools", "compliance_trade"}:
            source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            defaults = source.get("defaultCategories") if isinstance(source, dict) else None
            category = str(defaults[0]) if isinstance(defaults, list) and defaults else "policy"
        return self.result.model_copy(update={"category": category})


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
                        "seller_action_level, confidence_score, tags, event_type, key_facts, risk_flags, raw_json。"
                        "只做多维评分、中文标题、中文摘要和推荐理由，不要决定 selected。"
                        "评分必须遵守：相关度、影响度、新颖度、行动价值、可信度均为 0-100。"
                        "AI 频道重技术/产品/生态影响；Amazon 频道重卖家利润、风险和行动价值。"
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

    def screen_item(self, payload: dict[str, Any]) -> ScreeningResult:
        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AIHot 情报平台的低成本初筛器。只输出合法 JSON，不要输出 Markdown。"
                        "JSON 字段必须为：screen_status, screen_bucket, relevance_score, confidence_score, "
                        "category, title_cn, summary_cn, tags, reason_code, reason_cn, raw_json。"
                        "screen_status 只能是 accepted/rejected/failed；screen_bucket 只能是 "
                        "core/related/watch/irrelevant/invalid。accepted 只能用于 core 或 related。"
                        "初筛目标是判断内容是否值得进入业务情报库，不判断是否精选。"
                        "必须拒绝旧内容、无具体链接、泛教程、营销软文、低信息增量、频道无关内容。"
                        "中文标题必须具体，中文摘要必须说明发生了什么、涉及谁、变化点和影响。"
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
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
            raise RuntimeError("DeepSeek screening response was not valid JSON.") from exc
        if not isinstance(parsed_content, dict):
            raise RuntimeError("DeepSeek screening response JSON must be an object.")
        parsed_content = _normalize_screening_payload(parsed_content)
        result = ScreeningResult.model_validate(parsed_content)
        raw_json = dict(result.raw_json)
        raw_json.update(
            {
                "provider": "deepseek",
                "model": self.model,
                "responseId": response_json.get("id"),
                "usage": response_json.get("usage"),
            }
        )
        return result.model_copy(update={"raw_json": raw_json})

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


def build_screening_provider(settings: Settings | None = None) -> ScreeningProvider:
    resolved_settings = settings or Settings()
    if resolved_settings.llm_provider == "fake":
        return FakeScreeningProvider()
    if resolved_settings.llm_provider == "deepseek":
        return DeepSeekModelProvider(
            model=resolved_settings.llm_screening_model,
            api_key=resolved_settings.deepseek_api_key,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
            base_url=resolved_settings.deepseek_base_url,
        )
    raise ValueError(f"Unsupported screening provider: {resolved_settings.llm_provider}")


def build_scoring_provider(settings: Settings | None = None) -> LLMProvider:
    resolved_settings = settings or Settings()
    if resolved_settings.llm_provider == "fake":
        return FakeLLMProvider(default_fake_model_score())
    if resolved_settings.llm_provider == "deepseek":
        return DeepSeekModelProvider(
            model=resolved_settings.llm_scoring_model,
            api_key=resolved_settings.deepseek_api_key,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
            base_url=resolved_settings.deepseek_base_url,
        )
    if resolved_settings.llm_provider == "openai":
        return OpenAIModelProvider(
            model=resolved_settings.llm_model,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported scoring provider: {resolved_settings.llm_provider}")


def default_fake_model_score() -> ModelScore:
    return ModelScore(
        category="general",
        relevance_score=75,
        impact_score=75,
        novelty_score=70,
        actionability_score=70,
        credibility_score=80,
        confidence_score=75,
        summary_cn="Fake provider 生成的摘要。",
        title_cn=None,
        reason="Fake provider 仅用于稳定测试和本地流水线验证。",
        seller_action_level="review",
        tags=["测试", "本地验证"],
        event_type="test",
        key_facts=[],
        risk_flags=[],
        raw_json={"provider": "fake", "model": "fake-default"},
    )


def default_fake_screening_result() -> ScreeningResult:
    return ScreeningResult(
        screen_status="accepted",
        screen_bucket="core",
        relevance_score=80,
        confidence_score=80,
        category="ai_models",
        title_cn="待 AI 精筛标题",
        summary_cn="待 AI 精筛摘要。",
        tags=["测试", "本地验证"],
        reason_code="test_provider",
        reason_cn="Fake screening provider 仅用于测试。",
        raw_json={"provider": "fake", "model": "fake-screening"},
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
    normalized.setdefault("tags", [])
    normalized.setdefault("key_facts", [])
    normalized.setdefault("risk_flags", [])
    raw_json = normalized.get("raw_json")
    if raw_json is None:
        normalized["raw_json"] = {}
    elif isinstance(raw_json, str):
        normalized["raw_json"] = {"modelOutput": raw_json}
    elif not isinstance(raw_json, dict):
        normalized["raw_json"] = {"modelOutput": str(raw_json)}
    return normalized


def _normalize_screening_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("tags", [])
    raw_json = normalized.get("raw_json")
    if raw_json is None:
        normalized["raw_json"] = {}
    elif isinstance(raw_json, str):
        normalized["raw_json"] = {"modelOutput": raw_json}
    elif not isinstance(raw_json, dict):
        normalized["raw_json"] = {"modelOutput": str(raw_json)}
    return normalized
