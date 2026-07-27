# tg-watchbot 客制化开发计划

> 文档状态：本地开发完成，等待服务器部署阶段
> 最后更新：2026-07-27
> 当前检查点：`P6.1` 完成；下一步仅在用户提供正式域名并授权后执行 `P7`
> 用途：实现普通 Web/RSS 监控排除关键词，以及新用户首次私聊的 Turnstile + 算数两阶段验证。

## 1. 已确认需求

### 1.1 普通监控排除关键词

- 在普通 Web/RSS 监控的新增、编辑表单中，紧接现有“关键词（一行一个）”文本框，新增一个同样尺寸和样式的“排除关键词（一行一个）”文本框。
- 表单字段名使用 `exclude_keywords`。
- 每行一个排除词，继续复用现有 `parse_lines()` 行解析方式。
- 保存后写入对应监控项的 `exclude_keywords` 数组。
- 编辑已有监控时必须回显已有排除词，不能在保存时丢失 YAML 中原有配置。
- 排除词继续沿用现有匹配语义：不区分大小写，匹配标题、正文、作者和分类；命中任意一个排除词即跳过该条目。
- 本次不改变 TG 群监听的排除词功能；它已经存在。
- 本次不扩展“批量新增”格式；只处理用户截图所示的普通新增/编辑表单。

### 1.2 新用户首次私聊验证

- 验证对象：功能上线后首次出现的新用户。
- 已存在于数据库中的老用户一次性标记为历史已验证，不补做验证。
- 管理员不进入验证流程。
- 被封禁用户优先执行封禁逻辑，不显示验证入口。
- 验证通过后对该 Telegram 用户永久有效，除非未来人工重置；本次不开发重置 UI。
- 第一阶段：Cloudflare Turnstile。
- 第二阶段：Telegram 私聊中的算数题。
- 用户验证前发来的第一条消息不保存、不进入收件箱、不转发；验证完成后提示用户重新发送。
- 算数题使用 1～20 范围内的加减法，减法保证结果不为负数。
- 算数题有效期为 10 分钟。
- 最多答错 3 次；达到上限后冷却 10 分钟，再从 Turnstile 阶段重新开始。
- 验证过程中的消息不进入现有广告关键词、客服收件箱和管理员转发链路。
- 验证完成后的消息继续使用现有封禁、限流、广告过滤、入库和转发逻辑。

## 2. 当前项目基线

### 2.1 已有能力

- `app.py:item_blocked()` 已读取普通监控的 `exclude_keywords` 并在命中时跳过条目。
- `config.example.yaml` 已展示普通监控和 TG 群监听的 `exclude_keywords`。
- TG 群监听的 WebUI、表单解析和保存链路已经支持排除词，可作为普通监控表单的实现参考。
- 项目已有 FastAPI，可承载验证页面和验证 API。
- 项目已有 SQLite `users` 表、`app_meta` 表和逐次轻量迁移模式。
- 项目已有 aiogram Router、私聊 `/start` 处理器和普通消息兜底处理器。
- 项目已有 `httpx`，不需要为了 Turnstile 验证新增 HTTP 客户端依赖。

### 2.2 已知缺口

- 普通监控表单没有 `exclude_keywords` 文本框。
- `monitor_from_form()`、新增接口、编辑接口没有接收和保存 `exclude_keywords`。
- 当前编辑普通监控会重建监控配置，因此通过 YAML 设置的排除词可能被 WebUI 保存操作删除。
- `users` 表没有验证状态；当前新用户会直接进入客服转发流程。
- 当前多个命令处理器位于普通消息兜底处理器之前，只在 `/start` 和兜底函数中分别加判断容易产生遗漏，应使用统一私聊门禁。
- FastAPI 登录中间件目前只放行少数固定公共路径，验证页面/API 必须显式、安全地加入公共路由规则。
- 当前 Docker 端口只映射到主机 `127.0.0.1`。完整 Telegram Mini App 联调需要后续提供公网 HTTPS 地址；本地阶段以单元测试、FastAPI 测试客户端和 Turnstile 测试模式为主。

### 2.3 基线验证

- 计划创建前运行：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
- 结果：41 项测试通过。
- 计划创建前 Git 工作区无业务代码改动。

## 3. 目标架构

### 3.1 验证状态机

建议使用独立表 `user_verifications`，避免把短期挑战字段全部塞进 `users`：

