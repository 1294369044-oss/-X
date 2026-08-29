# VPS 新闻聚合器

`news_digest.py` 使用 Python 标准库低频读取公开来源，输出：

- `output/news.json`：供网站的 `scripts/import-crawler-data.mjs` 转换；
- `output/index.html`：用于在 VPS 上直接检查采集结果。

当前平台来源：

- B站公开热门视频榜；
- Steam 全球热销榜前五名游戏的最新 Steam 新闻；

脚本不使用账号 Cookie，不破解请求签名，也不绕过验证码或访问控制。NodeSeek 官方 RSS 只有“社区最新”而非热度排序；小红书探索页也不等同于热榜；抖音、X、小黑盒目前无法从公开 HTML 稳定取得榜单，因此这些来源没有接入生产。

在 VPS 中运行：

```bash
python3 news_digest.py
```

在网站仓库中导入：

```bash
node scripts/import-crawler-data.mjs /path/to/news.json
```
