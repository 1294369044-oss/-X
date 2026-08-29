#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""每日公开信息源聚合器。

只访问无需登录、无需 Cookie、无需签名破解的公开页面或接口。
"""

import html
import hashlib
import json
import os
import re
import sys
import random
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_HTML = OUTPUT_DIR / "index.html"
OUTPUT_JSON = OUTPUT_DIR / "news.json"

USER_AGENT = "YanLanNewsBot/0.2 (+https://news.yanlanyunxiu01.com/)"
TIMEOUT = 20

LIMITS = {
    "github": 10,
    "games": 12,
    "china": 12,
    "bilibili": 10,
    "nodeseek": 8,
    "xiaoheihe": 8,
    "douyin": 10,
    "steam": 5,
}

BING_QUERIES = {
    "games": [
        "游戏 Steam Xbox PlayStation Nintendo",
        "使命召唤 COD 游戏",
    ],
    "china": [
        "中国 新闻",
        "中国 时事 新闻",
        "中国 经济 新闻",
    ],
}

NODESEEK_KEYWORDS = [
    "VPS", "服务器", "线路", "IP", "CN2", "GIA", "9929", "Docker", "Linux",
    "AI", "GPT", "Claude", "Gemini", "开源", "代理", "网络", "优惠", "补货",
]


def fetch(url: str, accept: str = "application/json, application/rss+xml, application/xml, text/html, */*") -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def utc_from_timestamp(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def parse_rss_date(text: str) -> datetime | None:
    if not text:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def parse_datetime_value(value) -> datetime | None:
    """Parse the timestamp variants used by public hot-list JSON endpoints."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # APIs occasionally return milliseconds instead of Unix seconds.
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return utc_from_timestamp(int(numeric))
    text = str(value).strip()
    parsed = utc_from_timestamp(text) if text.isdigit() else None
    if parsed:
        return parsed
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is None:
        return parse_rss_date(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def make_item(
    title: str,
    url: str,
    source: str,
    description: str,
    published: datetime | None,
    section: str,
    category: str,
) -> dict:
    return {
        "title": clean_text(title),
        "url": url.strip(),
        "source": clean_text(source),
        "section": section,
        "category": category,
        "description": clean_text(description),
        "published": published.isoformat() if published else "",
        "timestamp": int(published.timestamp()) if published else 0,
    }


def bing_news(query: str, section: str, category: str) -> list[dict]:
    params = {"q": query, "qft": 'sortbydate="1"', "format": "RSS"}
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(params)
    root = ET.fromstring(fetch(url))
    items = []
    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title", ""))
        link = (node.findtext("link", "") or "").strip()
        if not title or not link:
            continue
        source_node = node.find("source")
        source = clean_text(source_node.text) if source_node is not None and source_node.text else "Bing News"
        items.append(make_item(
            title,
            link,
            source,
            node.findtext("description", "") or "",
            parse_rss_date(node.findtext("pubDate", "") or ""),
            section,
            category,
        ))
    return items


def github_hot() -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    params = {
        "q": f"created:>={since} stars:>5",
        "sort": "stars",
        "order": "desc",
        "per_page": LIMITS["github"],
    }
    data = json.loads(fetch("https://api.github.com/search/repositories?" + urllib.parse.urlencode(params)))
    items = []
    for repo in data.get("items", []):
        published = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00")) if repo.get("created_at") else None
        language = repo.get("language") or "未标注语言"
        stars = repo.get("stargazers_count", 0)
        items.append(make_item(
            repo.get("full_name", ""),
            repo.get("html_url", ""),
            f"GitHub · ★ {stars:,} · {language}",
            repo.get("description") or "暂无简介",
            published,
            "科技网络",
            "GitHub开源",
        ))
    return items


def bilibili_popular() -> list[dict]:
    params = urllib.parse.urlencode({"ps": LIMITS["bilibili"], "pn": 1})
    data = json.loads(fetch("https://api.bilibili.com/x/web-interface/popular?" + params))
    if data.get("code") != 0:
        raise RuntimeError(f"B站接口返回 code={data.get('code')}")

    items = []
    for video in data.get("data", {}).get("list", []):
        bvid = video.get("bvid", "")
        title = video.get("title", "")
        if not bvid or not title:
            continue
        owner = clean_text(video.get("owner", {}).get("name", "未知 UP 主"))
        views = video.get("stat", {}).get("view", 0)
        items.append(make_item(
            title,
            f"https://www.bilibili.com/video/{urllib.parse.quote(bvid)}",
            f"哔哩哔哩热门 · {owner} · {views:,} 播放",
            video.get("desc") or "B站当前热门视频，请打开原页面查看完整内容。",
            utc_from_timestamp(video.get("pubdate")),
            "游戏娱乐",
            "B站热门",
        ))
    return items


def nodeseek_curated() -> list[dict]:
    """从 NodeSeek 官方最新 RSS 中筛选与 VPS/网络/AI 相关的帖子。

    RSS 本身按发布时间排序，不是热度榜；这里用透明的标题/摘要关键词分数做精选。
    """
    root = ET.fromstring(fetch("https://rss.nodeseek.com/"))
    candidates = []
    for node in root.findall("./channel/item"):
        title = clean_text(node.findtext("title", ""))
        link = clean_text(node.findtext("link", ""))
        description = clean_text(node.findtext("description", "") or "")
        if not title or not link or not link.startswith("https://www.nodeseek.com/"):
            continue
        title_lower = title.casefold()
        description_lower = description.casefold()
        score = sum(3 for keyword in NODESEEK_KEYWORDS if keyword.casefold() in title_lower)
        score += sum(1 for keyword in NODESEEK_KEYWORDS if keyword.casefold() in description_lower)
        if score <= 0:
            continue
        published = parse_rss_date(node.findtext("pubDate", "") or "")
        candidates.append((score, published.timestamp() if published else 0, make_item(
            title,
            link,
            "NodeSeek精选",
            ("来自 NodeSeek 最新公开帖子中的相关内容精选，不是官方热榜。 " +
             (description or "打开原帖查看完整内容。")),
            published,
            "科技网络",
            "VPS与网络",
        )))
    candidates.sort(key=lambda value: (value[0], value[1]), reverse=True)
    return [item for _, _, item in candidates[:LIMITS["nodeseek"]]]


# 小黑盒网页公开接口使用的轻量参数校验。这里不保存账号信息或 Cookie。
XHH_DICT = "JKMNPQRTX1234OABCDFG56789H"


def _xhh_md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _xhh_convert_byte(value: int) -> int:
    return (0xFF & ((value << 1) ^ 0x1B)) if value & 0x80 else value << 1


def _xhh_c0(value: int) -> int:
    return _xhh_c1(value) ^ _xhh_c2(value) ^ _xhh_c3(value)


def _xhh_c1(value: int) -> int:
    return _xhh_c2(_xhh_c3(_xhh_convert_byte(value)))


def _xhh_c2(value: int) -> int:
    return _xhh_c3(_xhh_convert_byte(value))


def _xhh_c3(value: int) -> int:
    return _xhh_convert_byte(value) ^ value


def _xhh_checksum(data: list[int]) -> int:
    values = [
        _xhh_c0(data[0]) ^ _xhh_c1(data[1]) ^ _xhh_c2(data[2]) ^ _xhh_c3(data[3]),
        _xhh_c3(data[0]) ^ _xhh_c0(data[1]) ^ _xhh_c1(data[2]) ^ _xhh_c2(data[3]),
        _xhh_c2(data[0]) ^ _xhh_c3(data[1]) ^ _xhh_c0(data[2]) ^ _xhh_c1(data[3]),
        _xhh_c1(data[0]) ^ _xhh_c2(data[1]) ^ _xhh_c3(data[2]) ^ _xhh_c0(data[3]),
    ]
    return sum(values) % 100


def _xhh_signed_url(url: str) -> str:
    timestamp = int(time.time())
    nonce = _xhh_md5(str(random.random())).upper()
    path = urllib.parse.urlsplit(url).path
    normalized_path = "/" + "/".join(part for part in path.split("/") if part) + "/"
    nonce_digits = re.sub(r"\D", "", nonce + XHH_DICT)
    nonce_hash = _xhh_md5(nonce_digits).lower()
    rnd_digits = re.sub(r"\D", "", _xhh_md5(f"{timestamp + 1}{normalized_path}{nonce_hash}"))
    counter = int(rnd_digits[:9].ljust(9, "0"))
    key = ""
    for _ in range(5):
        index = counter % len(XHH_DICT)
        counter //= len(XHH_DICT)
        key += XHH_DICT[index]
    suffix = str(_xhh_checksum([ord(char) for char in key[-4:]])).zfill(2)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}hkey={key}{suffix}&_time={timestamp}&nonce={nonce}"


