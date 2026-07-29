from __future__ import annotations

from intel_engine.corroboration import CorroborationMember, corroborate_event


def _member(**overrides) -> CorroborationMember:
    data = {
        "publisher_key": "openai",
        "source_tier": "T1",
        "title": "OpenAI launches GPT-5",
        "summary": "OpenAI announced the GPT-5 model.",
        "key_facts": ("OpenAI launched GPT-5",),
        "risk_flags": (),
    }
    data.update(overrides)
    return CorroborationMember(**data)


def test_single_source_cannot_be_corroborated():
    result = corroborate_event([_member()])

    assert result.verification_status == "single_source"
    assert result.independent_source_count == 1
    assert result.authoritative_source_count == 1
    assert result.supported_facts == ()
    assert 0 <= result.evidence_score < 50


def test_multiple_endpoints_from_same_publisher_count_once():
    result = corroborate_event(
        [
            _member(title="OpenAI News: GPT-5", publisher_key="OpenAI"),
            _member(
                title="GPT-5 release notes",
                publisher_key=" openai ",
                source_tier="T2",
            ),
        ]
    )

    assert result.verification_status == "single_source"
    assert result.independent_source_count == 1
    assert result.authoritative_source_count == 1


def test_two_independent_publishers_corroborate_shared_fact():
    result = corroborate_event(
        [
            _member(
                publisher_key="openai",
                source_tier="T2",
                source_id="openai-news",
            ),
            _member(
                publisher_key="reuters",
                source_tier="T2",
                source_id="reuters-ai",
            ),
        ]
    )

    assert result.verification_status == "corroborated"
    assert result.independent_source_count == 2
    assert result.authoritative_source_count == 0
    assert result.supported_facts == ("OpenAI launched GPT-5",)
    assert result.supported_claims[0].publisher_keys == ("openai", "reuters")
    assert result.supported_claims[0].source_ids == ("openai-news", "reuters-ai")
    assert result.conflicting_claims == ()


def test_supported_claim_only_lists_endpoints_that_contain_the_fact():
    result = corroborate_event(
        [
            _member(
                publisher_key="publisher-a",
                source_id="a1",
                key_facts=("price: 99",),
            ),
            _member(
                publisher_key="publisher-a",
                source_id="a2",
                key_facts=("availability: us",),
            ),
            _member(
                publisher_key="publisher-b",
                source_id="b1",
                key_facts=("price: 99",),
            ),
        ]
    )

    assert result.supported_claims[0].source_ids == ("a1", "b1")


def test_authoritative_sources_increase_evidence_score():
    low_authority = corroborate_event(
        [
            _member(publisher_key="publisher-a", source_tier="T3"),
            _member(publisher_key="publisher-b", source_tier="T3"),
        ]
    )
    high_authority = corroborate_event(
        [
            _member(publisher_key="official", source_tier="T1"),
            _member(publisher_key="wire-service", source_tier="T1.5"),
        ]
    )

    assert high_authority.verification_status == "corroborated"
    assert high_authority.authoritative_source_count == 2
    assert high_authority.evidence_score > low_authority.evidence_score


def test_title_is_deterministic_fallback_when_ai_facts_are_missing():
    result = corroborate_event(
        [
            _member(
                publisher_key="official",
                key_facts=(),
                summary="",
            ),
            _member(
                publisher_key="wire-service",
                source_tier="T2",
                key_facts=(),
                summary="",
            ),
        ]
    )

    assert result.verification_status == "corroborated"
    assert result.supported_facts == ("OpenAI launches GPT-5",)


def test_explicit_fact_conflict_downgrades_result():
    result = corroborate_event(
        [
            _member(
                publisher_key="official",
                source_tier="T1",
                key_facts=("release_date: 2026-08-01",),
            ),
            _member(
                publisher_key="media",
                source_tier="T2",
                key_facts=("release_date: 2026-09-01",),
            ),
        ]
    )

    assert result.verification_status == "conflicted"
    assert result.independent_source_count == 2
    assert result.authoritative_source_count == 1
    assert result.supported_facts == ()
    assert len(result.conflicting_claims) == 1
    assert set(result.conflicting_claims[0].split(" <> ")) == {
        "release_date: 2026-08-01",
        "release_date: 2026-09-01",
    }
    assert result.evidence_score < 50
