export type NewsCategory = "要闻" | "国际" | "科技" | "游戏" | "视频" | "财经" | "文化" | "生活";

export interface NewsItem {
  slug: string;
  title: string;
  summary: string;
  content: string[];
  category: NewsCategory;
  source: string;
  sourceUrl: string;
  publishedAt: string;
  image?: string;
  featured?: boolean;
}

export const demoNews: NewsItem[] = [
  {
    slug: "demo-daily-briefing",
    title: "晨间新闻简报将在这里呈现重要信息",
    summary: "这是版面演示内容。接入爬虫数据后，这里会显示经过整理的最新要闻、来源和发布时间。",
    content: [
      "当前页面使用演示数据，用于验证新闻网站的视觉结构、分类、搜索和详情页。",
      "正式接入后，香港 VPS 上的爬虫会采集公开来源，并将标准化数据提供给网站构建流程。网站将保留原始来源名称与链接。",
    ],
    category: "要闻",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-29T08:30:00+08:00",
    featured: true,
  },
  {
    slug: "demo-global-observer",
    title: "全球观察栏目：用清晰脉络整理复杂事件",
    summary: "国际栏目将按时间、地区和来源梳理公开报道，帮助读者快速定位原文。",
    content: ["这里是国际新闻详情页的演示正文。正式内容将由数据接口在构建时生成。"],
    category: "国际",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-29T07:45:00+08:00",
  },
  {
    slug: "demo-ai-industry",
    title: "科技脉搏栏目：关注人工智能与开源生态",
    summary: "从产品发布到基础研究，用统一格式展示关键信息和可信来源。",
    content: ["这是科技新闻详情页的演示内容，不代表真实新闻报道。"],
    category: "科技",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-29T06:50:00+08:00",
  },
  {
    slug: "demo-market-window",
    title: "市场窗口栏目：重要数据一页读懂",
    summary: "财经信息将明确标注来源与时间，避免把过期数据当成当前行情。",
    content: ["这是财经新闻详情页的演示内容。本站不会把示例数字作为投资依据。"],
    category: "财经",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-28T21:20:00+08:00",
  },
  {
    slug: "demo-culture-reading",
    title: "文化现场栏目：记录阅读、创作与城市生活",
    summary: "文化版面将收录值得长期阅读的报道，而不只追逐短暂热度。",
    content: ["这是文化新闻详情页的演示内容。"],
    category: "文化",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-28T18:10:00+08:00",
  },
  {
    slug: "demo-practical-life",
    title: "生活指南栏目：把实用信息讲明白",
    summary: "天气、出行和公共服务信息会显示适用地区及更新时间。",
    content: ["这是生活新闻详情页的演示内容。"],
    category: "生活",
    source: "演示数据",
    sourceUrl: "https://example.com/",
    publishedAt: "2026-08-28T16:40:00+08:00",
  },
];
