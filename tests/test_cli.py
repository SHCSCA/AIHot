import httpx

from intel_engine.cli import run_crawl_command
from intel_engine.storage import ItemRepository, create_engine_for_path, init_db
from tests.test_jobs import write_channel_config


def test_crawl_command_writes_items_and_returns_zero(tmp_path, capsys):
    channels_dir = tmp_path / "channels"
    write_channel_config(channels_dir)
    db_path = tmp_path / "intel.sqlite3"

    rss = """<rss version="2.0"><channel><item><title>AI 动态</title><link>https://example.com/ai</link><description>摘要</description></item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    exit_code = run_crawl_command(
        [
            "--channels-dir",
            str(channels_dir),
            "--db",
            str(db_path),
            "--channel",
            "ai",
        ],
        client=client,
    )

    engine = create_engine_for_path(db_path)
    init_db(engine)
    repo = ItemRepository(engine)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "抓取完成" in output
    assert len(repo.list_items(channel="ai")) == 1
