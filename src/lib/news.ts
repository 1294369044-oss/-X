import { demoNews, type NewsItem } from "../data/news";

function isNewsItem(value: unknown): value is NewsItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return ["slug", "title", "summary", "category", "source", "sourceUrl", "publishedAt"].every(
    key => typeof item[key] === "string"
  ) && Array.isArray(item.content) && item.content.every(p => typeof p === "string");
}

export async function getNews(): Promise<NewsItem[]> {
  const url = import.meta.env.NEWS_DATA_URL;
  if (!url) return demoNews;

  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const value: unknown = await response.json();
    if (!Array.isArray(value) || !value.every(isNewsItem)) {
      throw new Error("新闻数据格式不正确");
    }
    return value.sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));
  } catch (error) {
    console.warn("远程新闻数据读取失败，使用演示数据继续构建。", error);
    return demoNews;
  }
}
