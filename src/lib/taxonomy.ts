import type { NewsCategory, NewsSection } from "../data/news";

export interface CategoryDefinition {
  slug: string;
  name: NewsCategory;
}

export interface SectionDefinition {
  slug: string;
  name: NewsSection;
  description: string;
  categories: CategoryDefinition[];
}

export const sectionDefinitions: SectionDefinition[] = [
  {
    slug: "current",
    name: "时事要闻",
    description: "国内、国际与社会文化信息，按来源和时间整理。",
    categories: [
      { slug: "domestic", name: "国内要闻" },
      { slug: "international", name: "国际动态" },
      { slug: "finance", name: "财经产业" },
      { slug: "social", name: "社会文化" },
      { slug: "hot", name: "网络热榜" },
    ],
  },
  {
    slug: "tech",
    name: "科技网络",
    description: "人工智能、开源项目、服务器与开发工具。",
    categories: [
      { slug: "ai", name: "AI与科技" },
      { slug: "github", name: "GitHub开源" },
      { slug: "vps", name: "VPS与网络" },
      { slug: "dev", name: "开发软件" },
    ],
  },
  {
    slug: "game",
    name: "游戏娱乐",
    description: "游戏新闻、Steam 动态、B站热门和游戏平台资讯。",
    categories: [
      { slug: "game-news", name: "游戏新闻" },
      { slug: "steam", name: "Steam" },
      { slug: "bilibili", name: "B站热门" },
      { slug: "platform", name: "游戏平台" },
    ],
  },
];

export const categoryDefinitions = sectionDefinitions.flatMap(section =>
  section.categories.map(category => ({ ...category, section }))
);

export function sectionBySlug(slug: string) {
  return sectionDefinitions.find(section => section.slug === slug);
}

export function categoryBySlug(slug: string) {
  return categoryDefinitions.find(category => category.slug === slug);
}

export function categoryPath(category: NewsCategory) {
  const definition = categoryDefinitions.find(item => item.name === category);
  return definition ? `/category/${definition.slug}/` : "/news/";
}

export function sectionPath(section: NewsSection) {
  const definition = sectionDefinitions.find(item => item.name === section);
  return definition ? `/section/${definition.slug}/` : "/news/";
}

export const legacyCategoryMap: Record<string, string> = {
  要闻: "domestic",
  国际: "international",
  科技: "ai",
  游戏: "game-news",
  视频: "bilibili",
  财经: "finance",
  文化: "social",
  生活: "social",
};