def xiaoheihe_news() -> list[dict]:
    base_url = (
        "https://api.xiaoheihe.cn/bbs/app/feeds/news?os_type=web&app=heybox&"
        "client_type=mobile&version=999.0.3&x_client_type=web&x_os_type=Mac&"
        "x_app=heybox&heybox_id=-1&appid=900018355&offset=0&limit=20"
    )
    payload = json.loads(fetch(_xhh_signed_url(base_url)))
    result = payload.get("result") or {}
    links = result.get("links") or []
    if not isinstance(links, list):
        raise RuntimeError(f"小黑盒返回结构变化: links={type(links).__name__}")
    status = str(payload.get("status", "success"))
    if status not in {"success", "ok"} and not links:
        raise RuntimeError(f"小黑盒接口返回 {status}: {payload.get('msg', '无说明')}")

    items = []
    for link in links:
        link_id = link.get("linkid")
        title = clean_text(link.get("title", ""))
        if link_id is None or not title:
            continue
        published = utc_from_timestamp(link.get("modify_at") or link.get("publish_at"))
        items.append(make_item(
            title,
            f"https://api.xiaoheihe.cn/v3/bbs/app/api/web/share?link_id={urllib.parse.quote(str(link_id))}",
            "小黑盒",
            link.get("description") or "小黑盒游戏新闻，请打开原文查看完整内容。",
            published,
            "游戏娱乐",
            "游戏平台",
        ))
        if len(items) >= LIMITS["xiaoheihe"]:
            break
    return items


