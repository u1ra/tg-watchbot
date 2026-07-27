<div align="center">
  <h1>tg-watchbot</h1>
  <p>Telegram 双向客服机器人 + Web/RSS 监控推送 + 群组/频道关键词监听 + 可视化管理面板</p>
  <p>
    <a href="#ai-一键部署推荐">AI 一键部署</a> ·
    <a href="#docker-手动部署">Docker 手动部署</a> ·
    <a href="#ai-一键升级">AI 一键升级</a> ·
    <a href="#开启新用户验证可选">新用户验证</a> ·
    <a href="#cloudflare-tunnel-教程">Tunnel 教程</a>
  </p>
</div>

> 本项目基于 [GongyiChuren/tg-watchbot](https://github.com/GongyiChuren/tg-watchbot) 二次开发，新增了群组/频道关键词监听、新用户两阶段验证、配置导入导出等功能。原项目保留全部署名与授权要求，详见文末 [License](#license)。

## 这是什么

一个跑在自己服务器上的 Python 小服务，把这几件事合在一起：

- **双向客服**：用户私聊 Bot，消息转发给你；你直接回复就能回给用户；
- **Web/RSS 监控**：定时抓网页或 RSS，命中关键词 / 新条目 / 价格库存变化就推送给你；
- **群组/频道监听**：用你自己的 TG 账号静默监听群消息，命中关键词自动通知；
- **新用户验证（可选）**：首次私聊的用户先过 Cloudflare Turnstile + 算数题，挡广告号；
- **Web 管理面板**：以上全部可视化配置，另有收件箱、用户管理、日志、配置导入导出。

新用户验证需要搭配姊妹项目 [tg-watchbot-verify](https://github.com/u1ra/tg-watchbot-verify)（两个 Cloudflare Worker，免费额度够用）。

## 功能截图

![双向对话](https://pic.gongyichuren.de/file/1779287173835_8521cab29a9635743a603582ceb7ba02.png)
![监控配置](https://pic.gongyichuren.de/file/1779287170665_17b7c8b4040d6334ea62a108d08db644.png)
![管理面板](https://pic.gongyichuren.de/file/1779345259571_image.png)
![新版面板](https://pic.gongyichuren.de/file/1779437104636_image.png)
![群监听](https://pic.gongyichuren.de/file/1779437050727_image.png)

## 部署（三选一）

部署前你只需要准备：一台 Linux 服务器（有 Docker）、一个 Telegram Bot Token（找 @BotFather 要）、你的 Telegram 数字 ID（找 @userinfobot 要）。

<a id="ai-one-line-install"></a>

### AI 一键部署（推荐）

把下面这段完整复制给有终端权限的 AI 编程助手（如 Kimi Code、Claude Code），照做即可：

```text
请作为服务器部署代理，完整部署 tg-watchbot：

仓库：https://github.com/u1ra/tg-watchbot.git
默认目录：/opt/tg-watchbot
首选方式：Docker Compose

执行要求：
1. 先检查操作系统、CPU 架构、Docker、Docker Compose、Git 和 8765 端口占用；报告异常后再处理，不要静默覆盖已有服务。
2. 如果目标目录已存在或已有 tg-watchbot 数据，停止全新安装，改用 README 的"AI 一键升级"提示词。
3. 克隆仓库后完整阅读 README.md、.env.example 和 docker-compose.yml。
4. 仅在文件不存在时执行：
   - cp .env.example .env
   - cp config.example.yaml config.yaml
   - touch tg-watchbot.sqlite3 tg-watchbot.log
   不得覆盖已有 .env、config.yaml 或 SQLite 数据库。
5. 将 .env 权限设为 600。不要要求用户在聊天中粘贴 Bot Token 等密钥，也不要在输出和报告中展示它们。
6. 保持 docker-compose.yml 默认的 127.0.0.1:8765 端口绑定，不要把管理面板直接裸露到公网。
7. 保持 BOT_VERIFICATION_ENABLED=false，不要自动创建 Cloudflare 资源或开启新用户验证。
8. 依次运行并检查：
   - docker compose config
   - docker compose build
   - docker compose run --rm --no-deps tg-watchbot python -m unittest discover -s tests -v
   - docker compose up -d
   - docker compose ps
   - curl --fail http://127.0.0.1:8765/health
9. 启动失败时查看 docker compose logs --tail=200，过滤 Token、secret、session 等敏感值；不要通过删除数据库或覆盖配置来"修复"。
10. 部署成功后告诉用户：如何用 SSH 隧道访问面板、立即修改默认密码、在"设置"里填写 TELEGRAM_BOT_TOKEN 和 ADMIN_CHAT_ID 后执行 docker compose restart。
11. 最终只汇报安装路径、容器状态、健康检查和面板访问方式；不要输出任何密钥内容。
```

<a id="docker-install"></a>

### Docker 手动部署

```bash
git clone https://github.com/u1ra/tg-watchbot.git tg-watchbot
cd tg-watchbot
cp .env.example .env
cp config.example.yaml config.yaml
chmod 600 .env
touch tg-watchbot.sqlite3 tg-watchbot.log
docker compose up -d --build
```

<a id="manual-install"></a>

### 手动 / systemd 部署

```bash
git clone https://github.com/u1ra/tg-watchbot.git tg-watchbot
cd tg-watchbot
python3 -m venv .venv
./.venv/bin/pip install -U pip -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
chmod 600 .env
./.venv/bin/python app.py
```

确认能打开面板后，安装 systemd 服务（仓库自带 [service 文件](systemd/tg-watchbot.service)，建议部署到 `/opt/tg-watchbot`）：

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin tg-watchbot || true
sudo chown -R tg-watchbot:tg-watchbot /opt/tg-watchbot
sudo chmod 600 /opt/tg-watchbot/.env
sudo cp systemd/tg-watchbot.service /etc/systemd/system/tg-watchbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now tg-watchbot
```

<a id="systemd-install"></a>

## 部署后必做的 3 件事

1. **打开面板**：面板只监听服务器本机 `http://127.0.0.1:8765`，在自己电脑上先开 SSH 隧道再访问：

   ```bash
   ssh -L 8765:127.0.0.1:8765 user@服务器IP
   ```

   然后浏览器打开 `http://127.0.0.1:8765`，默认账号 `admin` / `change-me`。

2. **改密码**：登录后进「设置」，立刻修改面板用户名和密码。

3. **填 Bot 信息**：「设置」里填 `TELEGRAM_BOT_TOKEN` 和 `ADMIN_CHAT_ID`（你的 Telegram 数字 ID，最多 3 个用逗号分隔），保存后重启：

   ```bash
   docker compose restart    # Docker 部署
   sudo systemctl restart tg-watchbot    # systemd 部署
   ```

之后添加监控、配置群监听等全部在面板里点选完成，不用再碰命令行。

> 想从公网直接访问面板：不要改端口映射裸奔，用 [Cloudflare Tunnel](#cloudflare-tunnel-教程) 或带鉴权的反代。

<a id="ai-一键升级"></a>

## AI 一键升级

已经在跑旧版本？把下面这段复制给 AI 助手，安全升级不丢数据：

```text
请安全升级服务器上的 tg-watchbot，不得丢失现有配置和数据：

目标仓库：https://github.com/u1ra/tg-watchbot.git

执行要求：
1. 先定位实际项目目录，检查 git remote、当前分支、git status、Docker Compose 状态和磁盘空间。
2. 如果存在未提交修改、来源不明文件或远端不是上述仓库，停止并向用户说明，不要 reset、checkout、clean 或强制覆盖。
3. 在项目目录旁创建带时间戳的备份目录，只备份并校验以下存在的文件：
   - .env
   - config.yaml
   - tg-watchbot.sqlite3
   - docker-compose.yml
   不要把备份提交到 Git。
4. 执行 git fetch，然后使用 git pull --ff-only；不允许强制推送、hard reset 或自动解决冲突。
5. 不要重新执行 cp .env.example .env 或 cp config.example.yaml config.yaml。新环境变量缺失时程序使用安全默认值，之后可在 WebUI 配置。
6. 保持 BOT_VERIFICATION_ENABLED 现状，不要自动创建 Cloudflare 资源。
7. 依次运行：
   - docker compose config
   - docker compose build
   - docker compose run --rm --no-deps tg-watchbot python -m unittest discover -s tests -v
   - docker compose up -d
   - docker compose ps
   - curl --fail http://127.0.0.1:8765/health
8. 检查最近 200 行容器日志，确认没有数据库迁移错误或循环重启；报告时隐藏所有敏感值。
9. 验证 WebUI 仍可登录、原监控和用户数据仍存在。
10. 如果升级失败，停止继续修改，保留现场和备份，汇报失败命令和错误摘要；不要自行删除数据库。
11. 最终汇报旧/新 commit、备份路径、测试结果、容器与健康状态；不要输出任何密钥内容。
```

面板里的 `/update` 页面也支持安全检查的在线更新（只允许 ff-only，更新前自动记录回滚点，可一键回滚）。

<a id="turnstile-production"></a>

## 开启新用户验证（可选）

默认关闭。开启后，首次私聊 Bot 的用户必须先完成 Cloudflare Turnstile 人机验证 + 一道算数题，广告号基本进不来。老用户一次性免验证。

准备工作只有一样：**一个指向 tg-watchbot 的 Tunnel 域名**（见下一节）。之后的完整步骤（创建 Turnstile、部署两个 Worker、填 WebUI、真机验收）全部在姊妹项目文档里，照做即可：

👉 **[tg-watchbot-verify 部署教程](https://github.com/u1ra/tg-watchbot-verify#readme)**

大致链路：

```text
Telegram 用户
  → 验证页面 Worker（Turnstile 页面）
  → Cloudflare Tunnel
  → VPS 上的 tg-watchbot:8765
  → Siteverify Worker（保管 Secret）
  → 通过后 Bot 发出算数题
```

两个 Worker 缺一不可，地址不能混用。部署完成后在面板「设置 → 新用户两阶段验证」勾选启用；「用户管理」页可查看每个用户的验证状态，也可以用「重置验证（测试）」让指定用户重新走一遍流程做验收。

<a id="cloudflare-tunnel-docker"></a>

## Cloudflare Tunnel 教程

作用：不开任何服务器入站端口，把公网 HTTPS 域名安全转发到只监听 `127.0.0.1:8765` 的 tg-watchbot。既是公网管理面板的推荐方式，也是新用户验证的前提。

需要准备：一个接入 Cloudflare DNS 的域名、一台有 Docker 的 VPS、正在运行的 tg-watchbot。全文示例域名 `bot-api.example.com`，请换成你自己的。

### 第 1 步：创建 Tunnel

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) → `Networking → Tunnels` → `Create a tunnel`。
2. Connector 选 `Cloudflared`，名称随意（如 `tg-watchbot-vps`），保存。
3. 安装环境选 `Docker`，页面会显示一条带 `--token eyJ...` 的命令。**只取出 `eyJ...` 开头的 Token**，不要把整条命令贴到聊天或公开日志里。

### 第 2 步：在 VPS 启动 cloudflared

这一步要做的事：在 VPS 上跑一个 `cloudflared` 容器，它拿着第 1 步的 Token 主动连上 Cloudflare，之后 Cloudflare 收到的 `bot-api.example.com` 请求就通过这条连接送到本机的 tg-watchbot：

```text
https://bot-api.example.com  →  Cloudflare  →  cloudflared 容器  →  127.0.0.1:8765（tg-watchbot）
```

Token 单独放在新目录里，**不要**写进 tg-watchbot 的 `.env`。

**① 建目录（复制执行）：**

```bash
sudo install -d -m 700 -o "$USER" -g "$(id -gn)" /opt/tg-watchbot-cloudflared
cd /opt/tg-watchbot-cloudflared
```

**② 写入 Token**——复制下面整段执行，然后在提示后**粘贴第 1 步的 Token 并回车**（输入不显示，是正常的）：

```bash
umask 077
read -s -p "粘贴 Tunnel Token 后回车: " TUNNEL_TOKEN; echo
printf 'TUNNEL_TOKEN=%s\n' "$TUNNEL_TOKEN" > cloudflared.env
chmod 600 cloudflared.env
unset TUNNEL_TOKEN
```

执行完 `cloudflared.env` 里就只有一行 `TUNNEL_TOKEN=eyJ...`，可以用 `ls -l cloudflared.env` 确认权限是 `-rw-------`。

**③ 创建 `compose.yaml`**——整段复制执行即可，不用改任何地方：

```bash
cat > compose.yaml <<'EOF'
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: tg-watchbot-cloudflared
    restart: unless-stopped
    network_mode: host
    command: tunnel --no-autoupdate --loglevel info run
    env_file:
      - ./cloudflared.env
EOF
```

**④ 启动并看日志：**

```bash
docker compose up -d
docker compose logs --tail=100 cloudflared
```

看到类似下面的输出就是连上了（关键是有 4 条 `Registered tunnel connection`）：

```text
INF Registered tunnel connection connIndex=0 connection=... location=...
INF Registered tunnel connection connIndex=1 connection=... location=...
INF Registered tunnel connection connIndex=2 connection=... location=...
INF Registered tunnel connection connIndex=3 connection=... location=...
```

这时回到 Cloudflare 控制台，Tunnel 状态会从 `Inactive` 变成 `Healthy`。

> `network_mode: host` 的作用：让容器里的 `127.0.0.1:8765` 指的就是 VPS 宿主机，和 tg-watchbot 默认的端口绑定正好对上，所以什么网络都不用配。如果你不用 host 网络，容器里的 `127.0.0.1` 是容器自己，就连不上了——那种情况要让两个容器进同一个 Docker 网络，并把第 3 步的 Service URL 改成 `http://tg-watchbot:8765`。

**连不上时按这个顺序查：**

| 日志/状态 | 原因和处理 |
|---|---|
| `error parsing token` / `Invalid token` | Token 复制不全或多了空格，重新从控制台复制 |
| 一直 `Retrying connection` | cloudflared 连 Cloudflare 用的是**出站** `7844` 端口（UDP/QUIC，失败自动回退 TCP）。普通 VPS 出站默认全放行，不会有这个问题；只有在出站被严格限制的网络（如只放行 80/443 的公司网络）才需要放行出站 `7844` |
| 日志正常但控制台一直 `Inactive` | 等 1-2 分钟刷新；还不行就重建容器 `docker compose up -d --force-recreate` |

### 第 3 步：添加 Published application 路由

控制台 → 打开 Tunnel → `Routes` → `Add route` → `Published application`：

| 项目 | 填写 |
|---|---|
| Subdomain | `bot-api` |
| Domain | `example.com` |
| Path | 留空；只想给验证用可只发布 `/api/verify/turnstile` |
| Service type | `HTTP` |
| Service URL | `http://127.0.0.1:8765` |

### 第 4 步：验证

```bash
curl --fail --silent --show-error https://bot-api.example.com/login >/dev/null
```

能通就成功了。常见故障：

| 现象 | 检查方向 |
|---|---|
| `502` | cloudflared 连不上 `127.0.0.1:8765`，查 tg-watchbot 状态和网络模式 |
| `403` / 跳 Access 登录页 | Access 策略拦截，见下面注意事项 |
| Error `1033` | Tunnel 没有健康连接，查容器日志和 Token |
| DNS 解析失败 | 路由或 DNS 未生效 |

### Access 注意事项

不要给验证 API 所在的 hostname 套需要邮箱登录的 Access 策略（Worker 不会浏览器登录）。推荐分工：

```text
admin.example.com    → Tunnel → tg-watchbot（Access 保护，管理用）
bot-api.example.com  → Tunnel → tg-watchbot（公开，供验证 Worker 调用）
verify.example.com   → 验证页面 Worker（Telegram Mini App）
```

日常维护：`docker compose pull && docker compose up -d` 更新 cloudflared；Token 泄露时在 Tunnel 详情页 `Refresh token` 并更新 `cloudflared.env` 后 `docker compose up -d --force-recreate`。

## 配置说明

### `.env` 常用项

全部变量见 [.env.example](.env.example)，都有注释。最常用的：

| 变量 | 说明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 创建的 Bot Token |
| `ADMIN_CHAT_ID` | 管理员 Telegram 数字 ID，最多 3 个逗号分隔 |
| `WEB_PANEL_USER` / `WEB_PANEL_PASSWORD` | 面板账号密码，部署后立刻改 |
| `WEB_PANEL_HOST` / `WEB_PANEL_PORT` | 面板监听地址和端口，默认 `127.0.0.1:8765` |
| `TG_API_ID` / `TG_API_HASH` / `TG_API_SESSION` | （可选）用户会话监听用，面板里可扫码登录生成 |
| `BOT_VERIFICATION_ENABLED` | 新用户验证开关，默认 `false` |
| `TURNSTILE_*` 系列 | 新用户验证参数，全部可在面板「设置」里填，见 [verify 教程](https://github.com/u1ra/tg-watchbot-verify#readme) |

### `config.yaml`

监控、群监听、清理策略等，**都能在面板里可视化编辑**，手改 YAML 只是高级选项。典型示例见 [config.example.yaml](config.example.yaml)：

```yaml
monitors:
  - name: NodeSeek 新帖
    type: rss                      # rss 或 web
    url: https://rss.nodeseek.com/
    interval_seconds: 30           # 默认 30 秒，最低 1 秒；太快容易被目标站限流
    keywords: [VPS, 优惠]           # 命中这些词才推送
    exclude_keywords: [出号]        # 命中排除词优先跳过
    notify_telegram: true          # false 则只记录到面板推送历史
```

```yaml
group_monitors:
  - name: TG 群关键词监听
    enabled: false
    listen_source: bot             # bot（需拉 Bot 进群）或 user_session（用自己账号静默监听）
    chat_id: -1001234567890        # 面板「已发现群聊」可一键填入
    keywords: [VPS, 优惠]
    exclude_keywords: [求带]
    summary_mode: template         # template 或 ai（AI 摘要参数面板里可视化配置）
```

```yaml
cleanup:
  enabled: true
  interval_minutes: 60                      # 每多少分钟清理一次
  monitor_message_delete_after_minutes: 60  # 监控通知消息发送后多久自动删除；0 不删
  monitor_retention_minutes: 1440           # 监控状态数据保留多久
```

清理只删监控状态和推送记录，**不会**删用户、收件箱和对话记录。

其他要点：

- 用 `listen_source: bot` 时，需要在 @BotFather 执行 `/setprivacy` 关闭隐私模式，Bot 才能收到群里普通消息；
- 用 `user_session` 时，在「设置」填 `TG_API_ID` / `TG_API_HASH` 后可直接扫码登录生成会话；
- 广告拦截关键词、快捷回复模板、监控导入导出都在面板里有对应页面。

## 管理命令

管理员在 Telegram 里可用：

```text
/reply <user_id> <内容>      回复指定用户（也可直接回复转发消息）
/sendpic <user_id> [说明]    给指定用户发图片
/block / /unblock <user_id>  封禁 / 解封
/note <user_id> <备注>       加备注
/who <user_id>               查看用户信息
/spamwords / /spamadd / /spamdel   广告关键词管理
/cancel                      取消待发送图片
```

## 面板路由

| 路由 | 说明 |
|---|---|
| `/` | 监控列表 |
| `/monitor/new` `/monitor/templates` `/monitor/bulk` | 新增 / 模板 / 批量新增监控 |
| `/yaml` | YAML 高级编辑 |
| `/settings` | `.env` 设置和清理策略 |
| `/inbox` | 收件箱（完整双向对话） |
| `/users` | 用户管理（备注/封禁/验证状态） |
| `/send` | 主动发消息 |
| `/rules` `/replies` | 广告拦截规则 / 快捷回复 |
| `/monitor/events` | 监控推送历史 |
| `/config/export` | 配置导入 / 导出 |
| `/update` | 在线更新（ff-only + 回滚） |
| `/logs` `/health` | 日志 / 健康检查 |

## 注意事项

- Telegram Bot 不能主动私聊陌生人，对方必须先给 Bot 发过消息。
- 公网暴露面板前务必改默认密码，优先用 Tunnel 或反代鉴权；`.env` 权限保持 `600`。
- 监控间隔默认 30 秒，实际部署建议按目标站承受能力调高，避免被限流。

## 使用的开源库

[`aiogram`](https://github.com/aiogram/aiogram)（Bot API）· [`FastAPI`](https://github.com/fastapi/fastapi) + [`Uvicorn`](https://github.com/encode/uvicorn)（面板）· [`APScheduler`](https://github.com/agronholm/apscheduler)（定时任务）· [`httpx`](https://github.com/encode/httpx)（抓取）· [`feedparser`](https://github.com/kurtmckee/feedparser)（RSS）· [`Beautiful Soup`](https://www.crummy.com/software/BeautifulSoup/)（网页解析）· [`telethon`](https://github.com/LonamiWebs/Telethon)（用户会话监听）· [`qrcode`](https://github.com/lincolnloop/python-qrcode)（扫码登录）· [`PyYAML`](https://pyyaml.org/) · [`python-dotenv`](https://github.com/theskumar/python-dotenv)

## 友链

- [Linux.do](https://linux.do)
- [NodeSeek](https://www.nodeseek.com)

## 更新日志

### 2026-07-27

- 普通 Web/RSS 监控新增「排除关键词」WebUI，命中排除词时优先跳过。
- 新增可选的新用户 Turnstile + 算数题两阶段验证（Telegram Mini App、initData 验签、nonce 防重放、失败冷却），老用户一次性免验证。
- 「用户管理」新增验证状态显示和「重置验证（测试）」。
- 配套项目 [tg-watchbot-verify](https://github.com/u1ra/tg-watchbot-verify) 的 Siteverify Worker 新增 Bearer 鉴权，本侧对应 `TURNSTILE_VERIFY_AUTH_TOKEN`。
- 新增 Cloudflare Tunnel Docker 部署教程。

### 2026-06-02

- 群组/频道关键词监听：用 Telethon 用户账号静默监听群消息，命中关键词自动推送。
- 「已发现群聊」自动记录，可一键创建监听。
- 移除频道媒体下载/转发功能，精简为纯关键词监听。

### 2026-05-28 及更早

- 频道媒体转发、Telegram 二维码登录（后于 06-02 精简）。
- TG 群监听可视化配置、AI 摘要、限频去重。
- `/update` 安全在线更新与一键回滚。
- 收件箱双向对话、用户管理、快捷回复、广告拦截、配置导入导出、多管理员。
- 面板先行启动，Token 后补。

更早历史见 [commit 记录](https://github.com/u1ra/tg-watchbot/commits)。

## License

本项目采用非商业授权（沿用原项目要求）。

你可以：
- 学习、研究、个人使用本项目
- 修改代码用于非商业用途
- 在非商业项目中使用本项目

你必须：
- 保留原作者署名
- 在引用或二次发布时注明项目来源：
  https://github.com/GongyiChuren/tg-watchbot

你不可以：
- 将本项目或其修改版本用于商业用途
- 售卖本项目或基于本项目提供付费服务
- 在未获得作者书面许可的情况下用于商业产品

商业使用请先联系原作者获得授权。