| 状态 | 含义 | 允许的下一状态 |
|---|---|---|
| 无记录 | 新用户尚未启动验证 | `pending_turnstile` |
| `pending_turnstile` | 等待完成 Turnstile | `pending_math`、重新生成 Turnstile 会话 |
| `pending_math` | Turnstile 已通过，等待算数答案 | `verified`、`cooldown`、过期后回到 `pending_turnstile` |
| `cooldown` | 算数错误达到上限 | 冷却到期后 `pending_turnstile` |
| `verified` | 永久通过 | 保持 `verified` |

建议字段：

```text
user_id                 INTEGER PRIMARY KEY
status                  TEXT NOT NULL
turnstile_nonce_hash    TEXT
turnstile_expires_at    REAL
math_question           TEXT
math_answer             INTEGER
math_attempts           INTEGER NOT NULL DEFAULT 0
math_expires_at         REAL
cooldown_until          REAL
verified_at             TEXT
verification_method     TEXT
created_at              TEXT NOT NULL
updated_at              TEXT NOT NULL
```

约束：

- 数据库只保存 Turnstile nonce 的哈希，不保存发给客户端的原始 nonce。
- 算数答案只短期存在，并受过期时间保护；验证完成、失败冷却或重新开始时清空。
- 所有状态转换使用短事务并检查当前状态，防止页面重复提交或并发消息造成越级。
- SQLite 继续使用独立连接；必要时增加合理的 `busy_timeout`，避免 FastAPI 回调和 Telegram polling 同时写入时立即失败。

### 3.2 老用户一次性迁移

不能在每次启动时无条件把 `users` 中的用户设为已验证，否则新用户重启后也会被错误放行。

迁移步骤：

1. 创建 `user_verifications` 表。
2. 检查 `app_meta` 中是否存在 `user_verification_legacy_migration_v1`。
3. 仅在标记不存在时，把当时 `users` 表中的全部用户插入为：
   - `status = verified`
   - `verification_method = legacy`
   - `verified_at = 当前时间`
4. 在同一事务写入迁移完成标记。
5. 以后新用户不会因进程重启而被自动标记为已验证。

### 3.3 私聊门禁

门禁必须覆盖所有普通用户私聊更新，而不是只改 `/start`：

```text
收到私聊消息
  -> 是否管理员：是 -> 现有管理员流程
  -> 是否封禁：是 -> 返回封禁提示
  -> 是否 verified：是 -> 现有用户消息流程
  -> pending_math：解析当前消息为答案
  -> cooldown：返回冷却提示
  -> 其他状态：创建或复用 Turnstile 会话，发送验证按钮
```

实现原则：

- 优先考虑 aiogram 消息中间件或一个明确的统一门禁函数，确保所有普通用户命令和消息都经过相同检查。
- `/start` 只负责触发/展示当前验证阶段，不直接把用户视为已连接客服。
- 验证前的文字、图片、文件、语音等全部丢弃，并明确提示验证后重新发送。
- 重复发送消息时不要无限创建新 nonce 或重复刷验证按钮；活动会话可复用，并增加提示发送频率限制。
- `pending_math` 收到非文本内容时不计错误次数，只提示输入数字。
- Bot 重启后根据 SQLite 恢复阶段；不依赖内存字典。

### 3.4 Turnstile Mini App

新增独立、最小化的验证页面，不复用管理面板页面，也不暴露面板导航：

```text
Telegram 私聊按钮
  -> HTTPS Mini App 页面
  -> 页面提交 Telegram initData + 会话 nonce + Turnstile token
  -> tg-watchbot 后端验证 Telegram 身份和会话
  -> 可信服务端调用 Turnstile 验证端
  -> 成功后原子切换为 pending_math
  -> Bot 发送算数题
```

安全要求：

- 使用 `InlineKeyboardButton.web_app`，正式环境 URL 必须为 HTTPS。
- 服务端必须校验 Telegram `initData` 的 HMAC、`auth_date` 新鲜度和用户 ID。
- `initDataUnsafe` 只能用于页面显示，不能用于服务端授权。
- URL 中的随机 nonce 必须与数据库哈希匹配、未过期且属于同一 Telegram 用户。
- Turnstile token 不从浏览器直接调用 Siteverify；浏览器只提交给本项目后端。
- 服务端验证结果必须检查：
  - `success == true`
  - 预期 `hostname`
  - 预期 `action`
  - 当前会话尚未被使用
