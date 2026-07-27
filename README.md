<div align="center">
  <h1>tg-watchbot</h1>
  <p>Telegram 双向客服机器人 + Web/RSS 监控推送 + 群组/频道关键词监听 + 可视化管理面板</p>
  <p>双向对话 · 关键词监控 · 群组/频道监听 · 私聊广告拦截 · 多管理员 · 配置导入导出</p>
  <p>
    <a href="#ai-one-line-install">AI 辅助部署</a> ·
    <a href="#docker-install">Docker 安装</a> ·
    <a href="#cloudflare-tunnel-docker">Tunnel Docker 部署</a> ·
    <a href="#manual-install">手动安装</a> ·
    <a href="#systemd-install">systemd 部署</a> ·
    <a href="#turnstile-production">新用户验证部署</a> ·
    <a href="#面板路由">面板路由</a> ·
    <a href="#更新日志">更新日志</a>
  </p>
</div>

## 简介：
tg-watchbot 是一个轻量级 Python 服务，把 **Telegram 双向客服机器人**、**Web/RSS 监控推送** 和 **群组/频道关键词监听** 合在一起：

- 普通用户私聊 Bot，消息会转发给管理员；
- 可选为首次私聊的新用户启用 Turnstile + 算数题两阶段验证；
- 管理员可以直接回复、主动发文字/图片、封禁/备注用户；
- 后台定时监控 RSS 或网页，命中关键词、新条目、价格/库存变化后推送给管理员；
- 使用 Telethon 用户账号监听群组/频道消息，命中关键词后自动推送通知给管理员；
- 自带一个 Web 管理面板，可配置监控目标、编辑 YAML、查看收件箱和日志。

项目为单文件应用，适合个人服务器、NAT 小鸡、轻量 VPS 直接用 systemd 跑。

