from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Sequence

import httpx

from intel_engine.channel_config import CHANNELS_DIR
from intel_engine.db import (
    create_engine_from_settings,
    init_schema_for_sqlite,
    sessionmaker_for_engine,
)
from intel_engine.jobs import crawl_enabled_sources
from intel_engine.pipeline import (
    backfill_event_evidence,
    reprocess_existing_items,
    run_pipeline_once,
    run_scheduler_once,
    run_worker_once,
)
from intel_engine.settings import Settings
from intel_engine.source_seed import seed_sources_from_channel_configs
from intel_engine.storage import (
    DEFAULT_DB_PATH,
    ItemRepository,
    create_engine_for_path,
    init_db,
)


def build_crawl_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行公开信源抓取并写入 SQLite。")
    parser.add_argument(
        "--channels-dir", type=Path, default=CHANNELS_DIR, help="频道配置目录。"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite 数据库路径。"
    )
    parser.add_argument(
        "--channel", choices=["ai", "amazon"], default=None, help="只抓取指定频道。"
    )
    return parser


def run_crawl_command(
    argv: Sequence[str] | None = None, client: httpx.Client | None = None
) -> int:
    parser = build_crawl_parser()
    args = parser.parse_args(argv)

    engine = create_engine_for_path(args.db)
    init_db(engine)
    repository = ItemRepository(engine)
    stats = crawl_enabled_sources(
        repository,
        channels_dir=args.channels_dir,
        channel_id=args.channel,
        client=client,
    )

    print(
        "抓取完成："
        f"频道 {stats.channels} 个，"
        f"信源 {stats.sources} 个，"
        f"抓取条目 {stats.fetched} 条，"
        f"新增 {stats.inserted} 条，"
        f"重复 {stats.duplicates} 条，"
        f"错误 {len(stats.errors)} 个。"
    )
    for error in stats.errors:
        print(f"错误：频道={error.channel} 信源={error.source_id} 原因={error.message}")

    return 1 if stats.errors else 0


def run_seed_sources_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入生产信源 seed。")
    parser.add_argument(
        "--channels-dir", type=Path, default=CHANNELS_DIR, help="频道配置目录。"
    )
    args = parser.parse_args(argv)

    SessionLocal = _production_sessionmaker()
    with SessionLocal() as session:
        stats = seed_sources_from_channel_configs(session, args.channels_dir)
        session.commit()

    print(
        f"信源导入完成：新增 {stats.created} 个，更新 {stats.updated} 个，总数 {stats.total} 个。"
    )
    return 0


def run_schedule_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="根据 source_states 生成生产抓取任务。"
    )
    parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    parser.add_argument("--limit", type=int, default=None, help="最多调度多少个信源。")
    args = parser.parse_args(argv)

    stats = run_scheduler_once(
        _production_sessionmaker(), now=_parse_now(args.now), limit=args.limit
    )
    print(f"调度完成：新增任务 {stats.scheduled} 个。")
    return 0


def run_worker_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="领取并处理生产抓取任务。")
    parser.add_argument("--worker-id", default="local-worker", help="worker 标识。")
    parser.add_argument("--limit", type=int, default=10, help="最多领取多少个任务。")
    parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    args = parser.parse_args(argv)

    stats = run_worker_once(
        _production_sessionmaker(),
        worker_id=args.worker_id,
        limit=args.limit,
        now=_parse_now(args.now),
    )
    print(
        "Worker 完成："
        f"领取 {stats.claimed} 个，成功 {stats.succeeded} 个，失败 {stats.failed} 个，"
        f"新增 raw {stats.raw_documents_inserted} 个，新增 normalized {stats.normalized_items} 个，"
        f"新增 cluster {stats.clusters} 个。"
    )
    return 0 if stats.failed == 0 else 1


def run_pipeline_once_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="执行一次生产调度和 worker 闭环。")
    parser.add_argument("--worker-id", default="local-worker", help="worker 标识。")
    parser.add_argument("--limit", type=int, default=10, help="最多处理多少个任务。")
    parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    args = parser.parse_args(argv)

    stats = run_pipeline_once(
        _production_sessionmaker(),
        worker_id=args.worker_id,
        limit=args.limit,
        now=_parse_now(args.now),
    )
    print(
        "流水线完成："
        f"调度 {stats.scheduled} 个，领取 {stats.claimed} 个，成功 {stats.succeeded} 个，失败 {stats.failed} 个，"
        f"新增 raw {stats.raw_documents_inserted} 个，新增 normalized {stats.normalized_items} 个，"
        f"新增 cluster {stats.clusters} 个。"
    )
    return 0 if stats.failed == 0 else 1


def run_reprocess_items_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="用当前 LLM Provider 重处理已有条目的中文标题、摘要和推荐理由。"
    )
    parser.add_argument(
        "--channel", choices=["ai", "amazon"], default=None, help="只处理指定频道。"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="最多处理多少个已有条目。"
    )
    args = parser.parse_args(argv)

    stats = reprocess_existing_items(
        _production_sessionmaker(), channel=args.channel, limit=args.limit
    )
    print(f"重处理完成：成功 {stats.items} 个，失败 {stats.failed} 个。")
    return 0 if stats.failed == 0 else 1


