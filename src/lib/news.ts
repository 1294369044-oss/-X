import { demoNews, type NewsItem } from "../data/news";
import generatedNews from "../data/generated-news.json";

function isNewsItem(value: unknown): value is NewsItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return ["slug", "title", "summary", "category", "source", "sourceUrl", "publishedAt"].every(
    key => typeof item[key] === "string"
  ) && Array.isArray(item.content) && item.content.every(p => typeof p === "string");
}

const localGenerated = Array.isArray(generatedNews.items)
  ? generatedNews.items.filter(isNewsItem)
  : [];

export const hasGeneratedNews = localGenerated.length > 0;
export const generatedAt = generatedNews.generatedAt;

function newestFirst(items: NewsItem[]) {
  return [...items].sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));
}

export async function getNews(): Promise<NewsItem[]> {
  const url = import.meta.env.NEWS_DATA_URL;
  if (!url) return hasGeneratedNews ? newestFirst(localGenerated) : demoNews;

  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const value: unknown = await response.json();
    if (!Array.isArray(value) || !value.every(isNewsItem)) {
      throw new Error("新闻数据格式不正确");
    }
    return newestFirst(value);
  } catch (error) {
    console.warn("远程新闻数据读取失败，使用仓库内的已核验数据继续构建。", error);
    return hasGeneratedNews ? newestFirst(localGenerated) : demoNews;
  }
}