生产环境的新用户验证配套项目为
[`u1ra/tg-watchbot-verify`](https://github.com/u1ra/tg-watchbot-verify)。
它提供独立的验证页面 Worker 和 Siteverify Worker，并通过 Cloudflare Tunnel
安全连接运行在 VPS 上的 tg-watchbot。准备启用时请依次阅读：

1. [Cloudflare Tunnel（Docker 推荐）部署教程](#cloudflare-tunnel-docker)：从控制台创建 Tunnel、保存 Token、启动 cloudflared 容器，到配置 Published application 和检查连通性。
2. [新用户两阶段验证完整部署教程](#turnstile-production)：部署验证页面 Worker、Siteverify Worker，并填写 tg-watchbot WebUI。

<a id="ai-one-line-install"></a>

## AI 辅助部署

下面的提示词可以直接复制给具有终端权限的 AI 编程助手。默认采用 Docker，保留现有数据，并把验证功能维持在安全的关闭状态，直到正式域名、Cloudflare Tunnel、验证页面 Worker 和 Siteverify Worker 全部准备完成。

### 全新部署提示词

```text
请作为服务器部署代理，完整部署 tg-watchbot：

仓库：https://github.com/u1ra/tg-watchbot.git
默认目录：/opt/tg-watchbot
首选方式：Docker Compose

执行要求：
1. 先检查操作系统、CPU 架构、Docker、Docker Compose、Git 和 8765 端口占用；报告异常后再处理，不要静默覆盖已有服务。
2. 如果目标目录已经存在或已经有 tg-watchbot 数据，停止全新安装，改用 README 的“已有实例升级提示词”。
3. 克隆仓库后完整阅读 README.md、DEVELOPMENT_PLAN.md、.env.example 和 docker-compose.yml。
4. 仅在文件不存在时执行：
   - cp .env.example .env
   - cp config.example.yaml config.yaml
   - touch tg-watchbot.sqlite3 tg-watchbot.log
   不得覆盖已有 .env、config.yaml 或 SQLite 数据库。
5. 将 .env 权限设为 600。不要要求用户在聊天中粘贴 Telegram Bot Token、Turnstile secret、API key 或会话字符串，也不要在命令输出和最终报告中展示它们。
6. 保持 docker-compose.yml 默认的 127.0.0.1:8765 端口绑定，不要把管理面板直接裸露到公网。管理访问可使用 SSH 隧道或带 HTTPS/鉴权的反向代理；新用户验证的生产公网链路按 README 的“生产部署”章节使用配套仓库和 Cloudflare Tunnel。
7. 保持 BOT_VERIFICATION_ENABLED=false 和 TURNSTILE_TEST_MODE=false。除非用户明确要求并确认 Cloudflare 资源范围，否则不要创建 Cloudflare Tunnel、Turnstile widget 或 Worker，也不要开启新用户验证。
8. 依次运行并检查：
   - docker compose config
   - docker compose build
   - docker compose run --rm --no-deps tg-watchbot python -m unittest discover -s tests -v
   - docker compose up -d
   - docker compose ps
   - curl --fail http://127.0.0.1:8765/health
9. 启动失败时查看 docker compose logs --tail=200，但必须过滤 Token、secret、initData、session 等敏感值；不要通过删除数据库或覆盖配置来“修复”。
10. 部署成功后告诉用户：
    - 如何通过 SSH 隧道访问 http://127.0.0.1:8765
    - 立即修改默认面板密码
    - 在“设置”中填写 TELEGRAM_BOT_TOKEN 和 ADMIN_CHAT_ID，保存后执行 docker compose restart
    - 普通监控的“排除关键词”可在新增/编辑页面直接配置
    - Turnstile 参数可在“设置 → 新用户两阶段验证”配置，但生产 secret 只能保存在配套 Siteverify Worker
11. 最终只汇报安装路径、容器状态、健康检查、面板访问方式、测试结果和仍需用户完成的项目；不要输出任何密钥内容。
```

### 已有实例升级提示词

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
5. 不要重新执行 cp .env.example .env 或 cp config.example.yaml config.yaml。新环境变量缺失时由程序使用安全默认值，之后可在 WebUI 中配置。
6. 保持 BOT_VERIFICATION_ENABLED=false，除非它在升级前已经由用户明确启用；不要自动使用测试 key 或自动创建 Cloudflare 资源。
7. 依次运行：
   - docker compose config
   - docker compose build
   - docker compose run --rm --no-deps tg-watchbot python -m unittest discover -s tests -v
   - docker compose up -d
   - docker compose ps
   - curl --fail http://127.0.0.1:8765/health
8. 检查最近 200 行容器日志，确认没有数据库迁移错误、循环重启或验证配置错误；报告时隐藏所有敏感值。
9. 验证 WebUI 仍可登录、原监控和用户数据仍存在，并确认普通监控编辑页出现“排除关键词”，设置页出现“新用户两阶段验证”。
10. 如果升级失败，停止继续修改，保留现场和备份，汇报失败命令、错误摘要及可恢复路径；不要自行删除数据库。
11. 最终汇报旧/新 commit、备份路径、测试结果、容器与健康状态，以及是否仍需配置正式 HTTPS/Turnstile。不要输出任何密钥内容。
```

### AI 部署验收标准

- 容器状态为运行中，`/health` 返回 `ok`。
- Web 面板仍只绑定在 `127.0.0.1:8765`，或已经由用户明确配置安全的 HTTPS 反代。
- `.env` 权限为 `600`，数据库和配置文件没有被覆盖。
- 默认面板密码已提醒修改，Token 等敏感值没有出现在聊天、日志摘要或 Git。
- 全量测试通过；若不能通过，AI 必须明确报告，不能把部署描述为成功。
- 新用户验证默认关闭。只有 Tunnel、验证页面 Worker、Siteverify Worker、sitekey、hostname/action 全部确认后，才通过 WebUI 启用。

### 启用新用户验证的 AI 部署提示词

下面这段用于已经成功运行 tg-watchbot、现在准备启用生产验证的实例：

```text
请为已经运行的 tg-watchbot 部署生产环境的新用户两阶段验证。

主仓库：https://github.com/u1ra/tg-watchbot.git
配套验证仓库：https://github.com/u1ra/tg-watchbot-verify

执行要求：
1. 先完整阅读两个仓库的 README、主项目 .env.example，以及配套仓库的 wrangler.jsonc、src/index.js、siteverify-worker/wrangler.jsonc 和 siteverify-worker/src/index.js；以代码中的实际变量名和路由为准。
2. 检查 tg-watchbot 健康状态，确认 http://127.0.0.1:8765/health 正常。不得为了验证功能把 8765 端口直接开放到公网。
3. 先向用户确认最终使用的三个地址：
   - 验证页面 Worker 地址，例如 https://verify.example.com
   - Tunnel 地址，例如 https://bot-api.example.com
   - Siteverify Worker 地址，例如 https://tg-watchbot-siteverify.example.workers.dev
   地址用途不得混用。
4. 只有获得用户明确授权后才能创建或修改 Cloudflare 资源。按照 README 的“Cloudflare Tunnel（Docker 推荐）”章节创建远程管理 Tunnel，使用独立 cloudflared Docker 容器和 host network，把 Tunnel 公网 hostname 转发到 http://127.0.0.1:8765；Tunnel Token 不得写入主项目 .env。
5. 创建 Turnstile Widget：模式使用 Managed，Pre-clearance 关闭，允许的 hostname 必须是“验证页面 Worker”的 hostname，不是 Tunnel 或 Siteverify Worker 的 hostname。
6. 在本机使用 `openssl rand -hex 32` 生成 Siteverify 共享鉴权 Token，然后从配套仓库分别部署两个 Worker，少一个都不能启用：
   - 验证页面 Worker：TG_WATCHBOT_ORIGIN=<Tunnel HTTPS 根地址>、TURNSTILE_SITE_KEY=<sitekey>、TURNSTILE_EXPECTED_ACTION=turnstile-spin-v1
   - Siteverify Worker：TURNSTILE_SECRET_KEY=<Turnstile secret，必须保存为加密 Secret>、SITEVERIFY_AUTH_TOKEN=<刚生成的共享鉴权 Token，必须保存为加密 Secret>、TURNSTILE_EXPECTED_HOSTNAME=<验证页面 Worker hostname>、TURNSTILE_EXPECTED_ACTION=turnstile-spin-v1
7. 不要要求用户在聊天中粘贴 Turnstile secret、共享鉴权 Token、Cloudflare API Token、Tunnel Token 或 Bot Token；不要把它们写入 Git、命令参数或日志。Turnstile secret 只能保存在 Siteverify Worker；共享鉴权 Token 还需要以 `TURNSTILE_VERIFY_AUTH_TOKEN` 的名称保存在 tg-watchbot 服务端 `.env`。
8. 在 tg-watchbot WebUI 中填写：
   - Mini App 公网根地址=<验证页面 Worker HTTPS 根地址，不加 /verify/telegram>
   - Turnstile Site Key=<同一个 sitekey>
   - Spin Siteverify Worker 地址=<Siteverify Worker HTTPS 根地址，不加 /health>
   - Siteverify 鉴权 Token=<与 Worker 的 SITEVERIFY_AUTH_TOKEN 完全相同>
   - 预期 Hostname=<验证页面 Worker hostname，不带协议和路径>
   - 预期 Action=turnstile-spin-v1
   - 本地测试模式=false
   全部验证完成前保持“启用新用户验证”关闭。
9. 检查 Siteverify Worker 的 /health 返回 ok；按照 Tunnel Docker 章节检查 /api/verify/turnstile 已经能到达 tg-watchbot，并确认验证页面 Worker 不返回 401/502/503。若 Tunnel hostname 使用 Cloudflare Access，必须保证该 API 不会被交互式登录拦截。
10. 最后再启用新用户验证，使用非管理员 Telegram 账号完成 Turnstile、算数题和重新发送消息的端到端测试。可以使用从未私聊过 Bot 的账号，也可以在 WebUI“用户管理”中对现有账号点击“重置验证（测试）”；后者只清除该用户的验证状态，不删除资料或历史消息。
11. 最终汇报三个非敏感 URL、hostname/action、是否已经配置两端共享鉴权、Worker 健康状态、Tunnel 状态和端到端结果；不得输出 sitekey 以外的任何密钥内容。
```

## 更新日志

### 2026-07-27 更新

- 普通 Web/RSS 监控新增“排除关键词”WebUI，支持保存和编辑回显，命中排除词时优先跳过。
- 新增可选的新用户 Turnstile + 算数题两阶段验证，老用户一次性免验证。
- 新增 Telegram Mini App、服务端 `initData` 验签、nonce 防重放、过期、失败冷却与安全响应头。
- “设置”和“用户管理”均可维护全部非敏感验证参数；生产 Turnstile secret 仍只保存在配套 Siteverify Worker。
- Siteverify Worker 新增可选 Bearer 鉴权；tg-watchbot 新增 `TURNSTILE_VERIFY_AUTH_TOKEN` 配置和 WebUI 密码输入框，请求时自动携带与 Worker `SITEVERIFY_AUTH_TOKEN` 相同的值。
- “用户管理”新增验证状态显示和“重置验证（测试）”操作，可让指定非管理员用户重新完成 Turnstile + 算数题，同时保留用户资料、备注、封禁状态和历史消息。
- 补充共享鉴权失败的 `401` 排查说明，并明确本地测试模式只切换 Cloudflare 测试密钥，不会改变新老用户的验证范围。
- 新用户验证默认关闭，生产 Cloudflare 资源与真实 Telegram 联调需在最终 HTTPS 域名确定后执行。
- 补充配套项目 [`tg-watchbot-verify`](https://github.com/u1ra/tg-watchbot-verify) 的联合部署说明，明确 Cloudflare Tunnel、验证页面 Worker、Siteverify Worker 和 WebUI 字段之间的对应关系。
- 新增独立的 Cloudflare Tunnel Docker 部署教程，覆盖 Tunnel 创建、Token 保存、host network、Published application、Access 策略、连通性验证与 Token 轮换。

### 2026-06-02 更新

- **群组/频道关键词监听**：使用 Telethon 用户账号监听群组和频道消息，命中关键词后自动推送通知给管理员。
- 支持 `user_session` 监听模式：Bot 不需要在群里，用你自己的 TG 账号静默监听，更隐蔽。
- 修复 Telethon `Message` 对象没有 `caption` 属性的错误，统一使用 `msg.message` 获取消息文本。
- 修复两个 Telethon 客户端使用同一个 session 互相冲突的问题，合并为单个客户端。
- 删除「频道媒体下载/转发」功能，精简为纯关键词监听。
- Web 面板导航优化：删除「频道媒体」入口，修复导航标签被遮住的问题。
- 已发现群聊自动记录：Telethon 收到消息的群组/频道会自动显示在面板，可一键创建监听。

### 2026-05-28 更新

- 新增「频道媒体转发」：使用 Telethon 用户账号登录 TG，实时转发群组/频道消息到你的 Telegram。
- 面板新增「频道媒体」页面：搜索已加入群组，一键添加转发监控。
- 支持暂停/恢复监控（保留配置）、删除监控。
- 支持关键词过滤：只转发包含特定关键词的消息，留空则转发全部。
- 支持媒体类型过滤：可选视频、文档、图片、音频。
- 支持 SOCKS5/HTTP 代理，适合国内服务器。
- 新增 Telegram 二维码登录：设置页填写 `TG_API_ID` / `TG_API_HASH` 后，可扫码生成并保存用户会话。
- 修复 Docker / FastAPI 启动报错：移除 `RedirectResponse | HTMLResponse` 联合返回注解，避免被 FastAPI 当成 Pydantic response model 解析。
- 内置下载到服务器、断点续传、并发下载等功能，后续可通过配置开启。
- 仍兼容手动填写 `TG_API_SESSION`。

### 2026-05-22 更新

- TG 群监听功能增强：支持可视化配置监听规则、AI 总结参数与防刷屏策略。
- TG 群监听新增“已发现群聊”：自动显示 Bot 收到过消息的群聊 `chat_id`，可一键创建监听。
- TG 群监听新增“监听来源”选项：`Bot` / `用户会话`（可用于 Bot 无法加入的群）。
- 设置页新增 `TG_API_ID`、`TG_API_HASH`、`TG_API_SESSION` 可视化配置；用于用户会话监听。
- 新增 `/update` 安全更新流程：显示本地/远端 commit、ahead/behind、工作区状态；仅允许 `ff-only` 更新。
- 更新前若检测到本地未提交改动，会拒绝更新；避免覆盖本地代码。
- 新增“回滚上次更新”按钮：更新前自动记录回滚点，可一键回滚并重启。
- TG 群监听 AI 总结新增可视化高级控制：`ai_prompt`、`ai_min_interval_seconds`、`ai_dedupe_window_seconds`。
- TG 群监听增加限频和去重窗口，降低重复推送与 AI 调用成本；AI 失败时仍会回退模板摘要。
- 监控面板新增可观测状态：最近成功/失败时间、最近错误、耗时、推送数、连续失败次数。

### 2026-05-21 第二次更新

- Web 面板新增收件箱直接回复、用户管理、快捷回复、私聊广告拦截、监控推送历史、配置导入/导出。
- 收件箱改为完整双向对话记录：用户消息、Web 回复、TG 管理员回复都会显示。
- 用户管理页新增 Bot / 面板配置卡片，和设置页共用同一份配置；修改 Token、管理员 ID、端口、账号或密码后需要重启。
- `ADMIN_CHAT_ID` 支持最多 3 个管理员，用逗号分隔。
- 单个监控可关闭 Telegram 推送，只记录到 Web 推送历史。

### 2026-05-21 第一次更新

- 默认启动改为先启动 Web 面板：未填写 `TELEGRAM_BOT_TOKEN` / `ADMIN_CHAT_ID` 时，面板仍可打开，同时 Telegram 收发、监控推送不可用。
- 面板配置页可填写 Bot Token、管理员 ID、面板账号和清理策略；保存后需要重启服务让 Bot 配置生效。
- 修复到期消息删除：监控推送消息支持到期自动删除，默认 `60` 分钟。
- 保存配置时会保留 `WEB_PANEL_SESSION_SECRET`，避免保存后登录状态被重置。
- Web 面板界面和站点图标已更新优化。

## 功能

### Telegram 双向机器人

- 使用官方 Telegram Bot API，不做 userbot/selfbot。
- `/start` 建立用户和管理员之间的联系。
- 用户消息先写入 SQLite，再转发给管理员，避免转发失败时丢消息。
- 管理员可通过“回复转发消息”直接回给原用户。
- 支持显式命令：
  - `/reply <user_id> <内容>`：给指定用户发文字；
  - `/sendpic <user_id> [说明]`：给指定用户发图片；
  - `/block <user_id>`：封禁用户；
  - `/unblock <user_id>`：解封用户；
  - `/note <user_id> <备注>`：给用户加备注；
  - `/who <user_id>`：查看用户信息；
  - `/spamwords`：查看广告关键词；
  - `/spamadd <关键词>`：添加广告关键词；
  - `/spamdel <关键词>`：删除广告关键词；
  - `/cancel`：取消待发送图片。
- 普通用户有简单限流，防止刷屏。
- 支持最多 3 个管理员 chat id，用逗号分隔配置。
- 支持私聊广告关键词自动拦截和自动拉黑，不影响 RSS/Web 监控。
- 可选的新用户验证会先校验 Cloudflare Turnstile，再在私聊中发送一道算数题；验证完成后用户需要重新发送原消息。

![示例图片](https://pic.gongyichuren.de/file/1779287173835_8521cab29a9635743a603582ceb7ba02.png)

### Web/RSS 监控

- 支持两类监控：
  - `rss`：解析 RSS/Atom 条目；
  - `web`：用 CSS selector 抓网页条目、标题、链接、价格、库存。
- 支持触发条件：
  - 关键词命中；
  - 新条目；
  - 价格变化；
  - 库存变化。
- 支持论坛 RSS 增强字段：作者、分类、tags、摘要。
- 支持去重，避免同一条反复推送。
- 支持在新增/编辑页面填写排除关键词；命中包含词和排除词时，排除优先。
- 支持作者、分类过滤（YAML 高级配置）。
- 单个监控可关闭 Telegram 推送，只记录到 Web 推送历史。
- 默认监控间隔为 30 秒，最低可设为 1 秒；频率越高越容易被目标站限流。

![示例图片](https://pic.gongyichuren.de/file/1779287170665_17b7c8b4040d6334ea62a108d08db644.png)

### Web 管理面板

- 登录页 + HttpOnly session cookie，不使用丑陋的浏览器 Basic Auth。
- 监控列表、新增、编辑、删除、手动检查、预览。
- NodeSeek / Linux.do RSS 模板。
- 批量新增监控。
- YAML 高级编辑。
- Bot Token / 管理员 ID / 面板账号配置页。
- 明亮 / 暗黑主题切换，主题选择保存在当前浏览器。
- 设置页可修改面板监听地址和端口，并会提示公网监听风险。
- 收件箱页面，可查看完整双向对话记录、重试转发、直接回复。
- 用户管理页，可备注、封禁、解封、主动发消息，并可编辑 Bot / 面板配置。
- 私聊广告拦截规则和快捷回复模板可在 Web 面板编辑。
- 监控推送历史页，可查看 Telegram 推送和仅 Web 记录。
- `config.yaml` 导入/导出页面，方便迁移。
- 主动发消息页面 `/send`，发送成功后会在页面显示结果，并给管理员聊天发送确认提醒。
- 自动清理监控/RSS/网站状态数据；支持定时删除 Telegram 监控通知消息；不会删除用户、收件箱、双向对话消息。
- 日志页面和健康检查 `/health`。

![示例图片](https://pic.gongyichuren.de/file/1779345259571_image.png)
![新版面板截图](https://pic.gongyichuren.de/file/1779437104636_image.png)
![新版群监听截图](https://pic.gongyichuren.de/file/1779437050727_image.png)

## 使用的开源库

本项目的业务逻辑为自写，主要使用并参考了以下开源库的公开 API 和常见用法：

- [`aiogram`](https://github.com/aiogram/aiogram)：Telegram Bot API、命令、消息处理、复制/发送消息。
- [`FastAPI`](https://github.com/fastapi/fastapi)：Web 管理面板、表单、路由、中间件。
- [`Uvicorn`](https://github.com/encode/uvicorn)：ASGI 服务运行。
- [`APScheduler`](https://github.com/agronholm/apscheduler)：异步定时监控任务。
- [`httpx`](https://github.com/encode/httpx)：异步 HTTP 抓取。
- [`feedparser`](https://github.com/kurtmckee/feedparser)：RSS/Atom 解析。
- [`Beautiful Soup`](https://www.crummy.com/software/BeautifulSoup/)：HTML 解析和 CSS selector 抽取。
- [`PyYAML`](https://pyyaml.org/)：`config.yaml` 配置读写。
- [`telethon`](https://github.com/LonamiWebs/Telethon)：Telegram 用户会话、群监听、二维码登录。
- [`qrcode`](https://github.com/lincolnloop/python-qrcode)：生成 Telegram 二维码登录图片。
- [`python-dotenv`](https://github.com/theskumar/python-dotenv)：读取 `.env`。
- Python 标准库 `sqlite3`：消息、用户、去重、监控状态持久化。

## 友链

- [Linux.do](https://linux.do)
- [NodeSeek](https://www.nodeseek.com)

## 安全说明

- 默认建议只在本机访问面板；如果要公网访问，建议使用 Cloudflare Tunnel、Nginx/Caddy 反代鉴权，并使用强密码。
- 监听地址填 `0.0.0.0` 会监听所有网卡；Docker 是否真正暴露公网还取决于端口映射和服务器防火墙。
- Bot 只能给“已经主动私聊过 Bot 的用户”发消息，这是 Telegram Bot API 的限制。

## 快速开始

<a id="docker-install"></a>
## Docker 安装（含自启）

```bash
git clone https://github.com/u1ra/tg-watchbot.git tg-watchbot
cd tg-watchbot
cp .env.example .env
cp config.example.yaml config.yaml
chmod 600 .env
touch tg-watchbot.sqlite3 tg-watchbot.log
docker compose up -d --build
```

Docker 容器内会监听 `0.0.0.0:8765`，但 `docker-compose.yml` 默认只把端口绑定到宿主机 `127.0.0.1:8765`。宿主机打开 `http://127.0.0.1:8765` 即可访问面板。

**⚠️ 注意事项：**
- `.env.example` 里的 `WEB_PANEL_HOST` 默认为 `127.0.0.1`；Docker Compose 会覆盖为容器内可访问的 `0.0.0.0`。
- 不建议直接把 `8765` 裸露到公网；如需公网访问，优先使用 Cloudflare Tunnel、Nginx/Caddy 反代鉴权或 SSH 隧道。
- `.env` 文件会被容器挂载并写入（如 session secret），请勿设置为只读（`:ro`）。
- 如果你明确要直接公网访问，需要同时修改 `docker-compose.yml` 端口映射、服务器防火墙/安全组，并在面板里改强密码。

查看状态与日志：

```bash
docker compose ps
docker compose logs -f
```

修改配置后重启：

```bash
docker compose up -d --build
docker compose restart
```

如果只是更新代码，建议直接重新构建并重启容器：

```bash
docker compose up -d --build
```

<a id="cloudflare-tunnel-docker"></a>

## Cloudflare Tunnel（Docker 推荐）

本节从零创建一个**远程管理的 Cloudflare Tunnel**，使用独立 Docker 容器运行 `cloudflared`，把公网 HTTPS hostname 安全转发到 VPS 上仅监听 `127.0.0.1:8765` 的 tg-watchbot。Cloudflare Tunnel 通过出站连接接入 Cloudflare，不需要开放 VPS 的 `8765`、`80` 或 `443` 入站端口。

新用户验证配套方案中，建议为验证 API 单独准备一个 hostname：

```text
https://bot-api.example.com
  → Cloudflare Tunnel
  → cloudflared Docker 容器（host network）
  → http://127.0.0.1:8765
  → tg-watchbot
```

这个地址以后填写到验证页面 Worker 的：

```text
TG_WATCHBOT_ORIGIN=https://bot-api.example.com
```

它不是 Telegram Mini App 地址，也不是 Siteverify Worker 地址。

### 1. 开始前检查

需要准备：

- 一个已经接入 Cloudflare DNS 的域名，例如 `example.com`；
- 一台已经安装 Docker 与 Docker Compose 的 Linux VPS；
- 已经运行的 tg-watchbot；
- 一个未被其他 DNS 记录占用的 hostname，例如 `bot-api.example.com`。

先在 VPS 确认 tg-watchbot 正常运行：

```bash
cd /opt/tg-watchbot
docker compose ps
curl --fail --silent --show-error http://127.0.0.1:8765/login >/dev/null
```

如果实际安装目录不是 `/opt/tg-watchbot`，请替换成自己的目录。这里失败时先修复 tg-watchbot，不要继续创建 Tunnel。

### 2. 在 Cloudflare 控制台创建 Tunnel

按照 Cloudflare 当前的[远程管理 Tunnel 创建指引](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)：

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)。
2. 进入 `Networking → Tunnels`。
3. 点击 `Create a tunnel`。
4. Connector 选择 `Cloudflared`。
5. Tunnel 名称建议填写 `tg-watchbot-vps`。
6. 点击 `Save tunnel` 或 `Create Tunnel`。
7. 在安装环境中选择 `Docker`。
8. 页面会显示一条包含 `--token eyJ...` 的 Docker 命令。**不要直接把整条命令粘贴到聊天、工单或公开日志**，只在本地临时文本中取出 `eyJ...` 开头的 Tunnel Token。

Tunnel Token 相当于这条 Tunnel 的运行凭证；任何拿到 Token 的人都能运行该 Tunnel。它不是 Cloudflare API Token，也不是 Turnstile Secret。

### 3. 创建独立的 cloudflared Compose 项目

推荐把 Tunnel 放在独立目录，不要把 Tunnel Token 写入 tg-watchbot 的 `.env`：

```bash
sudo install -d -m 700 -o "$USER" -g "$(id -gn)" /opt/tg-watchbot-cloudflared
cd /opt/tg-watchbot-cloudflared
umask 077
nano cloudflared.env
```

在 `cloudflared.env` 中填写刚才复制的 Token：

```dotenv
TUNNEL_TOKEN=<粘贴 eyJ... 开头的 Tunnel Token>
```

保存后确认权限：

```bash
chmod 600 cloudflared.env
```

然后创建 `/opt/tg-watchbot-cloudflared/compose.yaml`：

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: tg-watchbot-cloudflared
    restart: unless-stopped
    network_mode: host
    command: tunnel --no-autoupdate --loglevel info run
    env_file:
      - ./cloudflared.env
```

这里使用 `network_mode: host` 是为了让 cloudflared 容器中的 `127.0.0.1:8765` 指向 VPS 宿主机，与 tg-watchbot 默认的端口绑定直接兼容。此方案适用于 Linux VPS。

Cloudflare 官方支持通过 `TUNNEL_TOKEN` 环境变量运行远程管理 Tunnel。Token 会存在容器配置中，因此只有受信任的管理员才能拥有 Docker 权限；不要把 `docker inspect`、未脱敏的诊断包或 `docker compose config` 输出公开。

### 4. 启动 cloudflared 容器

在 Tunnel 目录执行：

```bash
cd /opt/tg-watchbot-cloudflared
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=100 cloudflared
```

正常情况下：

- 容器状态为 `Up`；
- 日志中出现已注册 Tunnel 连接的记录；
- Cloudflare 控制台中的 Tunnel 状态在稍后变为 `Healthy`。

如果 Tunnel 一直是 `Inactive`、`Down` 或 `Degraded`，先检查容器日志、Token 是否完整，以及 VPS 出站防火墙是否允许 cloudflared 连接 Cloudflare。受限网络还需要检查出站端口 `7844`。

### 5. 添加 Published application 路由

Tunnel 连接成功后，在 Cloudflare 控制台：

1. 进入 `Networking → Tunnels`。
2. 打开刚创建的 `tg-watchbot-vps`。
3. 进入 `Routes`。
4. 点击 `Add route`。
5. 选择 `Published application`。
6. 填写：

| 项目 | 示例 |
|---|---|
| Subdomain | `bot-api` |
| Domain | `example.com` |
| Path | 留空；需要收窄暴露面时可只发布 `/api/verify/turnstile` |
| Service type | `HTTP` |
| Service URL | `http://127.0.0.1:8765` |

7. 保存路由。

Cloudflare 会为 Published application 创建对应的 Tunnel DNS 路由。若提示已有 A、AAAA 或 CNAME 记录，先检查 Cloudflare DNS；不要直接覆盖用途不明的现有记录。

`Service URL` 能使用 `127.0.0.1` 是因为上面的 cloudflared 容器采用 host network。如果你自行改为普通 Docker 网络，应让 cloudflared 与 tg-watchbot 加入同一个网络，并改填：

```text
http://tg-watchbot:8765
```

普通 Docker 网络中不要填写 `http://127.0.0.1:8765`，因为它只会指向 cloudflared 容器自己。

### 6. 验证 Tunnel

若 Published application 未限制 Path，可以先检查登录页：

```bash
curl --fail --silent --show-error https://bot-api.example.com/login >/dev/null
```

再检查验证 API 是否能到达 tg-watchbot：

```bash
curl --silent --show-error --output /dev/null \
  --write-out 'HTTP %{http_code}\n' \
  --request POST \
  https://bot-api.example.com/api/verify/turnstile
```

这里没有提供合法 Telegram `initData` 和 Turnstile token，因此不会返回验证成功。`400`、`401`、`409` 或尚未启用验证时的 `503` JSON 响应，都说明请求已经到达 tg-watchbot；以下结果则需要处理：

| 结果 | 含义与检查方向 |
|---|---|
| `502` | cloudflared 无法连接 `127.0.0.1:8765`；检查 tg-watchbot 状态和 Docker 网络模式 |
| `403` 或跳到 Access 登录页 | Cloudflare Access 拦截了 Worker 请求 |
| Cloudflare Error `1033` | Tunnel 没有健康连接；检查 cloudflared 容器和 Token |
| DNS 解析失败 | Published application 路由或域名 DNS 尚未生效 |

确认后，在验证页面 Worker 中填写：

```text
TG_WATCHBOT_ORIGIN=https://bot-api.example.com
```

只填 HTTPS 根地址，不要附加 `/api/verify/turnstile`。

### 7. Cloudflare Access 注意事项

验证页面 Worker 会以服务端请求访问：

```text
https://bot-api.example.com/api/verify/turnstile
```

配套 Worker 当前不会执行浏览器式 Cloudflare Access 登录。因此：

- 不要给整个 `bot-api.example.com` 套上要求邮箱登录或一次性验证码的 Access 策略；
- 如果管理面板也使用 Tunnel，推荐另建 `admin.example.com`，并只给管理 hostname 配置 Access；
- 如果必须复用同一个 hostname，应依据 [Cloudflare Access 路径规则](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)确保 `/api/verify/turnstile` 不会被交互式登录拦截；
- tg-watchbot 自身仍会对该接口执行 Telegram `initData` 验签、nonce 校验、时效检查和限流。

推荐的 hostname 分工：

```text
admin.example.com    → Tunnel → tg-watchbot（使用 Access 保护管理页面）
bot-api.example.com  → Tunnel → tg-watchbot（供验证页面 Worker 调用）
verify.example.com   → 验证页面 Worker（Telegram Mini App）
```

### 8. 日常维护与 Token 安全

更新 cloudflared：

```bash
cd /opt/tg-watchbot-cloudflared
docker compose pull
docker compose up -d
```

查看状态：

```bash
docker compose ps
docker compose logs --tail=100 cloudflared
```

备份时不要把 `cloudflared.env` 放进 Git 或不加密的共享压缩包。Tunnel Token 泄露后，应立即在 Cloudflare Tunnel 的详情页执行 `Refresh token`，更新 `cloudflared.env`，然后重建容器：

```bash
docker compose up -d --force-recreate
```

Cloudflare 官方建议 Docker 环境使用远程管理 Tunnel；Docker 镜像使用 `--no-autoupdate` 时，应通过定期 `docker compose pull` 获取新版本。

<a id="manual-install"></a>
## 手动安装（Python）

```bash
git clone https://github.com/u1ra/tg-watchbot.git tg-watchbot
cd tg-watchbot
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
chmod 600 .env
```

启动：

```bash
./.venv/bin/python app.py
```

打开面板：

```text
http://127.0.0.1:8765
```

默认账号来自 `.env.example`：

```text
用户名：admin
密码：change-me
```

登录后进入“设置”，填写 Bot Token、管理员 Telegram 数字 chat id、面板账号和密码。保存后重启服务，Bot 才会开始收发 Telegram 消息和发送监控通知。

如需修改面板端口，在“设置”里调整 `WEB_PANEL_PORT` 并重启服务。手动部署默认只监听 `127.0.0.1`；如果改成 `0.0.0.0`，面板会监听所有网卡，请先确认反代鉴权或防火墙策略。

手动跑一次监控：

```bash
./.venv/bin/python app.py --run-once
```

<a id="systemd-install"></a>
## systemd 部署

推荐部署到 `/opt/tg-watchbot`：

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin tg-watchbot || true
sudo mkdir -p /opt/tg-watchbot
sudo chown -R "$USER:$USER" /opt/tg-watchbot

cd /opt/tg-watchbot
git clone https://github.com/u1ra/tg-watchbot.git .
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml

# 先用前台模式打开面板，确认能登录和保存配置
./.venv/bin/python app.py
```

在服务器本机打开：

```text
http://127.0.0.1:8765
```

默认账号来自 `.env.example`：

```text
用户名：admin
密码：change-me
```

如果要从公网访问面板，推荐按照“[Cloudflare Tunnel（Docker 推荐）](#cloudflare-tunnel-docker)”章节部署独立 cloudflared 容器，不需要开放服务器入站端口，也不用把 `WEB_PANEL_HOST` 改成 `0.0.0.0`。管理入口可另外配置 Zero Trust Access，例如只允许自己的邮箱访问。

如果还要启用配套的新用户验证，建议把管理入口和验证 API 入口分成两个 hostname：管理入口继续使用 Access，验证页面 Worker 使用的 Tunnel hostname（例如 `bot-api.example.com`）必须允许其访问 `/api/verify/turnstile`。如果复用一个被 Access 全站保护的 hostname，交互式登录页会拦截 Worker 请求并导致验证失败。

临时调试也可以用 SSH 端口转发：

```bash
ssh -L 8765:127.0.0.1:8765 user@服务器IP
```

然后在自己电脑打开 `http://127.0.0.1:8765`。

在面板“设置”里填好 Bot Token、管理员 ID、面板账号和密码后，停止前台进程，再安装 systemd 服务：

```bash
sudo chown -R tg-watchbot:tg-watchbot /opt/tg-watchbot
sudo chmod 600 /opt/tg-watchbot/.env
sudo cp systemd/tg-watchbot.service /etc/systemd/system/tg-watchbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now tg-watchbot
sudo journalctl -u tg-watchbot -f
```

健康检查：

```bash
curl http://127.0.0.1:8765/health
```

说明：`/restart` 命令在 systemd 下会让进程退出，由 `Restart=on-failure` 自动拉起；如果是手动 `python app.py` 启动，退出后需要自己重新执行启动命令。

## 配置说明

### `.env`

| 变量 | 说明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 创建的 Telegram Bot Token |
| `ADMIN_CHAT_ID` | 管理员 Telegram 数字 chat id；最多 3 个，用逗号分隔 |
| `LOG_LEVEL` | 日志级别，默认 `INFO` |
| `WEB_PANEL_ENABLED` | 是否启用 Web 面板，默认 `true` |
| `WEB_PANEL_HOST` | 面板监听地址，默认 `127.0.0.1`；Docker Compose 会在容器内覆盖为 `0.0.0.0` |
| `WEB_PANEL_PORT` | 面板端口，默认 `8765`；修改后需重启 |
| `WEB_PANEL_USER` | 面板用户名 |
| `WEB_PANEL_PASSWORD` | 面板密码 |
| `WEB_PANEL_SESSION_SECRET` | Session Secret，留空会自动生成并写回 `.env` |
| `WEB_PANEL_COOKIE_SECURE` | 留空时按 HTTPS 自动判断；特殊反代场景可手动设为 `true` / `false` |
| `TG_API_ID` | （可选）Telegram API ID，用于“TG 群监听=用户会话” |
| `TG_API_HASH` | （可选）Telegram API Hash，用于“TG 群监听=用户会话” |
| `TG_API_SESSION` | （可选）Telethon StringSession，用于“TG 群监听=用户会话” |
| `BOT_VERIFICATION_ENABLED` | 是否为新私聊用户启用两阶段验证；默认 `false` |
| `BOT_VERIFICATION_PUBLIC_BASE_URL` | Mini App 的公网 HTTPS 根地址；配套部署时填写“验证页面 Worker”地址，不包含 `/verify/telegram` |
| `BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS` | Telegram Mini App `initData` 最大有效期，默认 `300` 秒 |
| `BOT_VERIFICATION_SESSION_TTL_SECONDS` | Turnstile 入口会话有效期，默认 `600` 秒 |
| `BOT_VERIFICATION_MATH_TTL_SECONDS` | 算数题有效期，默认 `600` 秒 |
| `BOT_VERIFICATION_MATH_MAX_ATTEMPTS` | 算数题最多答错次数，默认 `3` |
| `BOT_VERIFICATION_COOLDOWN_SECONDS` | 达到错误上限后的冷却时间，默认 `600` 秒 |
| `BOT_VERIFICATION_PROMPT_INTERVAL_SECONDS` | 重复验证提示的最小间隔，默认 `15` 秒 |
| `TURNSTILE_SITE_KEY` | Turnstile 前端 sitekey；与验证页面 Worker 使用同一个值，不是 secret |
| `TURNSTILE_VERIFY_ENDPOINT` | 配套 Siteverify Worker 的 HTTPS 根地址，不包含 `/health` |
| `TURNSTILE_VERIFY_AUTH_TOKEN` | 可选但强烈建议；调用 Siteverify Worker 的共享鉴权 Token，必须与 Worker 的 `SITEVERIFY_AUTH_TOKEN` 完全相同 |
| `TURNSTILE_EXPECTED_HOSTNAME` | 验证页面 Worker 的正式 hostname，不含协议和路径；不是 Tunnel hostname |
| `TURNSTILE_EXPECTED_ACTION` | Siteverify 响应中必须匹配的 action，默认 `turnstile-spin-v1` |
| `TURNSTILE_TEST_MODE` | 是否使用 Cloudflare 官方测试 secret；只允许 loopback 地址，默认 `false` |

### 新用户两阶段验证

此功能默认关闭。启用后，首次私聊的新用户必须依次完成：

1. 从 Bot 发出的 Web App 按钮打开 Mini App，并通过 Cloudflare Turnstile。
2. 返回 Telegram，直接回复算数题的数字答案。

管理员可以在 Web 面板的“设置 → 新用户两阶段验证”中修改验证参数；“用户管理”里的共享配置卡片也提供同一组字段。页面会显示当前配置是否完整。可编辑项包括功能开关、Mini App 地址、sitekey、Siteverify Worker 地址、Siteverify 鉴权 Token、预期 hostname/action、各阶段有效期、答错次数、冷却和提示间隔。鉴权 Token 使用密码输入框并只保存在服务端 `.env`；WebUI 不提供生产 Turnstile secret 输入框。Turnstile secret 必须以 `TURNSTILE_SECRET_KEY` 的名称保存在配套 Siteverify Worker 的加密 Secret 中。

“用户管理”列表会显示每个用户当前的验证状态。需要使用现有非管理员账号重新测试完整流程时，可以点击“重置验证（测试）”；该操作只清除目标用户的验证记录和提示间隔缓存，不删除用户资料、备注或历史消息。用户下次私聊 Bot 时会重新进入 Turnstile + 算数题流程。管理员账号始终免验证，因此不会显示重置按钮。

“本地测试模式”和“重置验证（测试）”用途不同：前者让后端使用 Cloudflare 官方测试密钥并限制为 loopback 地址，不改变哪些用户需要验证；后者只重置一个现有非管理员用户的验证状态，可用于生产链路的定向端到端验收。

首次验证前发送的消息不会保存或转发；成功后 Bot 会要求用户重新发送。算数题 10 分钟过期，最多答错 3 次，达到上限后冷却 10 分钟并重新从 Turnstile 开始。管理员不受门禁影响，被封禁用户仍优先执行封禁。升级时数据库中已经存在的用户只会在一次性迁移中标记为历史已验证；之后出现的新用户不会因重启而自动放行。

验证状态、题目和过期时间保存在 SQLite，可跨进程重启恢复。原始 nonce 只以哈希形式入库。后端会验证 Telegram `initData` 的 HMAC 与时效，并检查 Turnstile 的 `success`、`hostname` 和 `action`；浏览器显示成功本身不会使用户通过验证。

#### 本地开发与测试

无需 Cloudflare 账号即可运行自动化测试：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile app.py
```

测试会模拟 Turnstile 成功、失败、超时、hostname/action 不匹配、错误 nonce、过期 `initData`、重复和并发回调，不依赖生产账号或 secret。

如只想在本机查看 Turnstile 测试组件，可临时使用 Cloudflare 的 [官方测试 sitekey](https://developers.cloudflare.com/turnstile/troubleshooting/testing/)：

```dotenv
BOT_VERIFICATION_ENABLED=true
BOT_VERIFICATION_PUBLIC_BASE_URL=http://127.0.0.1:8765
TURNSTILE_SITE_KEY=1x00000000000000000000AA
TURNSTILE_TEST_MODE=true
```

测试模式只允许 `localhost`、`127.0.0.1` 或 `::1`，不会接受公网 hostname。Telegram Web App 按钮仍要求 HTTPS，而且浏览器直接打开时没有可信 Telegram `initData`，因此本机只能检查页面和自动化链路，不能冒充真实 Telegram 端到端通过。不要在连接真实用户的 Bot 上保留这组本地配置。

<a id="turnstile-production"></a>

#### 生产部署：与 `tg-watchbot-verify` 联合使用

生产环境使用配套仓库
[`u1ra/tg-watchbot-verify`](https://github.com/u1ra/tg-watchbot-verify)。
该仓库包含两个必须分别部署的 Cloudflare Worker：

1. **验证页面 Worker**：向 Telegram 用户显示 Turnstile，并把验证表单转发给 tg-watchbot。
2. **Siteverify Worker**：加密保存 Turnstile secret，调用 Cloudflare Siteverify，并校验 `hostname` 和 `action`。

两个 Worker 作用不同，地址不能混用，少部署任意一个都无法完成生产验证。

配套方案的完整请求链路如下：

```text
Telegram
  → 验证页面 Worker（Mini App 页面）
  → Cloudflare Tunnel
  → VPS 上的 tg-watchbot:8765
  → Siteverify Worker（Bearer Token 鉴权）
  → Cloudflare Turnstile Siteverify
  → tg-watchbot 发送算数题
```

[Cloudflare Turnstile 本身可以独立用于未经过 Cloudflare 的网站](https://developers.cloudflare.com/turnstile/get-started/)，并非协议上强制要求 Tunnel；但本项目与配套仓库的标准生产方案使用 Tunnel 作为验证页面 Worker 到 VPS 的安全公网入口。下文均按这套方案配置，不应把 `8765` 直接开放到公网。

下面统一使用三个不同的示例地址：

```text
验证页面 Worker：https://verify.example.com
Cloudflare Tunnel：https://bot-api.example.com
Siteverify Worker：https://tg-watchbot-siteverify.example.workers.dev
```

请替换成自己的真实地址，并始终区分三者用途。

##### 1. 建立 Cloudflare Tunnel

先按照“[Cloudflare Tunnel（Docker 推荐）](#cloudflare-tunnel-docker)”章节，从 Cloudflare 控制台创建 Tunnel、使用独立 Docker 容器启动 cloudflared，并添加 Published application。最终将一个 Tunnel 公网 hostname 指向 tg-watchbot：

```text
https://bot-api.example.com
  → Cloudflare Tunnel
  → http://127.0.0.1:8765
```

保持 `WEB_PANEL_ENABLED=true`，因为验证 API 与 Web 面板由同一个服务提供。继续保留 Docker Compose 默认的 `127.0.0.1:8765` 绑定，不要开放公网端口。若 `cloudflared` 也运行在 Docker 中，容器内的 `127.0.0.1` 指向 cloudflared 容器自己；应使用 host network、`host.docker.internal`，或者让 cloudflared 与 tg-watchbot 加入同一个 Docker 网络。

Tunnel hostname 若受 Cloudflare Access 保护，必须确保 `/api/verify/turnstile` 不会被交互式登录拦截，否则验证页面 Worker 无法转发请求并会返回 `502`。需要保护其他页面时，可以依据 [Cloudflare Access 路径规则](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)为这个精确路径配置更具体的公开策略；tg-watchbot 自身仍会验证 Telegram `initData`、nonce、时效与频率。

验证页面 Worker 中的变量应填写 Tunnel 的 HTTPS **根地址**：

```text
TG_WATCHBOT_ORIGIN=https://bot-api.example.com
```

不要填写 VPS IP、`127.0.0.1`、`8765` 公网地址或 `/api/verify/turnstile` 路径。

##### 2. 创建 Turnstile Widget

在 Cloudflare Turnstile 控制台创建 Widget：

- Widget Mode 选择 **Managed**；
- Pre-clearance 保持关闭；
- 允许的 hostname 填“验证页面 Worker”的最终 hostname，例如 `verify.example.com`；
- 不要填写 Tunnel hostname 或 Siteverify Worker hostname。

创建完成后会得到：

| Cloudflare 字段 | 用途 |
|---|---|
| Site Key / 站点密钥 | 可以公开；填入验证页面 Worker 和 tg-watchbot WebUI |
| Secret Key / 密钥 | 不可公开；只保存到 Siteverify Worker 的 `TURNSTILE_SECRET_KEY` 加密 Secret |

##### 3. 部署验证页面 Worker

[一键部署验证页面 Worker](https://deploy.workers.cloudflare.com/?url=https://github.com/u1ra/tg-watchbot-verify)

部署时配置：

| Worker 变量 | 填写内容 |
|---|---|
| `TG_WATCHBOT_ORIGIN` | Tunnel HTTPS 根地址，例如 `https://bot-api.example.com` |
| `TURNSTILE_SITE_KEY` | Widget 的 Site Key / 站点密钥 |
| `TURNSTILE_EXPECTED_ACTION` | `turnstile-spin-v1` |

部署完成后得到“验证页面 Worker 地址”，例如：

```text
https://verify.example.com
```

这个地址才是 Telegram Mini App 的公网根地址。它不是 Tunnel 地址。

##### 4. 部署 Siteverify Worker

[一键部署 Siteverify Worker](https://deploy.workers.cloudflare.com/?url=https://github.com/u1ra/tg-watchbot-verify/tree/main/siteverify-worker)

部署时配置：

| Worker 变量 | 类型 | 填写内容 |
|---|---|---|
| `TURNSTILE_SECRET_KEY` | **Secret** | Widget 的 Secret Key / 密钥 |
| `SITEVERIFY_AUTH_TOKEN` | **Secret** | 自行生成的随机鉴权 Token；必须与 tg-watchbot 的 `TURNSTILE_VERIFY_AUTH_TOKEN` 完全相同 |
| `TURNSTILE_EXPECTED_HOSTNAME` | 普通变量 | 验证页面 Worker hostname，例如 `verify.example.com` |
| `TURNSTILE_EXPECTED_ACTION` | 普通变量 | `turnstile-spin-v1` |

可以先生成一个 32 字节随机鉴权 Token：

```bash
openssl rand -hex 32
```

`TURNSTILE_SECRET_KEY` 和 `SITEVERIFY_AUTH_TOKEN` 都必须按照 [Cloudflare Workers Secret 指引](https://developers.cloudflare.com/workers/configuration/secrets/)，在 Cloudflare Dashboard 的
`Workers & Pages → Siteverify Worker → Settings → Variables and Secrets`
中保存为加密的 **Secret**，不要保存为普通明文变量。Turnstile secret 不应写入本项目 `.env`、HTML、日志或 Git；Siteverify 鉴权 Token 则需要以另一个变量名 `TURNSTILE_VERIFY_AUTH_TOKEN` 保存到本项目服务端 `.env`，但同样不能进入 HTML、日志、聊天或 Git。

部署完成后得到“Siteverify Worker 地址”，例如：

```text
https://tg-watchbot-siteverify.example.workers.dev
```

##### 5. 填写 tg-watchbot WebUI

打开“设置 → 新用户两阶段验证”，按下表填写：

| WebUI 字段 | 填写内容 |
|---|---|
| 启用新用户验证 | 所有检查完成后最后勾选 |
| 本地测试模式 | 生产环境不要勾选 |
| Mini App 公网根地址 | 验证页面 Worker 地址，例如 `https://verify.example.com` |
| Turnstile Site Key | Widget 的 Site Key / 站点密钥 |
| Spin Siteverify Worker 地址 | Siteverify Worker HTTPS 根地址 |
| Siteverify 鉴权 Token | 与 Worker 的 `SITEVERIFY_AUTH_TOKEN` 完全相同的随机值 |
| 预期 Hostname | 验证页面 Worker hostname，例如 `verify.example.com` |
| 预期 Action | `turnstile-spin-v1` |
| initData 有效期 | 建议保持 `300` 秒 |
| Turnstile 会话有效期 | 建议保持 `600` 秒 |
| 算数题有效期 | 建议保持 `600` 秒 |
| 算数题最多答错次数 | 建议保持 `3` |
| 失败冷却时间 | 建议保持 `600` 秒 |
| 重复提示间隔 | 建议保持 `15` 秒 |

对应的 `.env` 示例为：

```dotenv
BOT_VERIFICATION_ENABLED=true
BOT_VERIFICATION_PUBLIC_BASE_URL=https://verify.example.com
TURNSTILE_SITE_KEY=<正式 sitekey>
TURNSTILE_VERIFY_ENDPOINT=https://tg-watchbot-siteverify.example.workers.dev
TURNSTILE_VERIFY_AUTH_TOKEN=<与 Worker 的 SITEVERIFY_AUTH_TOKEN 相同>
TURNSTILE_EXPECTED_HOSTNAME=verify.example.com
TURNSTILE_EXPECTED_ACTION=turnstile-spin-v1
TURNSTILE_TEST_MODE=false
```

注意：

- `BOT_VERIFICATION_PUBLIC_BASE_URL` 后面不要添加 `/verify/telegram`；
- `TURNSTILE_VERIFY_ENDPOINT` 后面不要添加 `/health`；
- Worker 配置了 `SITEVERIFY_AUTH_TOKEN` 后，这里必须填写完全相同的 `TURNSTILE_VERIFY_AUTH_TOKEN`，否则验证会失败；
- `TURNSTILE_EXPECTED_HOSTNAME` 填验证页面 Worker hostname，不是 Tunnel hostname；
- WebUI 提供 Site Key 和 Siteverify 鉴权 Token，但不提供 Turnstile Secret 输入框，这是有意的安全隔离；
- `TG_WATCHBOT_ORIGIN` 只存在于验证页面 Worker，不填写到 tg-watchbot WebUI。

##### 6. 验收与故障排查

先检查 Siteverify Worker：

```text
https://你的-siteverify-worker地址/health
```

正常应返回类似：

```json
{"ok":true,"service":"tg-watchbot-siteverify","version":"1.0.0"}
```

直接用浏览器打开 Siteverify Worker 根地址返回 `405` 是正常现象，因为根地址只接受 POST。最后必须使用一个**从未私聊过该 Bot 的 Telegram 账号**进行真实验收：

1. 首次私聊后出现验证按钮；
2. 验证页面 Worker 能显示 Turnstile；
3. 完成人机验证后 Bot 发出算数题；
4. 回答正确后要求重新发送原消息；
5. 重新发送的消息能够正常进入原有处理流程。

数据库中已经存在的旧用户会被标记为历史已验证，不能用来测试“首次私聊”门禁。

常见错误：

| 现象 | 优先检查 |
|---|---|
| 验证页面返回 `502` | `TG_WATCHBOT_ORIGIN`、Tunnel 状态、Access 策略、VPS/容器网络 |
| 验证页面返回 `503` | 验证页面 Worker 的 sitekey、action、Tunnel 根地址 |
| Turnstile 不显示或域名错误 | Widget 允许的 hostname 是否为验证页面 Worker hostname |
| Turnstile 完成后没有算数题 | Siteverify Worker secret、预期 hostname/action、tg-watchbot 日志 |
| Siteverify `/health` 正常但验证失败 | 是否把 Siteverify 根地址误填成 `/health`，或混用了两个 Worker 地址 |
| Siteverify 返回 `401` 或配置后突然全部失败 | Worker 的 `SITEVERIFY_AUTH_TOKEN` 与本项目的 `TURNSTILE_VERIFY_AUTH_TOKEN` 是否完全相同 |

Cloudflare 要求所有 token 都经过[服务端 Siteverify](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)，且 token 只有 5 分钟有效并只能使用一次。本项目的 `/api/verify/turnstile` 是验证页面 Worker 经 Tunnel 调用的精确公共入口；管理面板其他路由仍要求登录。缺少必要配置、验证端超时或返回异常时会失败关闭，不会自动放行用户。

配套 Worker 的变量、部署按钮和最新故障排查以
[`tg-watchbot-verify` README](https://github.com/u1ra/tg-watchbot-verify#readme)
为准。

### `config.yaml`

Bot 扩展配置示例：

```yaml
bot:
  rate_limit:
    window_seconds: 10
    max_messages: 3
  spam_filter:
    enabled: true
    auto_block: true
    keywords:
      - 投资
      - 博彩
      - 空投
  quick_replies:
    - title: 已收到
      text: 你好，消息已收到，我稍后处理。
```

TG 群关键词监听（可选，默认关闭）：

```yaml
group_monitors:
  - name: TG 群关键词监听
    enabled: false
    listen_source: bot
    chat_id: -1001234567890
    keywords:
      - VPS
      - 优惠
    exclude_keywords:
      - 求带
    notify_telegram: true
    summary_mode: template
    ai_base_url: ""
    ai_api_key: ""
    ai_model: gpt-4o-mini
    ai_interface: responses
    ai_temperature: 0.2
    ai_timeout_seconds: 30
    ai_prompt: ""
    ai_min_interval_seconds: 30
    ai_dedupe_window_seconds: 300
```

- 命中 `keywords` 且未命中 `exclude_keywords` 时，会给管理员发送摘要。
- TG 群监听页面会展示“已发现群聊”（Bot 收到过消息的群），可直接点“用此群创建监听”自动填入 `chat_id`。
- `listen_source` 支持：
  - `bot`：默认，使用 Bot 接收群消息（需把 Bot 拉进群）
  - `user_session`：使用用户会话接收群消息（适合 Bot 无法入群）
- `summary_mode` 支持：
  - `template`：固定模板摘要（默认）
  - `ai`：调用 AI 生成摘要（在 TG 群监听页面可视化配置）
- `ai_prompt` 可填自定义总结提示词；留空使用内置默认提示词。
- `ai_interface` 支持：
  - `responses`：`/v1/responses`
  - `chat`：`/v1/chat/completions`
- `ai_min_interval_seconds`：同一个群监听最小推送间隔（防刷屏）
- `ai_dedupe_window_seconds`：相同内容摘要去重窗口（防重复）
- 机器人想收到群里普通消息，需要在 `@BotFather` 执行 `/setprivacy` 关闭隐私模式。
- 若使用 `listen_source=user_session`，需在设置页填写 `TG_API_ID`、`TG_API_HASH`、`TG_API_SESSION` 后重启。

更新代码（`/update`）已支持安全检查：
- 显示本地/远端 commit、ahead/behind、工作区是否干净
- 只允许 `ff-only` 更新，工作区有未提交改动会拒绝更新
- 自动记录上次更新前的回滚点，并支持一键回滚

监控数据自动清理示例：

```yaml
cleanup:
  enabled: true
  interval_minutes: 60              # 每多少分钟执行一次清理
  monitor_message_delete_after_minutes: 60  # 监控通知消息发送后多久删除；0 表示不删除
  monitor_retention_minutes: 1440   # RSS/网站监控状态保留多久
```

清理范围只包括：

- `monitor_state`：网站/RSS 条目状态、价格/库存状态；
- `sent_events`：监控推送去重记录；
- `monitor_messages`：等待到期删除的 Telegram 监控通知消息队列。

不会删除：

- `users`；
- `message_map`；
- `inbox_messages`；
- 任何双向对话/客服消息记录。

RSS 示例：

```yaml
monitors:
  - name: NodeSeek 新帖
    type: rss
    url: https://rss.nodeseek.com/
    interval_seconds: 30
    keywords:
      - VPS
      - 优惠
    exclude_keywords:
      - 出号
    authors: []
    categories: []
    notify_on:
      keyword_match: true
      new_item: true
      price_change: false
      stock_change: false
    notify_telegram: true
    forum: true
```

网页示例：

```yaml
monitors:
  - name: Example Deals
    type: web
    url: https://example.com/deals
    interval_seconds: 300
    keywords:
      - discount
    selectors:
      item: article, .deal, li
      title: h1, h2, h3, a
      link: a
      price: .price
      stock: .stock
    notify_on:
      keyword_match: true
      new_item: true
      price_change: true
      stock_change: true
    notify_telegram: true
```

## 管理命令

管理员在 Telegram 里可用：

```text
/reply <user_id> <内容>
/sendpic <user_id> [图片说明]
/block <user_id>
/unblock <user_id>
/note <user_id> <备注>
/who <user_id>
/spamwords
/spamadd <关键词>
/spamdel <关键词>
/cancel
```

也可以直接“回复 Bot 转发给管理员的用户消息”，Bot 会按映射把回复发回原用户。

## 面板路由

| 路由 | 说明 |
|---|---|
| `/` | 监控列表 |
| `/monitor/new` | 新增监控 |
| `/monitor/templates` | 论坛模板 |
| `/monitor/bulk` | 批量新增 |
| `/monitor/{idx}/preview` | 预览抓取结果，不写入状态、不推送 |
| `/monitor/{idx}/run` | 手动检查单个监控 |
| `/run-once` | 手动检查全部监控 |
| `/yaml` | YAML 高级编辑 |
| `/settings` | `.env` 设置和监控清理策略 |
| `/send` | 主动发消息给已私聊过 Bot 的用户 |
| `/inbox` | 收件箱 |
| `/users` | 用户管理 |
| `/rules` | 私聊广告拦截规则 |
| `/replies` | 快捷回复模板 |
| `/monitor/events` | 监控推送历史 |
| `/channel-media` | 频道媒体监控 |
| `/channel-media/{id}/pause` | 暂停频道监控 |
| `/channel-media/{id}/resume` | 恢复频道监控 |
| `/channel-media/{id}/check` | 手动下载频道媒体 |
| `/channel-media/{id}/download` | 查看下载记录 |
| `/config/export` | 导出 / 导入 `config.yaml` |
| `/logs` | 日志 |
| `/health` | 健康检查 |

## 注意事项

- Telegram Bot 不能主动私聊陌生人；对方必须先给 Bot 发过 `/start` 或任意消息。
- 对公网暴露 Web 面板前，务必改默认密码，并优先使用反代鉴权或 Tunnel。
- RSS/Web 监控最低可设 1 秒，默认 30 秒；实际部署建议按目标站承受能力调高，避免被限流。
- 媒体消息当前只保证记录文本/说明和转发状态；转发失败后的媒体补发需要额外做本地附件存储。

## License

本项目采用非商业授权。

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

商业使用请先联系作者获得授权。
