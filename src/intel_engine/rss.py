from __future__ import annotations

from collections.abc import Iterable, Mapping
from xml.etree import ElementTree


def build_events_feed(
    events: Iterable[Mapping[str, object]],
    *,
    title: str,
    link: str,
    description: str,
) -> str:
    rss = ElementTree.Element("rss", version="2.0")
    channel = ElementTree.SubElement(rss, "channel")
    ElementTree.SubElement(channel, "title").text = title
    ElementTree.SubElement(channel, "link").text = link
    ElementTree.SubElement(channel, "description").text = description

    for event in events:
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "guid").text = str(event["id"])
        ElementTree.SubElement(item, "title").text = str(event["title"])
        ElementTree.SubElement(item, "link").text = str(event.get("url", ""))
        ElementTree.SubElement(item, "description").text = str(event.get("summary", ""))
        if event.get("publishedAt"):
            ElementTree.SubElement(item, "pubDate").text = str(event["publishedAt"])

    return ElementTree.tostring(rss, encoding="unicode")