DOUYIN_API_DEFAULTS = [
    "https://api-hot.imsyy.top/douyin",
    "https://api-hot.lhzzs.top/douyin/",
    "https://api-hot.lhzzs.top/douyin/new",
]


def douyin_hot() -> list[dict]:
    """Read the public DailyHotApi Douyin JSON route when an instance is available.

    This deliberately does not call Douyin pages, use cookies, or automate a
    browser.  An operator can set DAILYHOT_API_URL to a self-hosted DailyHotApi
    endpoint; public mirrors are tried only as a convenience.
    """
    configured = os.environ.get("DAILYHOT_API_URL", "").strip()
    urls = [configured] if configured else DOUYIN_API_DEFAULTS
    failures = []
    for endpoint in urls:
        if not endpoint:
            continue
        try:
            payload = json.loads(fetch(endpoint))
            if isinstance(payload, list):
                rows = payload
                update_value = None
            elif isinstance(payload, dict):
                code = payload.get("code")
                if code not in (None, 0, 200, "0", "200") and not payload.get("data"):
                    raise RuntimeError(f"接口 code={code}: {payload.get('msg', '无说明')}")
                rows = payload.get("data")
                update_value = payload.get("updateTime") or payload.get("update_time") or payload.get("timestamp")
                if isinstance(rows, dict):
                    update_value = update_value or rows.get("updateTime") or rows.get("update_time")
                    rows = rows.get("data") or rows.get("list") or rows.get("items") or rows.get("result")
            else:
                raise RuntimeError(f"返回类型为 {type(payload).__name__}")
            if not isinstance(rows, list):
                raise RuntimeError(f"未找到 data/list 数组（{type(rows).__name__}）")

            fallback_time = parse_datetime_value(update_value)
            items = []
            for rank, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                title = clean_text(row.get("title") or row.get("word") or row.get("name") or "")
                if not title:
                    continue
                target = row.get("url") or row.get("mobileUrl") or row.get("mobile_url") or row.get("link")
                if not target:
                    target = "https://www.douyin.com/search/" + urllib.parse.quote(title, safe="")
                published = parse_datetime_value(
                    row.get("timestamp") or row.get("publish_time") or row.get("publishTime") or
                    row.get("updateTime") or row.get("update_time") or fallback_time
                )
                hot = row.get("hot") or row.get("hotValue") or row.get("heat") or row.get("score")
                description = row.get("desc") or row.get("description") or row.get("remark") or "抖音当前热榜话题，请打开原页面查看详情。"
                if hot not in (None, ""):
                    description = f"热度 {clean_text(str(hot))} · {description}"
                items.append(make_item(
                    title,
                    str(target),
                    "抖音热点",
                    f"抖音公开热榜第 {rank} 名。{description}",
                    published,
                    "时事要闻",
                    "网络热榜",
                ))
                if len(items) >= LIMITS["douyin"]:
                    break
            return items
        except Exception as error:
            failures.append(f"{endpoint}: {type(error).__name__}: {error}")
    raise RuntimeError("；".join(failures) or "未配置 DailyHotApi 地址")


