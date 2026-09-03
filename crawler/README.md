# VPS 新闻聚合器

`news_digest.py` 使用 Python 标准库低频读取公开来源，输出：

- `output/news.json`：供网站的 `scripts/import-crawler-data.mjs` 转换；
- `output/index.html`：用于在 VPS 上直接检查采集结果。

当前平台来源：

- B站公开热门视频榜；
- Steam 全球热销榜前五名游戏的最新 Steam 新闻；
- NodeSeek 官方 RSS 中按 VPS、网络、AI 等关键词评分的内容精选；
- 小黑盒公开游戏新闻接口（无 Cookie，接口失败时跳过）；
- DailyHotApi 的抖音公开 JSON 热榜（配置 `DAILYHOT_API_URL`，接口失败时跳过）；

AI 情报来源：

- OpenAI 官方博客、Google AI 官方博客、Google DeepMind 官方博客：RSS；
- OpenAI、Anthropic、Gemini 的 Python SDK：GitHub Releases Atom；
- Anthropic Newsroom：公开 HTML（该站没有公开 RSS）；
- DeepSeek、Qwen：Hugging Face 官方账号 API；
- The Verge AI、TechCrunch AI：公开 RSS，标记为“高可信”；
- xAI：没有可用的公开 RSS/API，News 页阻止服务器访问，第一阶段不绕过访问控制；
- Reuters、Bloomberg、The Information：没有接入稳定免费的结构化来源，第一阶段暂缓。

AI 记录进入同一份 `output/news.json` 的 `ai` 数组，再由现有导入脚本合并进
`src/data/generated-news.json`。规则只使用本地代码：按 URL、标题相似度、公司、
三天时间窗口和模型版本关键词合并事件；同事件按官方、高可信、传闻、社区的顺序
保留主记录。标题党、来源不明、纯观点会降低重要度，不会因单个词直接删除。

脚本不使用账号 Cookie，不绕过验证码或访问控制。小黑盒接口只使用公开请求所需的时间戳/校验参数；如果接口返回版本过低、403、429 或结构变化，脚本会记录错误并继续其他来源。NodeSeek 页面明确标注为“最新帖子中的相关内容精选”，不是官方热榜。抖音只读取 DailyHotApi 的公开 JSON 路由，默认尝试公开镜像，也可通过 `DAILYHOT_API_URL` 指向自托管实例；镜像不可用时记录警告并跳过。小红书和 X 仍不接入生产，不使用登录 Cookie、浏览器自动化或验证绕过。AI 模块中的每个来源也独立失败，不会中断旧新闻采集、导入或构建。

在 VPS 中运行：

```bash
python3 news_digest.py
```

在网站仓库中导入：

```bash
node scripts/import-crawler-data.mjs /path/to/news.json
```