- Turnstile token 按单次使用处理；失败、过期或重复时要求刷新组件。
- 页面中的 Turnstile 片段包含 `data-action="turnstile-spin-v1"`。
- CSP 至少允许 `https://challenges.cloudflare.com` 的脚本、frame 和必要连接。
- 验证页面/API 是公共入口，但管理面板其余路径继续要求登录。
- 公共 API 增加请求体大小限制、超时、基础速率限制和无敏感信息错误响应。

### 3.5 本地与正式环境分离

本地开发阶段：

- 不创建正式 Turnstile widget。
- 不部署 Cloudflare Worker。
- 不写入真实 Turnstile secret。
- 单元测试中模拟 Turnstile 验证响应。
- 可选手工联调使用 Cloudflare 官方测试 sitekey/测试 secret，并要求显式启用测试模式。
- 测试模式默认关闭；缺少配置时验证流程必须失败关闭，不能自动放行。
- 未提供公网 HTTPS 时，不把“Telegram 内完整 Mini App 联调”列为本地完成条件。

服务器部署阶段：

- 用户提供最终 HTTPS 域名。
- 再确认 widget hostname：正式域名，并按需要单独配置开发/测试环境。
- 再确认采用 Cloudflare Spin 托管 Siteverify Worker，或由服务端直接调用 Siteverify；无论采用哪一种，浏览器都不能直接决定验证结果。
- 创建 widget、配置 secret/Worker 时必须单独获得确认。
- 真实 secret 不进入 Git、不显示在前端、不写入计划文件或聊天记录。
- 使用生产 sitekey 前，验证测试 key 不会在正式配置中被接受。

## 4. 配置设计

建议增加以下环境变量；最终名称可在实施时保持一致：

```text
BOT_VERIFICATION_ENABLED=false
BOT_VERIFICATION_PUBLIC_BASE_URL=
BOT_VERIFICATION_INITDATA_MAX_AGE_SECONDS=300
BOT_VERIFICATION_SESSION_TTL_SECONDS=600
BOT_VERIFICATION_MATH_TTL_SECONDS=600
BOT_VERIFICATION_MATH_MAX_ATTEMPTS=3
BOT_VERIFICATION_COOLDOWN_SECONDS=600
BOT_VERIFICATION_PROMPT_INTERVAL_SECONDS=15
TURNSTILE_SITE_KEY=
TURNSTILE_VERIFY_ENDPOINT=
TURNSTILE_EXPECTED_HOSTNAME=
TURNSTILE_EXPECTED_ACTION=turnstile-spin-v1
TURNSTILE_TEST_MODE=false
```

配置原则：

- `.env.example` 只记录空值、非敏感默认值和注释。
- 不在 `config.example.yaml`、HTML、日志或测试快照中写入生产 secret。
- `BOT_VERIFICATION_ENABLED=false` 时保持现有行为，便于紧急回退。
- `BOT_VERIFICATION_ENABLED=true` 但必要配置缺失时，启动日志明确报错，用户验证失败关闭，不允许绕过。
- 正式部署时 `BOT_VERIFICATION_PUBLIC_BASE_URL` 必须是 HTTPS。
- 测试模式必须同时满足显式开关和非生产环境限制，避免误带到正式部署。

## 5. 分阶段实施

每一阶段都必须做到：改动范围小、补测试、运行相关测试、更新本文档检查点，然后再进入下一阶段。

### P0：需求与架构冻结

- [x] 确认 Turnstile。
- [x] 确认老用户免验证。
- [x] 确认验证永久有效。
- [x] 确认首条消息丢弃并要求重发。
- [x] 确认算数题范围、有效期、尝试次数和冷却策略。
- [x] 确认排除词只添加到截图所示的普通监控新增/编辑表单。
- [x] 创建本开发计划。

完成条件：本文档存在，下一阶段入口明确。

### P1：普通监控排除关键词

预计修改：

- `app.py`
- `tests/test_monitor_message_cleanup.py`

任务：

- [x] 在 `monitor_form_html()` 中读取并回显 `exclude_keywords`。
- [x] 在关键词框下方增加同样样式的全宽 textarea。
- [x] 扩展 `monitor_from_form()` 参数和返回字典。
- [x] 扩展普通监控 create/save/common 保存链路。
- [x] 保证没有排除词时保存为空数组。
- [x] 保证从 YAML 读取后再经 WebUI 保存不会丢失排除词。
- [x] 不修改批量新增格式。
- [x] 增加表单字段契约、解析保存、编辑回显和实际拦截测试。

