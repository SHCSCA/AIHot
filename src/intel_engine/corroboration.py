from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Literal, Sequence


VerificationStatus = Literal[
    "single_source", "corroborated", "conflicted", "insufficient"
]

TIER_EVIDENCE_WEIGHT = {
    "T1": 1.0,
    "T1.5": 0.9,
    "T2": 0.7,
    "T3": 0.5,
}
AUTHORITATIVE_TIERS = {"T1", "T1.5"}
CONFLICT_FLAG_TERMS = (
    "conflict",
    "contradict",
    "disputed",
    "inconsistent",
    "冲突",
    "矛盾",
    "不一致",
    "存在争议",
)
ENGLISH_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|denies|denied|false)\b", re.IGNORECASE
)
CHINESE_NEGATION_TERMS = ("并非", "不是", "不会", "没有", "尚未", "未", "不")
KEY_VALUE_RE = re.compile(r"^\s*([^:=：]{1,80})\s*[:=：]\s*(.+?)\s*$")
TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


@dataclass(frozen=True)
class CorroborationMember:
    publisher_key: str
    source_tier: str
    title: str
    source_id: str | None = None
    summary: str = ""
    key_facts: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.publisher_key.strip():
            raise ValueError("publisher_key must not be empty")
        if self.source_tier not in TIER_EVIDENCE_WEIGHT:
            raise ValueError(f"unsupported source tier: {self.source_tier}")


@dataclass(frozen=True)
class CorroborationResult:
    verification_status: VerificationStatus
    independent_source_count: int
    authoritative_source_count: int
    evidence_score: float
    supported_claims: tuple[SupportedClaim, ...]
    supported_facts: tuple[str, ...]
    conflicting_claims: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class SupportedClaim:
    claim: str
    publisher_keys: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class _PublisherEvidence:
    publisher_key: str
    source_tier: str
    risk_flags: tuple[str, ...]


@dataclass
class _MutablePublisherEvidence:
    display_key: str
    source_tier: str
    risk_flags: list[str]


@dataclass(frozen=True)
class _Claim:
    publisher_key: str
    source_id: str | None
    text: str
    normalized: str
    base: str
    negated: bool
    key: str | None
    value: str | None


def corroborate_event(members: Sequence[CorroborationMember]) -> CorroborationResult:
    """Cross-check event evidence without network or model dependencies."""
    publishers = _merge_publishers(members)
    independent_count = len(publishers)
    authoritative_count = sum(
        publisher.source_tier in AUTHORITATIVE_TIERS for publisher in publishers
    )
    claims = _build_claims(members)
    conflict_flags = _explicit_conflict_flags(publishers)
    conflicting_claims = _find_conflicts(claims, conflict_flags)
    supported_claims = _find_supported_claims(claims)
    supported_facts = tuple(claim.claim for claim in supported_claims)
    risk_count = len(
        {
            _normalize_text(flag)
            for publisher in publishers
            for flag in publisher.risk_flags
            if _normalize_text(flag)
        }
    )

    if conflicting_claims:
        status: VerificationStatus = "conflicted"
    elif not claims:
        status = "insufficient"
    elif independent_count < 2:
        status = "single_source"
    elif supported_facts:
        status = "corroborated"
    else:
        status = "insufficient"

    score = _evidence_score(
        publishers=publishers,
        supported_facts=supported_facts,
        risk_count=risk_count,
        status=status,
    )
    return CorroborationResult(
        verification_status=status,
        independent_source_count=independent_count,
        authoritative_source_count=authoritative_count,
        evidence_score=score,
        supported_claims=supported_claims,
        supported_facts=supported_facts,
        conflicting_claims=conflicting_claims,
        summary=_summary(
            status=status,
            independent_count=independent_count,
            authoritative_count=authoritative_count,
            supported_count=len(supported_facts),
            conflict_count=len(conflicting_claims),
        ),
    )


def _merge_publishers(
    members: Sequence[CorroborationMember],
) -> tuple[_PublisherEvidence, ...]:
    grouped: dict[str, _MutablePublisherEvidence] = {}
    for member in members:
        publisher_key = _normalize_publisher_key(member.publisher_key)
        group = grouped.setdefault(
            publisher_key,
            _MutablePublisherEvidence(
                display_key=member.publisher_key.strip(),
                source_tier=member.source_tier,
                risk_flags=[],
            ),
        )
        if (
            TIER_EVIDENCE_WEIGHT[member.source_tier]
            > TIER_EVIDENCE_WEIGHT[group.source_tier]
        ):
            group.source_tier = member.source_tier

        group.risk_flags.extend(_unique_nonempty(member.risk_flags))

    return tuple(
        _PublisherEvidence(
            publisher_key=group.display_key,
            source_tier=group.source_tier,
            risk_flags=_unique_nonempty(group.risk_flags),
        )
        for _, group in sorted(grouped.items())
    )


def _build_claims(members: Sequence[CorroborationMember]) -> tuple[_Claim, ...]:
    claims: list[_Claim] = []
    for member in members:
        explicit_facts = _unique_nonempty(member.key_facts)
        member_claims = explicit_facts or _unique_nonempty(
            (member.title, member.summary)
        )
        for text in member_claims:
            normalized = _normalize_text(text)
            if not normalized:
                continue
            key, value = _key_value_parts(text)
            base, negated = _negation_signature(text)
            claims.append(
                _Claim(
                    publisher_key=member.publisher_key.strip(),
                    source_id=member.source_id,
                    text=text,
                    normalized=normalized,
                    base=base,
                    negated=negated,
                    key=key,
                    value=value,
                )
            )
    return tuple(claims)