def steam_top_appids(limit: int) -> list[str]:
    chart = fetch(
        "https://store.steampowered.com/charts/topselling/global?l=schinese",
        accept="text/html,application/xhtml+xml",
    ).decode("utf-8", errors="replace")
    appids = []
    seen = set()
    for appid in re.findall(r"https?://store\.steampowered\.com/app/(\d+)", chart, flags=re.I):
        if appid in seen:
            continue
        seen.add(appid)
        appids.append(appid)
        if len(appids) >= limit:
            break
    if not appids:
        raise RuntimeError("Steam 热销榜没有解析到 AppID")
    return appids


def steam_hot_news() -> tuple[list[dict], list[str]]:
    items = []
    errors = []
    for rank, appid in enumerate(steam_top_appids(LIMITS["steam"]), start=1):
        params = urllib.parse.urlencode({"appid": appid, "count": 1, "maxlength": 500})
        try:
            data = json.loads(fetch("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?" + params))
            news_items = data.get("appnews", {}).get("newsitems", [])
            if not news_items:
                continue
            news = news_items[0]
            published = utc_from_timestamp(news.get("date"))
            items.append(make_item(
                news.get("title", ""),
                news.get("url", ""),
                f"Steam 全球热销榜第 {rank} 名 · {clean_text(news.get('feedlabel', 'Steam 新闻'))}",
                news.get("contents") or "Steam 热销游戏的最新公开新闻，请打开原页面查看完整内容。",
                published,
                "游戏娱乐",
                "Steam",
            ))
        except Exception as error:
            errors.append(f"Steam App {appid}: {type(error).__name__}: {error}")
    return items, errors


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = re.sub(r"\W+", "", item.get("title", "").lower())[:100]
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def collect_category(
    queries: list[str],
    limit: int,
    section: str,
    category: str,
) -> tuple[list[dict], list[str]]:
    items = []
    errors = []
    for query in queries:
        try:
            items.extend(bing_news(query, section, category))
        except Exception as error:
            errors.append(f"{query}: {type(error).__name__}: {error}")
    items = dedupe(items)
    items.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
    return items[:limit], errors