完成条件：

- 新增/编辑表单包含 `name=exclude_keywords`。
- 保存后 YAML 正确保留该列表。
- 现有与新增测试全部通过。

### P2：验证数据模型与纯函数

预计修改：

- `app.py`
- `tests/test_monitor_message_cleanup.py`

任务：

- [x] 创建 `user_verifications` 表和必要索引。
- [x] 实现只运行一次的老用户 grandfather 迁移。
- [x] 实现读取、创建、更新验证状态的数据库函数。
- [x] 实现安全 nonce 生成、哈希、过期检查。
- [x] 实现算数题生成，保证取值范围和非负减法。
- [x] 实现正确、错误、过期、冷却状态转换。
- [x] 对状态转换增加并发/重复提交保护。
- [x] 测试重启后状态持久化和迁移不会误放行新用户。

完成条件：

- 状态机可在不启动 Telegram/FastAPI 的情况下通过纯单元测试验证。
- 老用户只在首次迁移时标为 `legacy` verified。

### P3：Telegram 私聊统一门禁

预计修改：

- `app.py`
- `tests/test_monitor_message_cleanup.py`

任务：

- [x] 增加验证门禁，覆盖 `/start`、其他用户命令和普通私聊消息。
- [x] 管理员和群组消息保持原行为。
- [x] 被封禁用户不进入验证。
- [x] 未验证用户消息不创建 `inbox_messages`，不调用管理员转发。
- [x] 创建/复用活动 Turnstile 会话并发送 Web App 按钮。
- [x] `pending_math` 状态处理算数答案。
- [x] 通过后提示“验证成功，请重新发送你的消息”。
- [x] 达到错误上限时进入 10 分钟冷却。
- [x] 添加验证提示自身的防刷频率限制。

完成条件：

- 各消息类型都不能绕过门禁。
- 已验证用户的现有客服链路无行为回归。

### P4：Mini App 页面与 Turnstile 服务端验证

预计修改：

- `app.py`
- `tests/test_monitor_message_cleanup.py`

任务：

- [x] 新增最小验证 HTML 页面。
- [x] 加载 Telegram Web App SDK 和 Turnstile widget。
- [x] 使用与现有面板一致但隔离的基础视觉风格，优先移动端。
- [x] 增加 Telegram `initData` 服务端验签和 `auth_date` 检查。
- [x] 增加 nonce、用户 ID、状态、过期时间绑定校验。
- [x] 把 Turnstile token 发送到可信服务端验证端，设置短超时。
- [x] 检查 `success`、hostname 和 action。
- [x] 成功后原子进入 `pending_math` 并让 Bot 发送题目。
- [x] Bot 暂时不可用时保存题目；用户下次发消息时重新展示同一道有效题目。
- [x] 精确放行验证页面/API 路径，不放宽其他面板路径。
- [x] 添加 CSP、安全响应头、错误处理和速率限制。

完成条件：

- 模拟成功响应能够推进到 `pending_math`。
- 模拟失败、超时、错误 hostname/action、旧 initData、错误 nonce 和重放均不能推进状态。
- 管理面板鉴权未被绕过。

### P5：配置、说明与本地联调

预计修改：

- `.env.example`
- `README.md`
- 视实现需要修改 `config.example.yaml`
- 测试文件

任务：

- [x] 增加环境变量示例和本地测试说明。
- [x] 说明 localhost 能做的测试范围，以及 Telegram Mini App 需要 HTTPS。
- [x] 说明生产部署前必须替换测试 key。
- [x] 说明 Turnstile secret/Worker 配置不进入 Git。
- [x] 说明老用户、新用户、首条消息和算数失败行为。
- [x] 使用 FastAPI 测试客户端完成页面/API 本地联调。
- [x] 使用官方测试 key 做一次联网测试；测试不是默认流程、不依赖生产账号。

完成条件：

- 新开发者仅靠 README 和 `.env.example` 能启动本地测试。
- 不需要真实 Cloudflare 账号即可完成自动化测试。

### P6：完整回归与交付检查

任务：

