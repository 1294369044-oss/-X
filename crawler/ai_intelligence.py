#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AI 情报采集、评分与同事件合并。

只读取公开 RSS、Atom、JSON API；Anthropic 因没有公开 RSS，使用其公开
Newsroom HTML。任何来源失败都只返回一条统计错误，不影响其他来源。
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime


USER_AGENT = "YanLanNewsBot/0.3 (+https://news.yanlanyunxiu01.com/)"
TIMEOUT = 20
MAX_AGE_DAYS = 14
ITEMS_PER_SOURCE = 8

SOURCE_LEVEL_ORDER = {"official": 4, "reliable": 3, "rumor": 2, "community": 1}

CLICKBAIT_TERMS = (
    "震惊", "炸锅", "彻底凉了", "完蛋了", "疯了", "怒了", "崩了", "史诗级",
    "杀疯了", "逆天", "全球震动", "重磅突发", "大地震", "必须看", "千万别",
    "网友吵翻", "全网沸腾",
)
MODEL_RELEASE_TERMS = (
    "introducing", "launches", "launched", "releases", "released", "new model",
    "模型发布", "发布模型", "正式发布",
)
PRODUCT_UPDATE_TERMS = (
    "now available", "new feature", "product update", "更新", "上线", "推出", "可用",
)
API_RULE_TERMS = (
    "api", "pricing", "price", "rate limit", "usage policy", "terms of use",
    "定价", "价格", "使用规则", "速率限制", "上下文窗口",
)
OUTAGE_TERMS = (
    "outage", "service disruption", "incident", "unavailable", "服务故障", "宕机", "中断",
)
OPINION_TERMS = ("opinion", "commentary", "what i think", "观点", "评论", "随笔")
RUMOR_TERMS = ("rumor", "unconfirmed", "传闻", "未经证实")

COMPANY_ALIASES = {
    "OpenAI": ("openai", "chatgpt", "gpt-", "gpt ", "sora"),
    "Claude": ("anthropic", "claude"),
    "Gemini": ("google deepmind", "deepmind", "gemini", "gemma"),
    "DeepSeek": ("deepseek", "深度求索"),
    "Qwen": ("qwen", "通义千问", "千问"),
    "xAI": ("xai", "x.ai", "grok"),
}

FEED_SOURCES = (
    {
        "name": "OpenAI 官方博客",
        "url": "https://openai.com/news/rss.xml",
        "company": "OpenAI",
        "source_level": "official",
    },
    {
        "name": "Google AI 官方博客",
        "url": "https://blog.google/technology/ai/rss/",
        "company": "Gemini",
        "source_level": "official",
    },
    {
        "name": "Google DeepMind 官方博客",
        "url": "https://deepmind.google/blog/rss.xml",
        "company": "Gemini",
        "source_level": "official",
    },
    {
        "name": "OpenAI GitHub Releases",
        "url": "https://github.com/openai/openai-python/releases.atom",
        "company": "OpenAI",
        "source_level": "official",
    },
    {
        "name": "Anthropic GitHub Releases",
        "url": "https://github.com/anthropics/anthropic-sdk-python/releases.atom",
        "company": "Claude",
        "source_level": "official",
    },
    {
        "name": "Gemini GitHub Releases",
        "url": "https://github.com/googleapis/python-genai/releases.atom",
        "company": "Gemini",
        "source_level": "official",
    },
)

MEDIA_FEEDS = (
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "source_level": "reliable",
    },
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "source_level": "reliable",
    },
)


def _fetch(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _clean_text(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    parsed = None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] in names:
            return "".join(child.itertext()).strip()
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        href = child.attrib.get("href", "").strip()
        if href and child.attrib.get("rel", "alternate") in ("", "alternate"):
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def _make_item(
    title: str,
    url: str,
    source: str,
    source_level: str,
    company: str,
    published: datetime,
    summary: str,
    collector: str,
    collected_at: datetime,
) -> dict:
    return {
        "title": _clean_text(title),
        "url": url.strip(),
        "source": _clean_text(source),
        "source_level": source_level,
        "category": "ai",
        "company": company,
        "published_at": published.isoformat(),
        "summary": _clean_text(summary) or "暂无摘要，请前往原始来源查看完整内容。",
        "importance": 0,
        "collected_at": collected_at.isoformat(),
        "related_sources": [],
        "_collector": collector,
    }


def parse_feed(payload: bytes, source: dict, collected_at: datetime) -> list[dict]:
    root = ET.fromstring(payload)
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in ("item", "entry")]
    items = []
    for node in entries:
        title = _child_text(node, ("title",))
        link = _entry_link(node)
        summary = _child_text(node, ("description", "summary", "content"))
        published = _parse_date(_child_text(node, ("pubDate", "published", "updated", "date")))
        combined = f"{title} {summary}"
        company = source.get("company") or detect_company(combined)
        if not title or not link or not published or not company:
            continue
        source_level = source["source_level"]
        if source_level == "reliable" and any(term in combined.casefold() for term in RUMOR_TERMS):
            source_level = "rumor"
        items.append(_make_item(
            title, link, source["name"], source_level, company,
            published, summary, source["name"], collected_at,
        ))
        if len(items) >= ITEMS_PER_SOURCE:
            break
    return items


