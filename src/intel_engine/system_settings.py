from __future__ import annotations

from sqlalchemy.orm import Session

from intel_engine.models import SystemSettingsRecord, utc_now


GLOBAL_SYSTEM_SETTINGS_ID = "global"
DEFAULT_AI_ANALYSIS_ENABLED = True


def get_system_settings(
    session: Session, *, create: bool = False
) -> SystemSettingsRecord | None:
    record = session.get(SystemSettingsRecord, GLOBAL_SYSTEM_SETTINGS_ID)
    if record is None and create:
        record = SystemSettingsRecord(
            id=GLOBAL_SYSTEM_SETTINGS_ID,
            ai_analysis_enabled=DEFAULT_AI_ANALYSIS_ENABLED,
            updated_at=utc_now(),
        )
        session.add(record)
        session.flush()
    return record


def ensure_system_settings(session: Session) -> SystemSettingsRecord:
    record = get_system_settings(session, create=True)
    assert record is not None
    return record


def is_ai_analysis_enabled(session: Session) -> bool:
    record = get_system_settings(session)
    if record is None:
        return DEFAULT_AI_ANALYSIS_ENABLED
    return bool(record.ai_analysis_enabled)