- [x] 运行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`。
- [x] 运行 `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile app.py`。
- [x] 运行 `git diff --check`。
- [x] 检查 `git status --short`，确认没有数据库、日志、`.env`、缓存或密钥进入变更。
- [x] 审查所有公共验证路由和管理面板鉴权边界。
- [x] 审查日志，确保不记录 Bot token、Turnstile token、initData、原始 nonce 或 secret。
- [x] 审查验证关闭开关和失败关闭行为。
- [x] 更新本文档最终检查点和测试结果。

完成条件：

- 所有测试通过。
- 没有未解释的文件变化。
- 本地开发目标完成；生产部署仍保持未执行状态。

### P6.1：验证参数管理 WebUI

此阶段由用户在 P6 完成后追加，仍属于本地开发范围。

- [x] 在“设置向导”新增“新用户两阶段验证”配置区。
- [x] 在“用户管理”的共享配置卡片复用同一组字段。
- [x] 支持修改验证开关、测试模式、Mini App 地址、sitekey、Spin Worker 地址和预期 hostname/action。
- [x] 支持修改 `initData`、Turnstile 会话、算数题有效期、最大错误次数、冷却和提示间隔。
- [x] 显示当前配置完整性诊断和生产/测试模式警告。
- [x] 不提供生产 Turnstile secret 输入框。
- [x] 保存时规范化布尔值、数字、URL 和 hostname。
- [x] 表单未提交的既有参数与其他自定义 `.env` 键不会被删除。
- [x] 两个保存路由使用相同的规范化与持久化逻辑。
- [x] 完成单元测试和真实 FastAPI `TestClient` 保存/回显联调。

完成条件：

- 管理员无需手工编辑 `.env` 即可维护全部非敏感验证参数。
- 生产 secret 仍只存在于 Spin Worker。
- 保存其他面板设置不会意外关闭验证或删除部署自定义环境变量。

### P7：服务器部署与真实 Turnstile 联调

此阶段不属于当前本地开发授权范围，必须在用户部署服务器并提供域名后单独开始。

- [ ] 确认最终域名和 HTTPS。
- [ ] 确认 Cloudflare 账号及部署方式。
- [ ] 创建或选用 Turnstile widget。
- [ ] 配置正式 hostname、sitekey 和服务端验证端。
- [ ] 如使用 Turnstile Spin，按其流程部署托管 Siteverify Worker。
- [ ] 以安全方式配置 secret；不粘贴进代码、计划或日志。
- [ ] 使用真实 Telegram 客户端完成 Mini App 两阶段端到端测试。
- [ ] 验证移动端、桌面端、重复点击、过期、网络失败和 Bot 重启场景。
- [ ] 确认正式环境没有测试 key 或测试模式。

## 6. 测试矩阵

### 6.1 排除关键词

- 无排除词：行为与当前一致。
- 单个排除词：命中标题、正文、作者、分类时均跳过。
- 多个排除词：命中任意一个即跳过。
- 大小写不同：仍能命中。
- 只有包含关键词、没有排除词：正常通知。
- 同时命中包含词和排除词：排除优先。
- YAML 已有排除词：WebUI 编辑其他字段后仍保留。
- HTML 特殊字符：正确转义并可往返保存。

### 6.2 老用户与新用户

- 迁移前已有用户：标记为 `legacy` verified。
- 迁移后新用户：无验证记录时必须进入 Turnstile。
- 重启服务：新用户不会被误标为历史用户。
- 已验证用户：重启后保持验证。
- 管理员：不受验证门禁影响。
- 被封禁用户：封禁优先。

### 6.3 Turnstile

- 有效 initData + 正确 nonce + 成功 token：进入算数阶段。
- initData 签名错误、过期或用户不匹配：拒绝。
- nonce 错误、过期、重复使用或属于其他用户：拒绝。
- Turnstile 缺 token、失败、超时、重复 token：拒绝。
- hostname/action 不匹配：拒绝。
- 同一成功回调并发提交：只能发生一次状态推进和一次题目发送。
- 缺少正式配置且验证功能开启：失败关闭。
- 测试模式未显式开启：不得接受测试旁路。

### 6.4 算数阶段

- 正确答案：永久 verified。
- 错误 1～2 次：保留同一道未过期题目并提示剩余次数。
- 第 3 次错误：进入 10 分钟冷却并清空题目。
- 非数字文本或媒体：提示输入数字，不消耗次数。
- 题目过期：回到 Turnstile。
- 冷却期间重复发消息：不创建新挑战。
- 冷却结束：重新从 Turnstile 开始。
- 验证成功后：此前消息不存在于收件箱，用户重新发送的新消息正常转发。

### 6.5 回归

- TG 群监听不受影响。
- 管理员命令和回复流程不受影响。
- 现有广告过滤与普通限流在已验证用户上仍生效。
- Web 面板登录、Cookie 和其他路由鉴权不受影响。
- 监控新增、编辑、预览、手动检查和调度不受影响。
- SQLite 清理任务不会删除用户验证状态。

## 7. 风险与应对

| 风险 | 应对 |
|---|---|
| 只在 `/start` 加判断，被其他命令路径绕过 | 使用统一私聊门禁并测试所有处理器顺序 |
| WebUI 编辑导致 YAML 字段丢失 | 为 `exclude_keywords` 做完整表单往返测试 |
| 每次启动都把新用户误当老用户 | 使用 `app_meta` 一次性迁移标记 |
| Turnstile 前端显示成功但未服务端验证 | 后端必须读取可信验证结果后才推进状态 |
| 验证链接被转发给他人 | Telegram initData、用户 ID、随机 nonce 三重绑定 |
| token/nonce 重放 | 单次状态转换、nonce 哈希、过期和并发保护 |
| Bot 重启导致挑战丢失 | 所有阶段与题目写入 SQLite |
| FastAPI 与 polling 并发写 SQLite | 短事务、WAL、必要的 busy timeout 和重试边界 |
| 验证 API 被刷 | 请求体限制、端点限流、会话冷却、短超时 |
| 测试 key 进入生产 | 显式测试模式、生产启动检查和部署清单 |
| Turnstile WebView 兼容问题 | 延后到有 HTTPS 域名时做真实客户端矩阵测试 |
| 算数题可被自动程序计算 | 明确其定位是第二层反垃圾摩擦，继续保留 Turnstile、限流和广告过滤 |

## 8. 额度中断与断点续作规范

无论是模型上下文、调用额度还是单次开发时间不足，都按以下规则停下和恢复。

### 8.1 阶段边界

- 一次只执行一个 `P` 阶段。
- 优先把一个阶段做到“代码 + 测试 + 文档检查点”闭环，再进入下一阶段。
- 不在额度明显不足时同时展开数据库、Telegram 和 Web 三条链路。
- 不为了赶进度跳过测试或把真实 secret 临时写入文件。

### 8.2 每次暂停前必须更新

在本文档末尾“执行日志”追加一条记录，至少包括：

- 当前阶段和完成百分比。
- 已完成的具体任务。
- 修改过的文件。
- 最后一次成功的测试命令与结果。
- 当前失败测试或已知问题。
- 下一步应执行的精确动作。
- `git status --short` 摘要。
- 是否存在未完成但可运行的代码。

若额度已经非常紧张，最低限度也要写：

```text
当前阶段：
最后完成：
最后测试：
下一步：
风险：
```

### 8.3 下次恢复顺序

新的开发会话不要依赖之前聊天上下文，按顺序执行：

1. 完整阅读本文件。
2. 查看“当前检查点”和最新“执行日志”。
3. 运行 `git status --short` 和 `git diff --stat`。
4. 阅读所有有变更文件的 diff，不覆盖用户或其他会话留下的改动。
5. 重新运行日志中最后一个相关测试。
6. 从“下一步应执行的精确动作”继续。
7. 完成阶段后更新复选框、检查点和执行日志。

### 8.4 中断时的代码要求

- 尽量停在测试通过的提交前状态；未经用户要求不自动创建 Git commit。
- 如果只能停在测试未通过状态，必须记录失败测试名称和预期修复位置。
- 不使用 `git reset --hard`、`git checkout --` 等命令丢弃现场。
- 不删除或覆盖无法确认来源的工作区改动。
- 数据库迁移必须保持幂等；即使进程在迁移中断后重启，也不能重复 grandfather 新用户。

## 9. 预计文件变更

| 文件 | 计划用途 |
|---|---|
| `app.py` | 排除词表单/保存、验证表、状态机、Telegram 门禁、Mini App 页面/API |
| `tests/test_monitor_message_cleanup.py` | 扩展现有表单、数据库、Telegram 和 FastAPI 契约测试 |
| `.env.example` | 验证与 Turnstile 非敏感配置说明 |
| `config.example.yaml` | 仅在最终决定把非敏感验证策略放入 YAML 时调整 |
| `README.md` | 使用行为、本地测试和服务器部署说明 |
| `DEVELOPMENT_PLAN.md` | 阶段状态、断点和执行日志 |

原则：项目当前是单文件应用，本次先保持结构一致；若 `app.py` 因测试困难需要拆分，必须先在执行日志说明理由和迁移范围，不顺手做无关重构。

## 10. 完成定义

本地开发完成需要同时满足：

- 普通监控新增/编辑页出现与关键词框同款的排除关键词框。
- 排除词可正确保存、回显并在监控执行中优先拦截。
- 老用户免验证，新用户必须依次通过 Turnstile 和算数题。
- 验证前消息不保存、不转发；成功后要求重新发送。
- 验证状态可跨重启恢复，错误和冷却规则符合约定。
- Turnstile 只信任服务端验证结果，身份与 Telegram 用户绑定。
- 管理面板鉴权没有因公共验证路由而放宽。
- 自动化测试全部通过，无密钥、数据库或运行产物进入 Git。
- README 明确本地完成范围和真实 HTTPS 部署后的待办。

不属于本地完成条件：

- 创建真实 Cloudflare widget。
- 部署正式 Cloudflare Worker。
- 配置生产域名、证书或 Tunnel。
- 在真实生产 Telegram Bot 上开启验证。

## 11. 执行日志

### 2026-07-27 — P0

- 当前阶段：`P0`，100%。
- 已完成：需求确认、代码基线梳理、Turnstile/Telegram 约束核对、阶段拆分和断点规范。
- 修改文件：仅新增 `DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，41 项通过。
- 已知问题：业务代码尚未开始；没有公网 HTTPS 时无法完成真实 Telegram Mini App 端到端联调。
- 下一步：执行 `P1`，只实现普通监控 `exclude_keywords` 表单、保存链路和对应测试。
- 预期工作区：仅 `DEVELOPMENT_PLAN.md` 为新增文件。
- 可运行性：业务代码未变，保持原基线状态。

