import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: process.env.SITE_URL ?? "https://news.yanlanyunxiu01.com",
  output: "static",
  integrations: [sitemap()],
  i18n: {
    locales: ["zh-CN"],
    defaultLocale: "zh-CN",
    routing: { prefixDefaultLocale: false },
  },
});
