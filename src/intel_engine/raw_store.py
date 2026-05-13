from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intel_engine.fetchers import FetchResult
from intel_engine.models import FetchJobRecord, FetchRunRecord, RawDocumentRecord


@dataclass(frozen=True)
class RawStoreResult:
    fetch_run_id: int
    documents_inserted: int
    duplicates: int


class RawStore:
    def __init__(self, session: Session):
        self.session = session

    def save_fetch_result(self, job: FetchJobRecord, result: FetchResult, *, now: datetime) -> RawStoreResult:
        fetch_run = FetchRunRecord(
            job_id=job.id,
            source_id=job.source_id,
            status=result.status,
            started_at=now,
            finished_at=now,
            http_status=result.http_status,
            content_type=result.content_type,
            bytes_received=result.bytes_received,
            item_count=len(result.documents),
            error_message=result.error_message,
            metadata_json=result.metadata_json,
        )
        self.session.add(fetch_run)
        self.session.flush()

        inserted = 0
        duplicates = 0
        for document in result.documents:
            existing_id = self.session.scalar(
                select(RawDocumentRecord.id)
                .where(RawDocumentRecord.source_id == document.source_id)
                .where(RawDocumentRecord.content_hash == document.content_hash)
                .limit(1)
            )
            if existing_id is not None:
                duplicates += 1
                continue

            self.session.add(
                RawDocumentRecord(
                    fetch_run_id=fetch_run.id,
                    source_id=document.source_id,
                    url=document.url,
                    canonical_url=document.canonical_url,
                    content_type=document.content_type,
                    body_text=document.body_text,
                    body_html=document.body_html,
                    response_headers_json=document.response_headers_json,
                    content_hash=document.content_hash,
                    fetched_at=document.fetched_at,
                )
            )
            inserted += 1

        self.session.flush()
        return RawStoreResult(fetch_run_id=fetch_run.id, documents_inserted=inserted, duplicates=duplicates)