### 2026-07-27 — P1

- 当前阶段：`P1`，100%。
- 已完成：普通监控排除关键词表单、回显、解析、创建/编辑保存链路和拦截测试；批量新增格式保持不变。
- 修改文件：`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，43 项通过。
- 已知问题：用户验证数据模型尚未实现。
- 下一步：执行 `P2`，创建验证表、一次性老用户迁移、nonce 和算数状态机纯函数及测试。
- 工作区摘要：`app.py` 与测试文件已修改，`DEVELOPMENT_PLAN.md` 为新增文件。
- 可运行性：当前业务代码和测试均可运行。

### 2026-07-27 — P2

- 当前阶段：`P2`，100%。
- 已完成：验证表与索引、一次性老用户迁移、nonce 哈希/过期、Turnstile 到算数的单次转换、算数正确/错误/过期/冷却状态机。
- 修改文件：`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_monitor_message_cleanup.UserVerificationStateTest -v`，6 项通过。
- 已知问题：状态机尚未接入 Telegram 消息路由。
- 下一步：执行 `P3`，实现统一私聊门禁、Web App 按钮、数学答案交互和提示防刷。
- 工作区摘要：业务代码、测试与计划均有预期修改；没有运行产物。
- 可运行性：P2 相关测试通过，原有 Bot 行为尚未接入新状态机。

### 2026-07-27 — P3

- 当前阶段：`P3`，100%。
- 已完成：优先级统一私聊门禁、管理员/群组绕过、封禁优先、Web App 按钮、提示防刷、数学交互和成功后重发提示。
- 修改文件：`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_monitor_message_cleanup.PrivateVerificationGateTest -v`，6 项通过。
- 已知问题：Web App 页面和 Turnstile/Telegram 服务端验证 API 尚未实现。
- 下一步：执行 `P4`，实现公共验证页面、initData 验签、Turnstile 可信验证、原子推进与路由安全测试。
- 工作区摘要：业务代码、测试与计划均有预期修改；无密钥与运行产物。
- 可运行性：门禁单元测试通过；完整网页验证流程尚不可用。

### 2026-07-27 — P4

- 当前阶段：`P4`，100%。
- 已完成：移动端 Mini App、Telegram `initData` 验签与时效检查、nonce/用户绑定、Turnstile 可信服务端验证、hostname/action 校验、并发单次状态推进、Bot 算数题发送、精确公共路由、CSP/安全头、请求体限制与双层基础限流。
- 修改文件：`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_monitor_message_cleanup.TurnstileVerificationTest -v`，11 项通过；之后补充活动入口复用测试，相关 P3/P4 合计 18 项通过。
- 已知问题：没有公网 HTTPS 域名时无法在真实 Telegram 客户端完成 Mini App 端到端联调；该项按计划保留到 `P7`。
- 下一步：执行 `P5`，补充非敏感配置示例、README、本地路由联调和官方测试凭据验证。
- 工作区摘要：业务代码、测试和计划为预期修改；未创建 Cloudflare 资源，未写入真实 secret。
- 可运行性：页面/API 和状态机自动化测试通过；功能默认关闭。

### 2026-07-27 — P5

- 当前阶段：`P5`，100%。
- 已完成：`.env.example`、README 行为说明、本地/生产边界、测试 key 防误用说明、生产 Spin Worker 配置方式；Docker 真实依赖环境完成 FastAPI `TestClient` 页面/API/鉴权/请求体联调。
- 修改文件：`.env.example`、`README.md`、`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：Docker FastAPI `TestClient` 集成检查通过；Cloudflare 官方测试 sitekey/secret 的联网 Siteverify 检查通过。
- 已知问题：未创建正式 widget、未部署 Worker、未连接生产 Bot，均属于未授权的 `P7`。
- 下一步：执行 `P6` 全量单元测试、编译、diff、工作区和安全边界检查。
- 工作区摘要：`.env.example`、README、业务代码、测试和计划为预期修改；真实 `.env`、数据库、日志与密钥未进入工作区变更。
- 可运行性：Docker 镜像成功构建，真实 FastAPI 运行时联调通过。

