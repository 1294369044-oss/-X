# 澜讯（新闻网 X）

中文静态新闻聚合前端，使用 Astro 构建，兼容 Cloudflare Pages。

AI 情报栏目位于 `/ai/`，复用现有 JSON、静态构建和发布流程，不需要数据库或 AI API。

## 本地运行

```cmd
pnpm install
pnpm dev
```

## 构建

```cmd
pnpm build
```

Cloudflare Pages 配置：

- 生产分支：`main`
- 构建命令：`pnpm build`
- 输出目录：`dist`
- Node.js：`22.12.0` 或更高版本
- `SITE_URL`：`https://news.yanlanyunxiu01.com`

## 接入爬虫数据

设置构建环境变量 `NEWS_DATA_URL`，指向可公开读取的 JSON 数组。字段格式见 `src/data/news.ts` 中的 `NewsItem`。

如果远程数据不可用或格式验证失败，构建会明确警告并回退到标有“演示数据”的本地内容，避免发布不完整数据。