def collect_feed(source: dict, collected_at: datetime) -> list[dict]:
    payload = _fetch(source["url"], "application/rss+xml, application/atom+xml, application/xml, text/xml")
    return parse_feed(payload, source, collected_at)


def collect_huggingface(author: str, company: str, collected_at: datetime) -> list[dict]:
    query = urllib.parse.urlencode({
        "author": author,
        "sort": "lastModified",
        "direction": "-1",
        "limit": ITEMS_PER_SOURCE,
    })
    payload = json.loads(_fetch(
        "https://huggingface.co/api/models?" + query,
        "application/json",
    ))
    items = []
    for model in payload if isinstance(payload, list) else []:
        model_id = str(model.get("id") or "").strip()
        published = _parse_date(model.get("lastModified"))
        if not model_id or not published:
            continue
        summary_bits = ["官方 Hugging Face 模型页更新"]
        if model.get("pipeline_tag"):
            summary_bits.append(str(model["pipeline_tag"]))
        if isinstance(model.get("downloads"), int):
            summary_bits.append(f"近月下载 {model['downloads']:,}")
        source_name = f"{company} Hugging Face 官方账号"
        items.append(_make_item(
            f"{model_id} 模型更新",
            "https://huggingface.co/" + urllib.parse.quote(model_id, safe="/"),
            source_name,
            "official",
            company,
            published,
            " · ".join(summary_bits),
            source_name,
            collected_at,
        ))
    return items


def collect_anthropic_news(collected_at: datetime) -> list[dict]:
    page = _fetch("https://www.anthropic.com/news", "text/html,application/xhtml+xml").decode("utf-8", errors="replace")
    anchor_pattern = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    items = []
    for href, body in anchor_pattern.findall(page):
        if not (href.startswith("/news/") or href.startswith("/claude-")):
            continue
        heading = re.search(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", body, re.I | re.S)
        date_match = re.search(r"<time\b[^>]*>(.*?)</time>", body, re.I | re.S)
        summary_match = re.search(r"<p\b[^>]*>(.*?)</p>", body, re.I | re.S)
        title = _clean_text(heading.group(1)) if heading else ""
        published = _parse_date(_clean_text(date_match.group(1))) if date_match else None
        if not title or not published:
            continue
        summary = _clean_text(summary_match.group(1)) if summary_match else "Anthropic 官方 Newsroom 更新。"
        items.append(_make_item(
            title,
            urllib.parse.urljoin("https://www.anthropic.com", href),
            "Anthropic Newsroom",
            "official",
            "Claude",
            published,
            summary,
            "Anthropic Newsroom",
            collected_at,
        ))
        if len(items) >= ITEMS_PER_SOURCE:
            break
    if not items:
        raise RuntimeError("公开 Newsroom 页面未解析到新闻条目")
    return items


def detect_company(text: str) -> str:
    lowered = text.casefold()
    for company, aliases in COMPANY_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return company
    return ""


def calculate_importance(item: dict) -> int:
    text = f"{item.get('title', '')} {item.get('summary', '')}".casefold()
    source_level = item.get("source_level", "community")
    score = 30 + {"official": 30, "reliable": 18, "rumor": 0, "community": -5}.get(source_level, -5)
    if any(term in text for term in MODEL_RELEASE_TERMS):
        score += 30
    if any(term in text for term in PRODUCT_UPDATE_TERMS):
        score += 20
    if any(term in text for term in API_RULE_TERMS):
        score += 20
    if any(term in text for term in OUTAGE_TERMS):
        score += 20
    if any(term in text for term in CLICKBAIT_TERMS):
        score -= 15
    if not item.get("source"):
        score -= 20
    if any(term in text for term in OPINION_TERMS):
        score -= 20
    return max(0, min(100, score))


def _canonical_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    kept_query = urllib.parse.urlencode([
        (key, val) for key, val in urllib.parse.parse_qsl(parsed.query)
        if not key.casefold().startswith("utm_") and key.casefold() not in {"ref", "source", "stream"}
    ])
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.casefold(), path, kept_query, ""))


def _normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def _title_terms(value: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "that", "this", "new", "official", "update", "模型", "发布", "更新"}
    return {
        term for term in re.findall(r"[a-z0-9][a-z0-9._-]{1,}|[\u4e00-\u9fff]{2,8}", value.casefold())
        if term not in stop
    }