### 2026-07-27 — P6

- 当前阶段：`P6`，100%；本地开发完成。
- 已完成：69 项全量测试、Python 编译、diff 格式检查、Docker 构建、真实 FastAPI `TestClient` 二次联调、公共路由/鉴权/日志/失败关闭/工作区安全审查。
- 修改文件：`.env.example`、`README.md`、`app.py`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，69 项通过；`python3 -m py_compile app.py`、`git diff --check`、Docker build、FastAPI `TestClient` 均通过。
- 安全检查：仅 `/verify/telegram` 与 `/api/verify/turnstile` 精确公开；未记录 Bot token、Turnstile token、`initData`、原始 nonce 或生产 secret；功能默认关闭且异常失败关闭。
- 已知限制：真实 Telegram 移动端/桌面端与生产 Turnstile widget/Worker 尚未联调，属于 `P7`，需要最终 HTTPS 域名和用户单独授权。
- 下一步：部署服务器后提供最终 HTTPS 域名，再按 `P7` 创建/配置 Cloudflare 资源并完成真实客户端验收。
- 工作区摘要：仅上述 5 个预期文件有变更；无 `.env`、数据库、日志、缓存或密钥进入 Git 状态。
- 可运行性：本地目标完整可运行，生产验证功能维持默认关闭。

