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
  return text || fallback;
}

function convert(items, category, requireRecent) {
  return (Array.isArray(items) ? items : []).flatMap(item => {
    const url = originalUrl(item.url);
    const published = new Date(item.published);
    if (!url || url.protocol !== "https:" || !item.title) return [];
    if (url.pathname === "/" && !url.search) return [];
    if (!Number.isFinite(published.getTime())) return [];
    if (requireRecent && published.getTime() < recentCutoff) return [];

    const summary = cleanText(item.description);
    return [{
      slug: `feed-${createHash("sha256").update(url.href).digest("hex").slice(0, 16)}`,
      title: cleanText(item.title, "未命名信息"),
      summary,
      content: [summary],
      category,
      source: sourceName(url, item.source),
      sourceUrl: url.href,
      publishedAt: published.toISOString(),
    }];
  });
}

const china = convert(raw.china, "要闻", true);
const games = convert(raw.games, "游戏", true);
const github = convert(raw.github, "科技", false);
const items = [...china, ...games, ...github]
  .sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));

if (items.length === 0) throw new Error("过滤后没有可发布内容");
const featured = items.find(item => item.category === "要闻") ?? items[0];
featured.featured = true;

await writeFile(outputPath, `${JSON.stringify({ generatedAt: generatedAt.toISOString(), items }, null, 2)}\n`, "utf8");
console.log(`已生成 ${items.length} 条：要闻 ${china.length}，游戏 ${games.length}，科技 ${github.length}`);