def run_evidence_backfill_command(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为已有事件回填可追溯的交叉验证证据。")
    parser.add_argument(
        "--channel",
        choices=["ai", "amazon"],
        default=None,
        help="只处理指定频道。",
    )
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少个事件。")
    parser.add_argument(
        "--with-ai",
        action="store_true",
        help="额外调用事件分析模型；默认只运行确定性证据规则。",
    )
    args = parser.parse_args(argv)

    stats = backfill_event_evidence(
        _production_sessionmaker(),
        channel=args.channel,
        limit=args.limit,
        use_ai=args.with_ai,
    )
    print(f"证据回填完成：处理 {stats.events} 个事件。")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="情报引擎命令行工具。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser(
        "crawl", description="抓取公开信源并写入 SQLite。"
    )
    crawl_parser.add_argument(
        "--channels-dir", type=Path, default=CHANNELS_DIR, help="频道配置目录。"
    )
    crawl_parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite 数据库路径。"
    )
    crawl_parser.add_argument(
        "--channel", choices=["ai", "amazon"], default=None, help="只抓取指定频道。"
    )
    seed_parser = subparsers.add_parser(
        "seed-sources", description="导入生产信源 seed。"
    )
    seed_parser.add_argument(
        "--channels-dir", type=Path, default=CHANNELS_DIR, help="频道配置目录。"
    )
    schedule_parser = subparsers.add_parser(
        "schedule", description="生成生产抓取任务。"
    )
    schedule_parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    schedule_parser.add_argument(
        "--limit", type=int, default=None, help="最多调度多少个信源。"
    )
    worker_parser = subparsers.add_parser("worker", description="处理生产抓取任务。")
    worker_parser.add_argument(
        "--worker-id", default="local-worker", help="worker 标识。"
    )
    worker_parser.add_argument(
        "--limit", type=int, default=10, help="最多领取多少个任务。"
    )
    worker_parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    pipeline_parser = subparsers.add_parser(
        "pipeline-once", description="执行一次生产调度和 worker 闭环。"
    )
    pipeline_parser.add_argument(
        "--worker-id", default="local-worker", help="worker 标识。"
    )
    pipeline_parser.add_argument(
        "--limit", type=int, default=10, help="最多处理多少个任务。"
    )
    pipeline_parser.add_argument(
        "--now", default=None, help="ISO 8601 时间；默认当前 UTC 时间。"
    )
    reprocess_parser = subparsers.add_parser(
        "reprocess-items", description="用当前 LLM Provider 重处理已有条目。"
    )
    reprocess_parser.add_argument(
        "--channel", choices=["ai", "amazon"], default=None, help="只处理指定频道。"
    )
    reprocess_parser.add_argument(
        "--limit", type=int, default=10, help="最多处理多少个已有条目。"
    )
    evidence_parser = subparsers.add_parser(
        "backfill-evidence",
        description="为已有事件回填交叉验证证据。",
    )
    evidence_parser.add_argument(
        "--channel",
        choices=["ai", "amazon"],
        default=None,
        help="只处理指定频道。",
    )
    evidence_parser.add_argument(
        "--limit", type=int, default=None, help="最多处理多少个事件。"
    )
    evidence_parser.add_argument(
        "--with-ai",
        action="store_true",
        help="额外调用事件分析模型。",
    )

    args = parser.parse_args(argv)
    if args.command == "crawl":
        crawl_args: list[str] = [
            "--channels-dir",
            str(args.channels_dir),
            "--db",
            str(args.db),
        ]
        if args.channel:
            crawl_args.extend(["--channel", args.channel])
        return run_crawl_command(crawl_args)
    if args.command == "seed-sources":
        return run_seed_sources_command(["--channels-dir", str(args.channels_dir)])
    if args.command == "schedule":
        schedule_args = []
        if args.now:
            schedule_args.extend(["--now", args.now])
        if args.limit is not None:
            schedule_args.extend(["--limit", str(args.limit)])
        return run_schedule_command(schedule_args)
    if args.command == "worker":
        worker_args = ["--worker-id", args.worker_id, "--limit", str(args.limit)]
        if args.now:
            worker_args.extend(["--now", args.now])
        return run_worker_command(worker_args)
    if args.command == "pipeline-once":
        pipeline_args = ["--worker-id", args.worker_id, "--limit", str(args.limit)]
        if args.now:
            pipeline_args.extend(["--now", args.now])
        return run_pipeline_once_command(pipeline_args)
    if args.command == "reprocess-items":
        reprocess_args = ["--limit", str(args.limit)]
        if args.channel:
            reprocess_args.extend(["--channel", args.channel])
        return run_reprocess_items_command(reprocess_args)
    if args.command == "backfill-evidence":
        evidence_args = []
        if args.channel:
            evidence_args.extend(["--channel", args.channel])
        if args.limit is not None:
            evidence_args.extend(["--limit", str(args.limit)])
        if args.with_ai:
            evidence_args.append("--with-ai")
        return run_evidence_backfill_command(evidence_args)
    raise SystemExit(f"未知命令：{args.command}")


def _production_sessionmaker():
    engine = create_engine_from_settings(Settings())
    init_schema_for_sqlite(engine)
    return sessionmaker_for_engine(engine)


def _parse_now(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