### 2026-07-27 — P6.1

- 当前阶段：`P6.1`，100%；验证参数管理 WebUI 已补齐。
- 已完成：在设置向导和用户管理共享卡片加入同一套验证配置表单、配置完整性提示、生产/测试警告、数值与 hostname 规范化，以及 `.env` 未提交字段和未知键保留。
- 修改文件：`app.py`、`README.md`、`tests/test_monitor_message_cleanup.py`、`DEVELOPMENT_PLAN.md`。
- 最后测试：全量 `unittest` 73 项通过，`python3 -m py_compile app.py` 与 `git diff --check` 通过；Docker 真实 FastAPI `TestClient` 完成表单提交、重复 checkbox 解析、保存、回显、自定义环境变量保留和 secret 边界检查。
- 安全检查：WebUI 只暴露 sitekey 与 Spin Worker URL，不存在 `TURNSTILE_SECRET_KEY` 表单或落盘逻辑。
- 已知限制：保存验证参数不会创建 widget 或 Worker；正式值及真实 Telegram 联调仍属于 `P7`。
- 下一步：服务器部署后提供最终 HTTPS 域名，再进入 `P7`。
- 工作区摘要：预期代码、文档、测试和开发计划改动；无真实 `.env`、数据库、日志或密钥变更。
- 可运行性：验证参数可以通过 WebUI 保存并立即用于后续验证请求。