def format_time(iso_text: str) -> str:
    if not iso_text:
        return ""
    try:
        parsed = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
        return parsed.astimezone(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
    except ValueError:
        return iso_text[:16].replace("T", " ")


def card(item: dict) -> str:
    title = html.escape(item.get("title", ""))
    url = html.escape(item.get("url", ""), quote=True)
    source = html.escape(item.get("source", ""))
    description = html.escape(item.get("description", ""))
    published = html.escape(format_time(item.get("published", "")))
    return (
        '<article class="card">'
        f'<a class="title" href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
        f'<div class="meta">{source}{" · " + published if published else ""}</div>'
        f'<div class="desc">{description}</div>'
        "</article>"
    )


def render(data: dict) -> str:
    labels = [
        ("bilibili", "📺 B站当前热门"),
        ("steam", "🎮 Steam 热销游戏新闻"),
        ("xiaoheihe", "🕹️ 小黑盒游戏新闻"),
        ("douyin", "📱 抖音热点"),
        ("nodeseek", "🖥️ NodeSeek 精选"),
        ("github", "🔥 GitHub 本周新热项目"),
        ("games", "🕹️ 游戏资讯"),
        ("china", "🇨🇳 国内重点信息"),
    ]
    sections = []
    for key, title in labels:
        body = "".join(card(item) for item in data.get(key, [])) or '<div class="empty">本次没有抓到内容</div>'
        sections.append(f'<section><h2>{title}</h2><div class="grid">{body}</div></section>')
    now_cn = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日要点</title><style>
:root{{color-scheme:dark;--bg:#0f1115;--panel:#171a21;--line:#2a2f3a;--text:#e8eaf0;--muted:#98a2b3;--link:#8ab4ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}
main{{width:min(1100px,calc(100% - 28px));margin:32px auto 80px}}h1{{margin:0 0 6px;font-size:30px}}.sub{{color:var(--muted);margin-bottom:28px}}
section{{margin:30px 0}}h2{{font-size:20px;margin:0 0 12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.card{{padding:15px 16px;border:1px solid var(--line);border-radius:12px;background:var(--panel);min-height:128px}}.title{{color:var(--text);text-decoration:none;font-weight:700;line-height:1.5}}.title:hover{{color:var(--link)}}
.meta{{color:var(--muted);font-size:12px;margin-top:8px}}.desc{{color:#c4c8d0;line-height:1.6;font-size:14px;margin-top:8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}.empty{{color:var(--muted);padding:16px;border:1px dashed var(--line);border-radius:12px}}
</style></head><body><main><h1>每日要点</h1><div class="sub">北京时间 {now_cn} · 公开来源低频抓取</div>{''.join(sections)}<p class="sub">不使用登录 Cookie 或签名破解；点击标题核对原文。</p></main></body></html>"""


def collect_optional(label: str, collector, errors: list[str]) -> list[dict]:
    try:
        return collector()
    except Exception as error:
        errors.append(f"{label}: {type(error).__name__}: {error}")
        return []


def main() -> None:
    errors = []
    github = collect_optional("GitHub", github_hot, errors)
    bilibili = collect_optional("Bilibili", bilibili_popular, errors)
    nodeseek = collect_optional("NodeSeek", nodeseek_curated, errors)
    xiaoheihe = collect_optional("小黑盒", xiaoheihe_news, errors)
    douyin = collect_optional("抖音 DailyHotApi", douyin_hot, errors)
    try:
        steam, steam_errors = steam_hot_news()
        errors.extend(steam_errors)
    except Exception as error:
        steam = []
        errors.append(f"Steam: {type(error).__name__}: {error}")

    games, game_errors = collect_category(BING_QUERIES["games"], LIMITS["games"], "游戏娱乐", "游戏新闻")
    china, china_errors = collect_category(BING_QUERIES["china"], LIMITS["china"], "时事要闻", "国内要闻")
    errors.extend(game_errors)
    errors.extend(china_errors)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "github": github,
        "games": games,
        "china": china,
        "bilibili": bilibili,
        "nodeseek": nodeseek,
        "xiaoheihe": xiaoheihe,
        "douyin": douyin,
        "steam": steam,
        "errors": errors,
    }
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_HTML.write_text(render(data), encoding="utf-8")

    print(f"完成：{OUTPUT_JSON}")
    print(
        f"B站 {len(bilibili)} | Steam {len(steam)} | 小黑盒 {len(xiaoheihe)} | 抖音 {len(douyin)} | "
        f"NodeSeek精选 {len(nodeseek)} | GitHub {len(github)} | 游戏 {len(games)} | 国内 {len(china)}"
    )
    if errors:
        print("部分来源发生错误：")
        for error in errors:
            print(" -", error)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
