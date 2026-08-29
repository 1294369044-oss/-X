import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const inputPath = process.argv[2];
if (!inputPath) {
  throw new Error("用法：node scripts/import-crawler-data.mjs <news.json>");
}

const projectRoot = path.resolve(import.meta.dirname, "..");
const outputPath = path.join(projectRoot, "src", "data", "generated-news.json");
const raw = JSON.parse(await readFile(path.resolve(inputPath), "utf8"));
const generatedAt = new Date(raw.generated_at);
if (!Number.isFinite(generatedAt.getTime())) throw new Error("generated_at 无效");

const recentCutoff = generatedAt.getTime() - 14 * 24 * 60 * 60 * 1000;

function originalUrl(value) {
  try {
    const url = new URL(value);
    if (url.hostname.endsWith("bing.com")) {
      const target = url.searchParams.get("url");
      if (target) return new URL(target);
    }
    return url;
  } catch {
    return null;
  }
}

function sourceName(url, fallback) {
  if (fallback && fallback !== "Bing News") return fallback;
  return url.hostname.replace(/^www\./, "");
}

function cleanText(value, fallback = "暂无摘要，请前往原始来源查看完整内容。") {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text && !/^[-—–]+$/.test(text) ? text : fallback;
}

const legacyClassification = {
  china: { section: "时事要闻", category: "国内要闻" },
  games: { section: "游戏娱乐", category: "游戏新闻" },
  github: { section: "科技网络", category: "GitHub开源" },
  bilibili: { section: "游戏娱乐", category: "B站热门" },
  steam: { section: "游戏娱乐", category: "Steam" },
  nodeseek: { section: "科技网络", category: "VPS与网络" },
  xiaoheihe: { section: "游戏娱乐", category: "游戏平台" },
  douyin: { section: "时事要闻", category: "网络热榜" },
};

const legacyNameClassification = {
  要闻: { section: "时事要闻", category: "国内要闻" },
  国际: { section: "时事要闻", category: "国际动态" },
  科技: { section: "科技网络", category: "AI与科技" },
  游戏: { section: "游戏娱乐", category: "游戏新闻" },
  视频: { section: "游戏娱乐", category: "B站热门" },
  财经: { section: "时事要闻", category: "财经产业" },
  文化: { section: "时事要闻", category: "社会文化" },
  生活: { section: "时事要闻", category: "社会文化" },
};

function convert(items, fallbackClassification, requireRecent) {
  return (Array.isArray(items) ? items : []).flatMap(item => {
    const url = originalUrl(item.url);
    const published = new Date(item.published);
    if (!url || url.protocol !== "https:" || !item.title) return [];
    if (url.pathname === "/" && !url.search) return [];
    if (!Number.isFinite(published.getTime())) return [];
    if (requireRecent && published.getTime() < recentCutoff) return [];

    const section = item.section || fallbackClassification.section;
    const category = item.category || fallbackClassification.category;
    if (!section || !category) return [];

    const summary = cleanText(item.description);
    return [{
      slug: `feed-${createHash("sha256").update(url.href).digest("hex").slice(0, 16)}`,
      title: cleanText(item.title, "未命名信息"),
      summary,
      content: [summary],
      section,
      category,
      source: sourceName(url, item.source),
      sourceUrl: url.href,
      publishedAt: published.toISOString(),
    }];
  });
}

function migrateExistingItem(item) {
  if (!item || typeof item !== "object") return null;
  const value = item;
  const fallback = legacyNameClassification[value.category];
  const section = value.section || fallback?.section;
  const category = value.section ? value.category : fallback?.category;
  if (!section || !category || typeof value.slug !== "string" || typeof value.sourceUrl !== "string") return null;
  const published = new Date(value.publishedAt);
  if (!Number.isFinite(published.getTime())) return null;
  const summary = cleanText(value.summary);
  return {
    slug: value.slug,
    title: cleanText(value.title, "未命名信息"),
    summary,
    content: Array.isArray(value.content) && value.content.length ? value.content.map(part => cleanText(part)) : [summary],
    section,
    category,
    source: cleanText(value.source, "未知来源"),
    sourceUrl: value.sourceUrl,
    publishedAt: published.toISOString(),
    ...(value.featured ? { featured: true } : {}),
  };
}

const china = convert(raw.china, legacyClassification.china, true);
const games = convert(raw.games, legacyClassification.games, true);
const steam = convert(raw.steam, legacyClassification.steam, true);
const bilibili = convert(raw.bilibili, legacyClassification.bilibili, true);
const nodeseek = convert(raw.nodeseek, legacyClassification.nodeseek, true);
const xiaoheihe = convert(raw.xiaoheihe, legacyClassification.xiaoheihe, true);
const douyin = convert(raw.douyin, legacyClassification.douyin, true);
const github = convert(raw.github, legacyClassification.github, false);
const freshItems = [...china, ...games, ...steam, ...bilibili, ...nodeseek, ...xiaoheihe, ...douyin, ...github]
  .sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));

let previousItems = [];
try {
  const previous = JSON.parse(await readFile(outputPath, "utf8"));
  previousItems = Array.isArray(previous.items) ? previous.items.map(migrateExistingItem).filter(Boolean) : [];
} catch {
  // 首次导入时没有历史生成文件，直接使用本次抓取结果。
}
const freshSlugs = new Set(freshItems.map(item => item.slug));
const retainedItems = previousItems.filter(item => !freshSlugs.has(item.slug));
const items = [...freshItems, ...retainedItems]
  .sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));

if (items.length === 0) throw new Error("过滤后没有可发布内容");
for (const item of items) delete item.featured;
const featured = items.find(item => item.section === "时事要闻" && item.category === "国内要闻") ?? items[0];
featured.featured = true;

await writeFile(outputPath, `${JSON.stringify({ generatedAt: generatedAt.toISOString(), items }, null, 2)}\n`, "utf8");
console.log(
  `已生成 ${items.length} 条：要闻 ${china.length}，游戏资讯 ${games.length}，` +
  `Steam ${steam.length}，B站 ${bilibili.length}，小黑盒 ${xiaoheihe.length}，抖音 ${douyin.length}，` +
  `NodeSeek精选 ${nodeseek.length}，科技 ${github.length}`
);
