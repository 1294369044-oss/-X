#!/usr/bin/env bash
set -Eeuo pipefail

# Node3 定时发布入口：拉取站点仓库，采集公开信息，构建静态站点并仅在
# generated-news.json 发生实质变化时提交。密钥和 GitHub 主机指纹由服务器配置提供。

ENV_FILE="${LANXUN_ENV_FILE:-/opt/daily-news/automation/publish.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

BASE_DIR="${LANXUN_BASE_DIR:-/opt/daily-news}"
REPO_DIR="${LANXUN_REPO_DIR:-$BASE_DIR/news-site}"
REMOTE_URL="${LANXUN_REMOTE_URL:-git@github.com:1294369044-oss/-X.git}"
KEY_FILE="${LANXUN_DEPLOY_KEY:-/root/.ssh/lanxun_news_deploy}"
KNOWN_HOSTS="${LANXUN_KNOWN_HOSTS:-/root/.ssh/known_hosts}"
LOG_DIR="${LANXUN_LOG_DIR:-$BASE_DIR/logs}"
LOCK_FILE="${LANXUN_LOCK_FILE:-$BASE_DIR/publish.lock}"

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_FILE")"
RUN_LOG="$LOG_DIR/publish-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$RUN_LOG") 2>&1
find "$LOG_DIR" -maxdepth 1 -type f -name 'publish-*.log' -mtime +30 -delete

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "已有发布任务运行，跳过本次。"
  exit 0
fi

if [[ ! -r "$KEY_FILE" ]]; then
  echo "缺少 Deploy Key：$KEY_FILE" >&2
  exit 1
fi
if [[ ! -r "$KNOWN_HOSTS" ]]; then
  echo "缺少 GitHub 主机指纹文件：$KNOWN_HOSTS；拒绝在无人值守任务中自动信任主机。" >&2
  exit 1
fi

export GIT_SSH_COMMAND="ssh -i $KEY_FILE -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS -o ConnectTimeout=20"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone --branch main --single-branch "$REMOTE_URL" "$REPO_DIR"
else
  if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
    echo "仓库存在未提交修改，停止以免覆盖：$REPO_DIR" >&2
    exit 1
  fi
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" pull --ff-only origin main
fi

cd "$REPO_DIR"
if [[ ! -f package.json || ! -f crawler/news_digest.py || ! -f scripts/import-crawler-data.mjs ]]; then
  echo "仓库缺少站点或爬虫入口文件，停止。" >&2
  exit 1
fi

if command -v corepack >/dev/null 2>&1; then
  corepack pnpm install --frozen-lockfile
elif command -v pnpm >/dev/null 2>&1; then
  pnpm install --frozen-lockfile
else
  echo "找不到 corepack 或 pnpm，停止。" >&2
  exit 1
fi

python3 crawler/news_digest.py
node scripts/import-crawler-data.mjs crawler/output/news.json
if command -v corepack >/dev/null 2>&1; then
  CI=true ASTRO_TELEMETRY_DISABLED=1 corepack pnpm build
else
  CI=true ASTRO_TELEMETRY_DISABLED=1 pnpm build
fi

# 构建输出和爬虫临时输出均被 .gitignore 排除；自动任务只允许提交数据文件。
git add -- src/data/generated-news.json
if git diff --cached --quiet; then
  echo "新闻数据没有实质变化，不创建提交。"
  exit 0
fi

echo "待提交文件："
git diff --cached --name-status
git commit -m "chore: refresh news feed $(date '+%Y-%m-%d %H:%M %z')"
git push origin main
echo "新闻站点已推送：$(git rev-parse --short HEAD)"
