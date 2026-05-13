from __future__ import annotations

import json

import httpx
import pytest

from intel_engine.llm import DeepSeekModelProvider, OpenAIModelProvider, build_llm_provider
from intel_engine.settings import Settings


def test_build_llm_provider_defaults_to_fake_provider():
    provider = build_llm_provider(Settings(llm_provider="fake", llm_model="fake-default"))

    score = provider.score_item({"title": "OpenAI launches GPT-5"})

    assert score.raw_json["provider"] == "fake"
    assert score.category == "general"


def test_build_llm_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        build_llm_provider(Settings(llm_provider="other"))


def test_openai_provider_requires_client_or_installed_sdk():
    provider = OpenAIModelProvider(model="gpt-test", timeout_seconds=5, client=None)

    with pytest.raises(RuntimeError, match="OpenAI SDK"):
        provider.score_item({"title": "OpenAI launches GPT-5"})


def test_build_llm_provider_supports_deepseek():
    provider = build_llm_provider(
        Settings(
            llm_provider="deepseek",
            llm_model="deepseek-chat",
            deepseek_api_key="test-key",
        )
    )

    assert isinstance(provider, DeepSeekModelProvider)


def test_build_llm_provider_uses_current_deepseek_default_model_when_not_configured():
    provider = build_llm_provider(Settings(llm_provider="deepseek", deepseek_api_key="test-key"))

    assert isinstance(provider, DeepSeekModelProvider)
    assert provider.model == "deepseek-v4-flash"


def test_deepseek_provider_posts_json_mode_request_and_parses_model_score():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "usage": {"total_tokens": 321},
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "category": "ai_models",
                                    "relevance_score": 86,
                                    "impact_score": 82,
                                    "novelty_score": 78,
                                    "actionability_score": 64,
                                    "credibility_score": 91,
                                    "summary_cn": "DeepSeek 生成的中文摘要。",
                                    "title_cn": "OpenAI 发布新模型",
                                    "reason": "模型发布来自高权威信源，值得关注。",
                                    "seller_action_level": "review",
                                    "raw_json": {"modelOutputVersion": "test"},
                                }
                            )
                        }
                    }
                ],
            },
        )

    provider = DeepSeekModelProvider(
        model="deepseek-chat",
        api_key="test-key",
        timeout_seconds=5,
        base_url="https://api.deepseek.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    score = provider.score_item({"title": "OpenAI launches GPT-5", "source": "OpenAI"})

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert "json" in captured["payload"]["messages"][0]["content"].lower()
    assert score.category == "ai_models"
    assert score.summary_cn == "DeepSeek 生成的中文摘要。"
    assert score.raw_json["provider"] == "deepseek"
    assert score.raw_json["model"] == "deepseek-chat"
    assert score.raw_json["usage"] == {"total_tokens": 321}


def test_deepseek_provider_normalizes_string_raw_json_from_model_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "category": "ai_models",
                                    "relevance_score": 86,
                                    "impact_score": 82,
                                    "novelty_score": 78,
                                    "actionability_score": 64,
                                    "credibility_score": 91,
                                    "summary_cn": "中文摘要。",
                                    "title_cn": "中文标题",
                                    "reason": "推荐理由。",
                                    "seller_action_level": "review",
                                    "raw_json": "{\"unexpected\":\"string\"}",
                                }
                            )
                        }
                    }
                ],
            },
        )

    provider = DeepSeekModelProvider(
        model="deepseek-chat",
        api_key="test-key",
        timeout_seconds=5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    score = provider.score_item({"title": "OpenAI launches GPT-5"})

    assert score.raw_json["modelOutput"] == '{"unexpected":"string"}'
    assert score.raw_json["provider"] == "deepseek"
