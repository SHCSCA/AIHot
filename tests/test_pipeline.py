from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from intel_engine.db import create_engine_from_settings, init_schema, sessionmaker_for_engine
from intel_engine.llm import FakeLLMProvider, FakeScreeningProvider, ModelScore, ScreeningResult
from intel_engine.models import (
    ClusterMemberRecord,
    EventClusterRecord,
    FetchJobRecord,
    FetchRunRecord,
    ModelScoreRecord,
    NormalizedItemRecord,
    RankedItemRecord,
    RawDocumentRecord,
    SourceRecord,
    SourceStateRecord,
)
from intel_engine.pipeline import (
    _apply_screening_guardrails,
    _ensure_active_strategy,
    _fake_score,
    _model_payload,
    _normalize_raw_document,
    reprocess_existing_items,
    run_pipeline_once,
    run_worker_once,
)
from intel_engine.settings import Settings
from intel_engine.sources import SourceRegistry, SourceUpsert


def _session_factory(tmp_path):
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'production.sqlite3'}")
    engine = create_engine_from_settings(settings)
    init_schema(engine)
    return sessionmaker_for_engine(engine)


def _add_source(session, source_id: str, url: str, tier: str = "T1") -> None:
    SourceRegistry(session).upsert_source(
        SourceUpsert(
            id=source_id,
            channel="ai",
            source_type="rss",
            tier=tier,
            name=source_id.replace("_", " ").title(),
            url=url,
            language="en",
            region="global",
            marketplace=None,
            authority_weight=95 if tier == "T1" else 70,
            noise_level=0.05,
            fetch_adapter="rss",
            parser_type="rss",
            default_categories=["ai_models"],
            fetch_interval_minutes=60,
            enabled=True,
            visibility="public",
            notes=None,
        )
    )