def _find_supported_claims(claims: Sequence[_Claim]) -> tuple[SupportedClaim, ...]:
    groups: list[list[_Claim]] = []
    for claim in claims:
        matching = next(
            (
                group
                for group in groups
                if group[0].negated == claim.negated
                and _claims_equivalent(group[0], claim)
            ),
            None,
        )
        if matching is None:
            groups.append([claim])
        else:
            matching.append(claim)

    supported: list[SupportedClaim] = []
    seen: set[str] = set()
    for group in groups:
        publisher_keys_list: list[str] = []
        normalized_publishers: set[str] = set()
        for claim in group:
            normalized_publisher = _normalize_publisher_key(claim.publisher_key)
            if (
                not normalized_publisher
                or normalized_publisher in normalized_publishers
            ):
                continue
            normalized_publishers.add(normalized_publisher)
            publisher_keys_list.append(claim.publisher_key.strip())
        publisher_keys = tuple(publisher_keys_list)
        normalized_claim = _normalize_text(group[0].text)
        if len(normalized_publishers) < 2 or normalized_claim in seen:
            continue
        seen.add(normalized_claim)
        supported.append(
            SupportedClaim(
                claim=group[0].text,
                publisher_keys=publisher_keys,
                source_ids=tuple(
                    dict.fromkeys(
                        claim.source_id
                        for claim in group
                        if claim.source_id is not None
                    )
                ),
            )
        )
    return tuple(supported)


def _find_conflicts(
    claims: Sequence[_Claim],
    conflict_flags: Sequence[str],
) -> tuple[str, ...]:
    conflicts = list(conflict_flags)
    for index, first in enumerate(claims):
        for second in claims[index + 1 :]:
            if _normalize_publisher_key(
                first.publisher_key
            ) == _normalize_publisher_key(second.publisher_key):
                continue
            if _negation_conflict(first, second) or _key_value_conflict(first, second):
                conflicts.append(f"{first.text} <> {second.text}")
    return _unique_nonempty(conflicts)


def _negation_conflict(first: _Claim, second: _Claim) -> bool:
    return (
        first.negated != second.negated
        and bool(first.base)
        and _claims_match(first.base, second.base)
    )


def _key_value_conflict(first: _Claim, second: _Claim) -> bool:
    return (
        first.key is not None
        and first.key == second.key
        and first.value is not None
        and second.value is not None
        and first.value != second.value
    )


def _claims_equivalent(first: _Claim, second: _Claim) -> bool:
    if first.key is not None or second.key is not None:
        return (
            first.key is not None
            and first.key == second.key
            and first.value is not None
            and first.value == second.value
        )
    return _claims_match(first.normalized, second.normalized)


def _explicit_conflict_flags(
    publishers: Sequence[_PublisherEvidence],
) -> tuple[str, ...]:
    return _unique_nonempty(
        flag
        for publisher in publishers
        for flag in publisher.risk_flags
        if any(term in flag.casefold() for term in CONFLICT_FLAG_TERMS)
    )


def _evidence_score(
    *,
    publishers: Sequence[_PublisherEvidence],
    supported_facts: Sequence[str],
    risk_count: int,
    status: VerificationStatus,
) -> float:
    source_score = min(
        45.0,
        sum(TIER_EVIDENCE_WEIGHT[publisher.source_tier] for publisher in publishers)
        * 22.5,
    )
    authoritative_count = sum(
        publisher.source_tier in AUTHORITATIVE_TIERS for publisher in publishers
    )
    authority_score = min(20.0, authoritative_count * 10.0)
    agreement_score = min(25.0, len(supported_facts) * 12.5)
    score = (
        source_score + authority_score + agreement_score - min(15.0, risk_count * 3.0)
    )

    if status == "single_source":
        score = min(score, 49.0)
    elif status == "insufficient":
        score = min(score, 39.0)
    elif status == "conflicted":
        score = min(score - 30.0, 44.0)
    return round(max(0.0, min(100.0, score)), 2)


def _summary(
    *,
    status: VerificationStatus,
    independent_count: int,
    authoritative_count: int,
    supported_count: int,
    conflict_count: int,
) -> str:
    if status == "corroborated":
        return (
            f"{independent_count} 个独立发布方相互印证，"
            f"其中 {authoritative_count} 个为权威信源，确认 {supported_count} 条共同事实。"
        )
    if status == "conflicted":
        return (
            f"{independent_count} 个独立发布方的证据中发现 "
            f"{conflict_count} 处明确冲突，需要人工复核。"
        )
    if status == "single_source":
        return "仅有 1 个独立发布方，尚不能完成交叉验证。"
    if independent_count == 0:
        return "没有可用于交叉验证的事件成员。"
    return f"{independent_count} 个独立发布方尚未形成可确认的共同事实。"


def _key_value_parts(text: str) -> tuple[str | None, str | None]:
    match = KEY_VALUE_RE.match(text)
    if match is None:
        return None, None
    key = _normalize_text(match.group(1))
    value = _normalize_text(match.group(2))
    return (key or None), (value or None)


def _negation_signature(text: str) -> tuple[str, bool]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    negated = bool(ENGLISH_NEGATION_RE.search(normalized))
    normalized = ENGLISH_NEGATION_RE.sub(" ", normalized)
    for term in CHINESE_NEGATION_TERMS:
        if term in normalized:
            negated = True
            normalized = normalized.replace(term, "")
    return _normalize_text(normalized), negated


def _claims_match(first: str, second: str) -> bool:
    if first == second:
        return True
    if not first or not second:
        return False
    return SequenceMatcher(a=first, b=second).ratio() >= 0.9


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(TOKEN_RE.findall(normalized))


def _normalize_publisher_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _unique_nonempty(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        normalized = _normalize_text(text)
        if text and normalized not in seen:
            seen.add(normalized)
            result.append(text)
    return tuple(result)