def _model_keys(value: str) -> set[str]:
    patterns = (
        r"gpt[- ]?\d+(?:\.\d+)?", r"claude[- ]?[a-z]+[- ]?\d+(?:\.\d+)?",
        r"gemini[- ]?\d+(?:\.\d+)?", r"deepseek[- ]?[a-z0-9.]+",
        r"qwen[- ]?\d+(?:\.\d+)?", r"grok[- ]?\d+(?:\.\d+)?",
    )
    lowered = value.casefold()
    return {match.replace(" ", "-") for pattern in patterns for match in re.findall(pattern, lowered)}


def _same_event(left: dict, right: dict) -> bool:
    if _canonical_url(left["url"]) == _canonical_url(right["url"]):
        return True
    if left.get("company") != right.get("company"):
        return False
    left_time = _parse_date(left.get("published_at"))
    right_time = _parse_date(right.get("published_at"))
    if not left_time or not right_time or abs(left_time - right_time) > timedelta(days=3):
        return False
    left_title = _normalized_title(left.get("title", ""))
    right_title = _normalized_title(right.get("title", ""))
    if SequenceMatcher(None, left_title, right_title).ratio() >= 0.72:
        return True
    left_models = _model_keys(left.get("title", ""))
    right_models = _model_keys(right.get("title", ""))
    if left_models & right_models:
        return True
    left_terms = _title_terms(left.get("title", ""))
    right_terms = _title_terms(right.get("title", ""))
    union = left_terms | right_terms
    return bool(union) and len(left_terms & right_terms) / len(union) >= 0.45


def _valid_item(item: dict, collected_at: datetime) -> bool:
    published = _parse_date(item.get("published_at"))
    return bool(
        item.get("title")
        and _canonical_url(item.get("url", ""))
        and published
        and collected_at - timedelta(days=MAX_AGE_DAYS) <= published <= collected_at + timedelta(days=1)
    )


def collect_ai_intelligence() -> tuple[list[dict], list[dict], list[str]]:
    collected_at = datetime.now(timezone.utc)
    stats: list[dict] = []
    errors: list[str] = []
    candidates: list[dict] = []

    def run_source(name: str, collector) -> None:
        stat = {"source": name, "fetched": 0, "added": 0, "duplicates": 0, "filtered": 0, "error": ""}
        stats.append(stat)
        try:
            items = collector()
            stat["fetched"] = len(items)
            for item in items:
                item["_collector"] = name
                if not _valid_item(item, collected_at):
                    stat["filtered"] += 1
                    continue
                item["importance"] = calculate_importance(item)
                candidates.append(item)
        except Exception as error:
            stat["error"] = f"{type(error).__name__}: {error}"
            errors.append(f"{name}: {stat['error']}")

    for source in FEED_SOURCES:
        run_source(source["name"], lambda source=source: collect_feed(source, collected_at))
    run_source("Anthropic Newsroom", lambda: collect_anthropic_news(collected_at))
    run_source("DeepSeek Hugging Face", lambda: collect_huggingface("deepseek-ai", "DeepSeek", collected_at))
    run_source("Qwen Hugging Face", lambda: collect_huggingface("Qwen", "Qwen", collected_at))
    for source in MEDIA_FEEDS:
        run_source(source["name"], lambda source=source: collect_feed(source, collected_at))

    # xAI 没有公开 RSS/API，News 页对服务器访问触发 Cloudflare 拦截；不绕过。
    xai_stat = {
        "source": "xAI News",
        "fetched": 0,
        "added": 0,
        "duplicates": 0,
        "filtered": 0,
        "error": "无公开 RSS/API，News 页阻止服务器访问，第一阶段按规则跳过",
    }
    stats.append(xai_stat)
    errors.append(f"xAI News: {xai_stat['error']}")

    stats_by_source = {stat["source"]: stat for stat in stats}
    candidates.sort(
        key=lambda item: (
            SOURCE_LEVEL_ORDER.get(item.get("source_level", "community"), 0),
            item.get("importance", 0),
            _parse_date(item.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    kept: list[dict] = []
    for candidate in candidates:
        duplicate = next((item for item in kept if _same_event(item, candidate)), None)
        collector = candidate.get("_collector", "")
        if duplicate:
            candidate["importance"] = max(0, candidate["importance"] - 30)
            duplicate["related_sources"].append({
                "title": candidate["title"],
                "url": candidate["url"],
                "source": candidate["source"],
                "source_level": candidate["source_level"],
                "published_at": candidate["published_at"],
            })
            stats_by_source[collector]["duplicates"] += 1
            continue
        stats_by_source[collector]["added"] += 1
        kept.append(candidate)

    kept.sort(key=lambda item: _parse_date(item["published_at"]), reverse=True)
    for item in kept:
        item.pop("_collector", None)
    return kept, stats, errors


def format_source_stats(stats: list[dict]) -> list[str]:
    lines = []
    for stat in stats:
        line = (
            f"{stat['source']}: 抓取 {stat['fetched']} | 新增 {stat['added']} | "
            f"重复 {stat['duplicates']} | 过滤 {stat['filtered']}"
        )
        if stat.get("error"):
            line += f" | 错误 {stat['error']}"
        lines.append(line)
    return lines