def _rss(title: str, link: str, summary: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Feed</title>
        <item>
          <title>{title}</title>
          <link>{link}</link>
          <pubDate>Tue, 12 May 2026 08:00:00 GMT</pubDate>
          <description>{summary}</description>
        </item>
      </channel>
    </rss>
    """


def _stable_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider(
        ModelScore(
            category="ai_models",
            relevance_score=95,
            impact_score=95,
            novelty_score=90,
            actionability_score=90,
            credibility_score=95,
            confidence_score=88,
            summary_cn="AI 处理后的中文摘要。",
            title_cn=None,
            reason="测试推荐理由。",
            seller_action_level="review",
            tags=["模型发布", "官方动态"],
            event_type="model_release",
            key_facts=["OpenAI 发布新模型"],
            risk_flags=[],
            raw_json={"provider": "fake", "model": "fake-default"},
        )
    )


def _stable_screening_provider() -> FakeScreeningProvider:
    return FakeScreeningProvider(
        ScreeningResult(
            screen_status="accepted",
            screen_bucket="core",
            relevance_score=92,
            confidence_score=88,
            category="ai_models",
            title_cn="OpenAI 发布 GPT-5",
            summary_cn="OpenAI 发布新模型摘要。",
            tags=["模型发布", "官方动态"],
            reason_code="accepted",
            reason_cn="信息增量明确。",
            raw_json={"provider": "fake", "model": "fake-screening"},
        )
    )


def test_amazon_screening_guardrail_accepts_fba_missing_inventory_signal():
    now = datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
    source = SourceRecord(
        id="ecommercebytes",
        channel="amazon",
        source_type="rss",
        tier="T3",
        name="EcommerceBytes RSS",
        url="https://www.ecommercebytes.com/feed/",
        language="en",
        region="global",
        marketplace="global",
        authority_weight=72,
        noise_level=0.35,
        fetch_adapter="rss",
        parser_type="rss",
        default_categories=["policy", "fees_margin", "tools"],
        fetch_interval_minutes=60,
        enabled=True,
        visibility="public",
        source_group="media",
        collection_status="collectable",
        free_access=True,
    )
    raw_document = RawDocumentRecord(
        fetch_run_id=1,
        source_id=source.id,
        url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        canonical_url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        content_type="application/rss+xml",
        body_text=(
            "Amazon offers a perk to sellers who use its FBA fulfillment services when products go missing "
            "upon arrival at Amazon fulfillment centers."
        ),
        body_html=None,
        response_headers_json={
            "x-intel-title": "The Amazon FBA Perk You May Not Know About",
            "x-intel-published-at": now.isoformat(),
        },
        content_hash="amazon-fba-perk",
        fetched_at=now,
    )
    rejected = ScreeningResult(
        screen_status="rejected",
        screen_bucket="irrelevant",
        relevance_score=20,
        confidence_score=70,
        category="fba_logistics",
        title_cn="你可能不知道的亚马逊FBA福利",
        summary_cn="文章介绍亚马逊FBA入仓后商品丢失时卖家可能使用的权益。",
        tags=["FBA", "库存"],
        reason_code="low_info_generic",
        reason_cn="内容为一般性FBA福利介绍，信息增量低。",
        raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )

    corrected = _apply_screening_guardrails(rejected, raw_document, source)

    assert corrected.screen_status == "accepted"
    assert corrected.screen_bucket == "related"
    assert corrected.relevance_score >= 72
    assert corrected.confidence_score >= 72
    assert corrected.reason_code == "seller_ops_signal"
    assert "库存" in corrected.reason_cn
    assert corrected.raw_json["guardrail"] == "amazon_seller_ops_signal"


def test_amazon_screening_guardrail_rescues_low_confidence_seller_signal():
    now = datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
    source = SourceRecord(
        id="ecommercebytes",
        channel="amazon",
        source_type="rss",
        tier="T3",
        name="EcommerceBytes RSS",
        url="https://www.ecommercebytes.com/feed/",
        language="en",
        region="global",
        marketplace="global",
        authority_weight=72,
        noise_level=0.35,
        fetch_adapter="rss",
        parser_type="rss",
        default_categories=["fba_logistics"],
        fetch_interval_minutes=60,
        enabled=True,
        visibility="public",
        source_group="media",
        collection_status="collectable",
        free_access=True,
    )
    raw_document = RawDocumentRecord(
        fetch_run_id=1,
        source_id=source.id,
        url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        canonical_url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        content_type="application/rss+xml",
        body_text="FBA sellers can reconcile missing inventory after products arrive at Amazon fulfillment centers.",
        body_html=None,
        response_headers_json={"x-intel-title": "The Amazon FBA Perk You May Not Know About"},
        content_hash="amazon-fba-low-confidence",
        fetched_at=now,
    )
    low_confidence = ScreeningResult(
        screen_status="accepted",
        screen_bucket="related",
        relevance_score=65,
        confidence_score=55,
        category="fba_logistics",
        title_cn="亚马逊FBA入仓丢件权益提醒",
        summary_cn="内容涉及FBA卖家在货件入仓后发生库存丢失时的处理方式。",
        tags=["FBA", "库存"],
        reason_code="accepted",
        reason_cn="模型认为相关但置信度不足。",
        raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )

    corrected = _apply_screening_guardrails(low_confidence, raw_document, source)

    assert corrected.screen_status == "accepted"
    assert corrected.relevance_score >= 72
    assert corrected.confidence_score >= 72
    assert corrected.reason_code == "seller_ops_signal"


def test_amazon_screening_guardrail_repairs_schema_invalid_seller_signal():
    now = datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc)
    source = SourceRecord(
        id="ecommercebytes",
        channel="amazon",
        source_type="rss",
        tier="T3",
        name="EcommerceBytes RSS",
        url="https://www.ecommercebytes.com/feed/",
        language="en",
        region="global",
        marketplace="global",
        authority_weight=72,
        noise_level=0.35,
        fetch_adapter="rss",
        parser_type="rss",
        default_categories=["fba_logistics"],
        fetch_interval_minutes=60,
        enabled=True,
        visibility="public",
        source_group="media",
        collection_status="collectable",
        free_access=True,
    )
    raw_document = RawDocumentRecord(
        fetch_run_id=1,
        source_id=source.id,
        url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        canonical_url="https://www.ecommercebytes.com/2026/05/13/the-amazon-fba-perk-you-may-not-know-about/",
        content_type="application/rss+xml",
        body_text=(
            "FBA sellers can reconcile missing inventory and seek reimbursement after products arrive "
            "at Amazon fulfillment centers."
        ),
        body_html=None,
        response_headers_json={"x-intel-title": "The Amazon FBA Perk You May Not Know About"},
        content_hash="amazon-fba-schema-invalid",
        fetched_at=now,
    )
    invalid = ScreeningResult(
        screen_status="rejected",
        screen_bucket="invalid",
        relevance_score=72,
        confidence_score=72,
        category="seller_benefit",
        title_cn="亚马逊FBA入仓丢件权益提醒",
        summary_cn="内容涉及FBA卖家在货件入仓后发生库存丢失时的处理方式。",
        tags=["FBA", "库存"],
        reason_code="schema_invalid",
        reason_cn="模型分类不在合法集合内。",
        raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )

    corrected = _apply_screening_guardrails(invalid, raw_document, source)

    assert corrected.screen_status == "accepted"
    assert corrected.screen_bucket == "related"
    assert corrected.category == "fba_logistics"
    assert corrected.reason_code == "seller_ops_signal"


def test_default_strategy_uses_channel_config_selected_threshold(tmp_path):
    SessionLocal = _session_factory(tmp_path)

    with SessionLocal() as session:
        ai_strategy = _ensure_active_strategy(session, "ai")
        amazon_strategy = _ensure_active_strategy(session, "amazon")

    assert ai_strategy.thresholds_json["selected"] == 75
    assert amazon_strategy.thresholds_json["selected"] == 72


def test_pipeline_once_produces_public_event_and_isolates_failed_source(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        _add_source(session, "broken_feed", "https://example.com/broken.xml", tier="T2")
        session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/openai.xml":
            return httpx.Response(
                200,
                text=_rss(
                    "OpenAI launches GPT-5",
                    "https://example.com/gpt-5",
                    "Important model release details.",
                ),
                headers={"content-type": "application/rss+xml"},
            )
        return httpx.Response(500, text="failed")

    stats = run_pipeline_once(
        SessionLocal,
        worker_id="worker-a",
        limit=10,
        now=now,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        llm_provider=_stable_llm_provider(),
        screening_provider=_stable_screening_provider(),
    )

    with SessionLocal() as session:
        jobs = session.scalars(select(FetchJobRecord).order_by(FetchJobRecord.source_id)).all()
        broken_state = session.get(SourceStateRecord, "broken_feed")
        raw_count = len(session.scalars(select(RawDocumentRecord)).all())
        item_count = len(session.scalars(select(NormalizedItemRecord)).all())
        score_count = len(session.scalars(select(ModelScoreRecord)).all())
        rank_count = len(session.scalars(select(RankedItemRecord)).all())
        cluster = session.scalar(select(EventClusterRecord))
        member_count = len(session.scalars(select(ClusterMemberRecord)).all())

    assert stats.scheduled == 2
    assert stats.claimed == 2
    assert stats.succeeded == 1
    assert stats.failed == 1
    assert {job.source_id: job.status for job in jobs}["openai_feed"] == "succeeded"
    assert {job.source_id: job.status for job in jobs}["broken_feed"] == "pending"
    assert broken_state is not None
    assert broken_state.error_streak == 1
    assert raw_count == 1
    assert item_count == 1
    assert score_count == 1
    assert rank_count == 1
    assert cluster is not None
    assert cluster.canonical_title == "OpenAI 发布 GPT-5"
    assert member_count == 1


def test_worker_marks_adapter_exception_failed_without_stopping_other_jobs(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        _add_source(session, "timeout_feed", "https://example.com/timeout.xml", tier="T2")
        session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.com/timeout.xml":
            raise httpx.ConnectTimeout("timeout")
        return httpx.Response(
            200,
            text=_rss("OpenAI launches GPT-5", "https://example.com/gpt-5", "Important model release details."),
            headers={"content-type": "application/rss+xml"},
        )

    stats = run_pipeline_once(
        SessionLocal,
        worker_id="worker-a",
        limit=10,
        now=now,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        llm_provider=_stable_llm_provider(),
        screening_provider=_stable_screening_provider(),
    )

    with SessionLocal() as session:
        jobs = session.scalars(select(FetchJobRecord)).all()
        cluster_count = len(session.scalars(select(EventClusterRecord)).all())

    assert stats.succeeded == 1
    assert stats.failed == 1
    assert {job.source_id: job.status for job in jobs}["timeout_feed"] == "pending"
    assert cluster_count == 1


def test_worker_marks_processing_exception_failed_and_continues(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "first_feed", "https://example.com/first.xml")
        _add_source(session, "second_feed", "https://example.com/second.xml")
        session.add(FetchJobRecord(source_id="first_feed", status="pending", priority=10, run_after=now))
        session.add(FetchJobRecord(source_id="second_feed", status="pending", priority=20, run_after=now))
        session.commit()

    class CrashingProvider:
        def score_item(self, payload):
            raise RuntimeError("model crash")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_rss("OpenAI launches GPT-5", str(request.url).replace(".xml", "/gpt-5"), "Important model release."),
            headers={"content-type": "application/rss+xml"},
        )

    stats = run_worker_once(
        SessionLocal,
        worker_id="worker-a",
        limit=2,
        now=now,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        llm_provider=CrashingProvider(),
        screening_provider=_stable_screening_provider(),
    )

    with SessionLocal() as session:
        jobs = {job.source_id: job for job in session.scalars(select(FetchJobRecord)).all()}

    assert stats.claimed == 2
    assert stats.failed == 2
    assert jobs["first_feed"].status == "pending"
    assert jobs["second_feed"].status == "pending"
    assert jobs["first_feed"].last_error == "model crash"
    assert jobs["second_feed"].last_error == "model crash"


def test_worker_is_idempotent_for_duplicate_documents(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_rss("OpenAI launches GPT-5", "https://example.com/gpt-5", "Important model release details."),
            headers={"content-type": "application/rss+xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _stable_llm_provider()
    screening = _stable_screening_provider()
    first = run_pipeline_once(
        SessionLocal,
        worker_id="worker-a",
        limit=10,
        now=now,
        client=client,
        llm_provider=provider,
        screening_provider=screening,
    )
    with SessionLocal() as session:
        session.add(FetchJobRecord(source_id="openai_feed", status="pending", priority=10, run_after=now))
        session.commit()
    second = run_worker_once(
        SessionLocal,
        worker_id="worker-b",
        limit=10,
        now=now,
        client=client,
        llm_provider=provider,
        screening_provider=screening,
    )

    with SessionLocal() as session:
        raw_count = len(session.scalars(select(RawDocumentRecord)).all())
        item_count = len(session.scalars(select(NormalizedItemRecord)).all())
        cluster_count = len(session.scalars(select(EventClusterRecord)).all())

    assert first.raw_documents_inserted == 1
    assert second.raw_documents_inserted == 0
    assert raw_count == 1
    assert item_count == 1
    assert cluster_count == 1


def test_pipeline_uses_injected_llm_provider_for_model_scores(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_rss("OpenAI launches GPT-5", "https://example.com/gpt-5", "Important model release details."),
            headers={"content-type": "application/rss+xml"},
        )

    provider = FakeLLMProvider(
        ModelScore(
            category="ai_products",
            relevance_score=88,
            impact_score=84,
            novelty_score=76,
            actionability_score=65,
            credibility_score=90,
            confidence_score=86,
            summary_cn="外部 Provider 生成的摘要。",
            title_cn="外部 Provider 生成的标题",
            reason="外部 Provider 被流水线调用。",
            seller_action_level="review",
            tags=["产品更新", "模型能力"],
            event_type="product_update",
            key_facts=["外部 Provider 返回结构化结果"],
            risk_flags=[],
            raw_json={"provider": "deepseek", "model": "deepseek-chat"},
        )
    )
    run_pipeline_once(
        SessionLocal,
        worker_id="worker-a",
        limit=10,
        now=now,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        llm_provider=provider,
        screening_provider=_stable_screening_provider(),
    )

    with SessionLocal() as session:
        score = session.scalar(select(ModelScoreRecord))
        item = session.scalar(select(NormalizedItemRecord))

    assert score is not None
    assert score.category == "ai_products"
    assert score.model == "deepseek-chat"
    assert score.raw_json["provider"] == "deepseek"
    assert item is not None
    assert item.title_cn == "外部 Provider 生成的标题"
    assert item.summary_cn == "外部 Provider 生成的摘要。"


def test_reprocess_existing_items_updates_ai_processed_fields(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        source = session.get(SourceRecord, "openai_feed")
        assert source is not None
        run = FetchRunRecord(
            source_id="openai_feed",
            status="succeeded",
            started_at=now,
            finished_at=now,
            http_status=200,
            content_type="text/html",
            bytes_received=128,
            item_count=1,
            metadata_json={},
        )
        session.add(run)
        session.flush()
        raw = RawDocumentRecord(
            fetch_run_id=run.id,
            source_id="openai_feed",
            url="https://example.com/gpt-5",
            canonical_url="https://example.com/gpt-5",
            content_type="text/html",
            body_text="Very long original English content.",
            body_html="<article>Very long original English content.</article>",
            response_headers_json={},
            content_hash="raw-existing",
            fetched_at=now,
        )
        session.add(raw)
        session.flush()
        item = NormalizedItemRecord(
            channel="ai",
            source_id="openai_feed",
            raw_document_id=raw.id,
            title_original="OpenAI launches GPT-5",
            title_cn=None,
            url="https://example.com/gpt-5",
            canonical_url="https://example.com/gpt-5",
            summary_original="Very long original English content.",
            summary_cn=None,
            published_at=now,
            fetched_at=now,
            language="en",
            content_hash="item-existing",
        )
        session.add(item)
        session.commit()

    provider = FakeLLMProvider(
        ModelScore(
            category="ai_models",
            relevance_score=91,
            impact_score=88,
            novelty_score=84,
            actionability_score=70,
            credibility_score=95,
            confidence_score=87,
            summary_cn="AI 处理后的中文摘要。",
            title_cn="AI 处理后的中文标题",
            reason="AI 处理后的推荐理由。",
            seller_action_level="review",
            tags=["模型发布", "官方动态"],
            event_type="model_release",
            key_facts=["AI 处理字段被更新"],
            risk_flags=[],
            raw_json={"provider": "deepseek", "model": "deepseek-v4-flash"},
        )
    )

    stats = reprocess_existing_items(SessionLocal, channel="ai", limit=1, llm_provider=provider)

    with SessionLocal() as session:
        item = session.scalar(select(NormalizedItemRecord))
        score = session.scalar(select(ModelScoreRecord))

    assert stats.items == 1
    assert stats.failed == 0
    assert item is not None
    assert item.title_cn == "AI 处理后的中文标题"
    assert item.summary_cn == "AI 处理后的中文摘要。"
    assert score is not None
    assert score.reason == "AI 处理后的推荐理由。"


def test_model_payload_truncates_long_original_text(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        source = session.get(SourceRecord, "openai_feed")
        assert source is not None
        item = NormalizedItemRecord(
            channel="ai",
            source_id="openai_feed",
            raw_document_id=1,
            title_original="T" * 400,
            title_cn=None,
            url="https://example.com/gpt-5",
            canonical_url="https://example.com/gpt-5",
            summary_original="S" * 5000,
            summary_cn=None,
            published_at=now,
            fetched_at=now,
            language="en",
            content_hash="item-long",
        )

        payload = _model_payload(item, source)

    assert len(str(payload["titleOriginal"])) == 301
    assert len(str(payload["summaryOriginal"])) == 4001
    assert str(payload["summaryOriginal"]).endswith("…")


def test_normalize_raw_document_skips_non_beijing_today_item(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        source = session.get(SourceRecord, "openai_feed")
        assert source is not None
        run = FetchRunRecord(
            source_id="openai_feed",
            status="succeeded",
            started_at=now,
            finished_at=now,
            http_status=200,
            content_type="application/rss+xml",
            bytes_received=128,
            item_count=1,
            metadata_json={},
        )
        session.add(run)
        session.flush()
        raw = RawDocumentRecord(
            fetch_run_id=run.id,
            source_id="openai_feed",
            url="https://example.com/gpt-5",
            canonical_url="https://example.com/gpt-5",
            content_type="application/rss+xml",
            body_text="Old summary.",
            body_html="<p>Old summary.</p>",
            response_headers_json={
                "x-intel-title": "Old item",
                "x-intel-published-at": "2026-05-10T18:00:00+00:00",
            },
            content_hash="old-raw",
            fetched_at=now,
        )
        session.add(raw)
        session.flush()

        item = _normalize_raw_document(session, source, raw)

    assert item is None


def test_fake_score_does_not_persist_raw_original_summary(tmp_path):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as session:
        _add_source(session, "openai_feed", "https://example.com/openai.xml")
        source = session.get(SourceRecord, "openai_feed")
        assert source is not None
        item = NormalizedItemRecord(
            channel="ai",
            source_id="openai_feed",
            raw_document_id=1,
            title_original="OpenAI launches GPT-5",
            title_cn=None,
            url="https://example.com/gpt-5",
            canonical_url="https://example.com/gpt-5",
            summary_original="Important model release details in raw English.",
            summary_cn=None,
            published_at=now,
            fetched_at=now,
            language="en",
            content_hash="item-fallback",
        )

        score = _fake_score(item, source)

    assert score.summary_cn == "待 AI 处理后生成中文摘要。"
    assert score.summary_cn != "Important model release details in raw English."
