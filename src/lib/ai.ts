import type { AICompany, NewsItem, SourceLevel } from "../data/news";

export const sourceLevelLabels: Record<SourceLevel, string> = {
  official: "官方",
  reliable: "高可信",
  rumor: "传闻",
  community: "社区",
};

export const aiCompanies: AICompany[] = ["OpenAI", "Claude", "Gemini", "DeepSeek", "Qwen", "xAI"];

export function isAIIntelligence(item: NewsItem): boolean {
  return item.category === "AI与科技" && Boolean(item.sourceLevel && item.company);
}

function shanghaiDay(value: string | Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).formatToParts(new Date(value));
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function aiIntelligence(items: NewsItem[]): NewsItem[] {
  return items
    .filter(isAIIntelligence)
    .sort((a, b) => (b.importance ?? 0) - (a.importance ?? 0) || Date.parse(b.publishedAt) - Date.parse(a.publishedAt));
}

export function homepageAIIntelligence(items: NewsItem[], generatedAt: string): NewsItem[] {
  if (!Number.isFinite(Date.parse(generatedAt))) return [];
  const today = shanghaiDay(generatedAt);
  return aiIntelligence(items)
    .filter(item => (item.importance ?? 0) >= 40 && shanghaiDay(item.publishedAt) === today)
    .slice(0, 8);
}
