---
description: "界定 melody 交付阶段 1（插件创建事项卡、inbox 展示与浏览器通知、钩子提醒、一键交给自己的 Agent）的必做范围、低保真线框与验收判据，并保留执行交接的单客户端实测记录与后续阶段计划。"
---

# MVP：事项卡 inbox 最小闭环与分阶段交付

## 摘要

本文供产品与开发人员确认当前交付范围、低保真线框与验收判据。当前交付范围是交付阶段 1：发起人通过 melody 插件在原有 coding 客户端一句话创建事项卡；接收人在 inbox 页面看到这张卡并收到浏览器通知，其 coding 客户端里的 Agent 也通过插件钩子得知有待处理事项；接收人自己回答，或一键交给自己的 Agent 处理并把回复写回卡片；发起人确认后关闭。交付阶段 1 不需要常驻客户端。企业微信入口与通知属于交付阶段 2，方案确认与 worktree 执行交接属于交付阶段 3；后者的单客户端实测记录保留在本文。

状态：交付阶段 1 规划草案，尚未实现生产代码；钩子提醒与 deep link 交接待按本文试验矩阵实测。

## 目录

- [已拍板的核心决策](#已拍板的核心决策)
- [交付阶段 1 范围](#交付阶段-1-范围)
- [交付阶段 1 低保真线框](#交付阶段-1-低保真线框)
- [交付阶段 1 试验设计](#交付阶段-1-试验设计)
- [执行交接单客户端实测记录](#执行交接单客户端实测记录)
- [分阶段实施计划](#分阶段实施计划)
- [Dev Note](#dev-note)

## 已拍板的核心决策

| 编号 | 决策项 | 已确认方案 | 生效阶段 |
|---|---|---|---|
| D1 | 协作载体 | 一件事一张事项卡，在 melody inbox 页面展示；不做频道、成员列表或自由聊天流。取舍见 [ADR-002](adr/0002-inbox-cards-instead-of-chat.md) | 交付阶段 1 起 |
| D2 | Agent 开始处理的触发 | 收到事项卡后不自动运行模型；Agent 只在接收人本人于自己的工具中发出提示后开始处理。deep link 只填写提示、不发送，接收人按回车即为唤起 | 交付阶段 1 起 |
| D3 | 原客户端会话交接路线 | 不把“插入已打开的既有活跃 session”作为阻塞项。每次获批工作拉起一个带原生 session ID 的新会话，接收人在原工具 `resume` 接手；同一事项卡的后续补充复用该 session ID | 交付阶段 3 |
| D4 | 断线与重试防重复开工 | 投递携带唯一 `attempt_id`，落盘到本地适配器状态与 worktree 元数据；重连后先核对本地是否已有对应会话或进程，查不到才启动，无法核对时停在“状态未知”由接收人决定 | 交付阶段 3 |
| D5 | 并发隔离与 worktree 来源透明 | 代码执行默认使用独立的 `git worktree`；确认单、事项卡和交接入口必须让人一眼看明白该 worktree 从哪个主仓库、哪个基准分支与 commit 派生，以及对应的本地目录和工作分支名 | 交付阶段 3 |
| D6 | 发起入口 | 发起人在原有 coding 客户端中通过 melody 插件发起，由发起人的 Agent 打包附带上下文；发送前展示附带与不附带的内容 | 交付阶段 1 起 |
| D7 | 企业微信定位 | 外围的入口与通知通道，放到交付阶段 2；企业微信中的操作只改变服务端事项卡状态，不能直接触发接收人电脑上的动作 | 交付阶段 2 |
| D8 | 收件对象 | 事项卡发给人，不设独立的 Agent 身份或常驻个人总代理；平台只保存人的身份和接入配置。取舍见 [ADR-003](adr/0003-cards-addressed-to-people.md) | 交付阶段 1 起 |
| D9 | 交付阶段 1 的提醒方式 | melody 插件钩子提醒接收人的 Agent，inbox 页面发出浏览器通知；不做常驻客户端或系统弹窗 | 交付阶段 1 |
| D10 | 知识沉淀预留 | 事项卡从交付阶段 1 起记录可见范围、依据的仓库与 commit、所属仓库和结论；知识检索在交付阶段 3 之后再做 | 交付阶段 1 起 |
| D11 | 参与者与分享 | 参与者分为发起人、恰好一个接收人、读者。继续讨论是往同一张卡追加往来。分享是增加读者，不复制卡片，也不做公告牌。交付阶段 1 读者为空，不提供分享 | 交付阶段 1 起预留，分享在其后 |
| D12 | 信息单位与代码事实 | 事项卡是唯一的信息单位，不另建事件流。执行卡用工作分支名和代码对应，问答卡没有工作分支名 | 交付阶段 1 起；分支名在交付阶段 3 写入 |

## 交付阶段 1 范围

### 必须交付

- **身份与接入配置：** 持久保存 `Person` 及其接入配置（默认客户端、本地代码根目录）；每个人用本地配置的个人令牌访问服务。
- **melody 插件：** 为 Claude Code 与 Codex 提供一个插件，包含 skill（`ask` 发起、`show` 读取、`reply` 回复）和钩子配置，以及 skill 与钩子调用的命令行脚本。安装插件即可发起、接收提醒和处理事项卡。
- **创建事项卡：** 发起人一句话指定接收人和请求，由发起人的 Agent 选择附带上下文（会话片段、文件位置），发送前预览。卡片类型为问题卡或执行卡；服务端从附带内容自动记录所属仓库。
- **inbox 页面：** “待我处理”“我发出的”“已完成”三个列表；详情页展示请求、附带上下文、状态和往来记录；页面打开时，新卡到达发出浏览器通知，页面关闭期间到达的卡在下次打开时显示为未读。
- **钩子提醒：** Claude Code 与 Codex 的 `SessionStart`、`UserPromptSubmit` 钩子调用插件脚本，有未处理事项时向会话注入一句事实性提醒。
- **三种处理方式：** 接收人在详情页自己回复；或点“交给我的 Agent 处理”，通过 deep link 在默认客户端和对应仓库中打开新会话并填好“处理 melody 事项卡 <编号>”；或在工具中直接让 Agent 处理。Agent 通过插件读取卡片，处理后经接收人同意用插件写回回复。
- **关闭与结论：** 发起人可追问；发起人点“收到”或“关闭”结束事项。关闭问题卡时，发起人确认的那条回答记为结论。往来记录在关闭后仍可追加，供以后继续讨论。
- **参与者：** 保存发起人与恰好一个接收人。读者列表存在但为空。可见范围默认仅参与者，阶段 1 不提供切换。

### 本阶段不做

常驻客户端、系统弹窗与远程唤起接收人电脑；企业微信推送与回调；方案确认单、worktree 派生与执行结果自动回传；自动运行模型；在 inbox 页面直接新建事项卡；频道、成员列表、群聊和公告牌；把第三人加为读者或提供「分享给我的」；团队可见开关；优先级、指派流转、看板列；知识检索与团队统计页；自动合并代码；跨客户端私有上下文无损迁移。

### 交付阶段 1 状态

| 状态 | 进入条件 | 谁能改变 |
|---|---|---|
| 待处理 | 事项卡创建成功 | 接收人在 inbox 打开或其 Agent 用 `show` 读取后变为“已读” |
| 已读 | 接收人或其 Agent 读取卡片 | 接收人回复后变为“已回复” |
| 已回复 | 接收人或其 Agent 写回回复 | 发起人追问后回到“已读”；发起人点“收到”或“关闭”后变为“已关闭” |
| 已关闭 | 发起人结束事项 | 无 |

钩子提醒与浏览器通知只读取状态，不改变状态。

### 成功与失败判据

| 必须观察到的行为 | 失败信号 |
|---|---|
| A 在 Claude Code 或 Codex 中一句话发起，预览中列出附带与不附带的内容后发出 | A 必须打开网页填表，或必须手工复制会话内容 |
| B 的 inbox 在“待我处理”中出现该卡，详情包含请求与附带上下文；页面开着时收到浏览器通知 | B 必须回群聊或问 A 才能看懂请求 |
| B 下一次在 Claude Code 或 Codex 中提交提示时，Agent 上下文中出现未处理事项提醒，且钩子本身没有调用模型 | 钩子触发了模型调用、改写了仓库，或提醒中混入卡片全文 |
| B 点“交给我的 Agent 处理”后，自己的工具在对应仓库打开并填好提示，按回车后 Agent 读到卡片全文并把回复写回卡片 | B 需要从网页复制请求或附带内容到工具里，或回复需要手工粘贴回网页 |
| A 能在“我发出的”看到回复，点“收到”后卡片进入“已完成”并记录结论 | 回复只能在 B 本地看到，或卡片被系统自动关闭 |

## 交付阶段 1 低保真线框

### 1. 在原工具发起（发起人 A 的终端）

```text
> /melody ask @B 请补退款状态接口，字段见上面讨论

melody · 将发出事项卡
  类型    执行卡
  给      B
  请求    补退款状态接口
  附带    接口字段说明（本会话第 12 轮）
          src/pages/order/RefundTag.tsx 调用点
  仓库    order-service
  不附带  本会话其余内容

  [Enter 发送]  [e 编辑附带内容]  [Esc 取消]

已发送 · 事项 W-42 · 待 B 处理
查看：http://melody.local/cards/W-42
```

### 2. inbox 列表与详情（接收人 B）

```text
┌──────────────────────────────────────────────┐
│ melody inbox · B                              │
│ [待我处理 2]  [我发出的]  [已完成]            │
├──────────────────────────────────────────────┤
│ ● W-42  补退款状态接口      A →   待处理      │
│   Q-17  部分退款是否单独展示 C →   已回复      │
├──────────────────────────────────────────────┤
│ W-42 补退款状态接口                  执行卡    │
│ 发起人 A · 给 B · order-service · 仅参与者    │
│                                              │
│ 请求                                          │
│   请补退款状态接口，字段见附带内容            │
│ 附带上下文                                    │
│   [展开] 接口字段说明                         │
│   [展开] src/pages/order/RefundTag.tsx #L30   │
│ 往来记录                                      │
│   15:40 A 发起                                │
│   15:52 B 已读                                │
│                                              │
│ [交给我的 Agent 处理 · Claude Code ▾]         │
│ 回复：____________________________ [发送]    │
└──────────────────────────────────────────────┘
```

回复框只服务这张卡，不是聊天流；详情页没有成员栏和新建入口。“▾”可临时改用接入配置中的其他客户端。

### 3. 交给自己的 Agent（B 点按钮后）

```text
新终端窗口 · ~/code/order-service
┌──────────────────────────────────────────────┐
│ > 处理 melody 事项卡 W-42                     │
│   Prompt from an external link                │
└──────────────────────────────────────────────┘
（B 按回车）
Agent：读取 W-42 …… A 需要新增 partial_refunded
  字段与单测。我先看 order/api/refund.py ……
  ……
  已完成，要把以下回复写回 W-42 吗？
  “已新增字段并补 4 项单测，分支 feat/refund-status”
> 好
已写回 W-42 · 状态：已回复
```

### 4. 钩子提醒（B 正在做别的事）

```text
B 的 Claude Code 会话：
> 帮我看下今天的告警
  （钩子注入的上下文，对 B 不显示为消息：
    melody inbox 有 1 张待处理事项卡：
    W-42 补退款状态接口，来自 A。）

Agent：先说告警……另外 A 给你发了一张待处理的
  执行卡 W-42（补退款状态接口），需要我处理吗？
> 处理 W-42
```

## 交付阶段 1 试验设计

以下能力已核对官方文档，尚未在当前 MacBook Air 实测：

- [Claude Code hooks](https://code.claude.com/docs/en/hooks) 说明 `SessionStart` 与 `UserPromptSubmit` 的纯文本 stdout 或 `hookSpecificOutput.additionalContext` 会作为上下文提供给 Claude，不显示为聊天消息；[Codex hooks](https://learn.chatgpt.com/docs/hooks) 说明这两个事件可通过 `additionalContext` 向会话添加开发者上下文。
- [Claude Code deep links](https://code.claude.com/docs/en/deep-links) 支持 `claude-cli://open?cwd=<目录>&q=<提示>` 在新终端窗口打开并填好提示，不自动发送；需要先在这台机器上交互使用过一次 Claude Code 才会注册该链接。[Claude 桌面版](https://support.claude.com/en/articles/14729294-open-claude-desktop-with-a-link)使用 `claude://code/new?folder=<目录>&q=<提示>`，每次都会确认目录。[Codex](https://learn.chatgpt.com/docs/reference/commands) 使用 `codex://new?path=<目录>&prompt=<提示>`。[Cursor](https://cursor.com/docs/reference/deeplinks) 使用 `cursor://anysphere.cursor-deeplink/prompt?text=<提示>`，不能指定目录。

| 试验编号 | 验证内容 | 通过判据 |
|---|---|---|
| N1 插件安装与创建 | 在 Claude Code 与 Codex 中安装 melody 插件，分别发起问题卡和执行卡 | 安装一次即可使用 skill 与钩子；预览列出附带与不附带内容；服务端只保存预览中列出的内容并记录所属仓库 |
| N2 inbox 展示与浏览器通知 | 接收人打开“待我处理”与详情页；页面开着时创建新卡；关闭页面后再创建一张 | 卡片、附带上下文、往来记录完整；页面开着时一次通知；重新打开后关闭期间的卡显示为未读 |
| N3 Claude Code 钩子提醒 | 有未处理卡时启动会话并提交提示 | 上下文中出现一句提醒；钩子本身不调用模型、不写仓库；服务端不可达或无未处理卡时不注入且不阻塞提示 |
| N4 Codex 钩子提醒 | 同 N3，在 Codex 中执行 | 同 N3 |
| N5 deep link 交接 | 分别以 Claude Code 命令行、Codex、Cursor 为默认客户端点“交给我的 Agent 处理” | 工具打开并填好提示，未自动发送；Claude Code 与 Codex 的工作目录为对应仓库；按回车后 Agent 用 `show` 读到卡片全文 |
| N6 回复、关闭与结论 | B 分别用 inbox 和 Agent 写回回复，A 追问后点“收到” | 状态按“交付阶段 1 状态”表流转；Agent 写回前征得 B 同意；关闭只能由发起人触发，并记录结论 |

## 执行交接单客户端实测记录

本节是交付阶段 3 的前置证据。实测时协作载体仍称为 `#thread`，记录保留原样。

### 候选客户端证据分级

以下文档事实已核对官方公开资料，但均未在当前 MacBook Air 实测端到端行为；Matt Pocock 原帖（`https://x.com/mattpocockuk/status/2124797717834543167`）读取返回 `403`，其“人与 Agent 私有 Slack、身份互 `@`、离线队列、chat 而非新 Jira”定位按用户提供的调研摘要对标。

| 候选路线 | 官方文档已描述的事实 | 待实测验证项（不能仅凭文档认定） |
|---|---|---|
| [Claude 原生后台会话](https://code.claude.com/docs/en/agent-view)与[会话管理](https://code.claude.com/docs/en/sessions) | 支持 `claude --bg` 启动、在 `claude agents` 查看并 attach，或按 session ID `resume` | 适配器在指定 worktree 拉起后，B 能否在本地终端流畅 attach/resume 继续同一会话且状态可回传 |
| [Codex App Server](https://developers.openai.com/codex/app-server) | 提供 thread 新建/恢复、turn 推进与事件流，CLI 支持 `--remote` 连接同一后端 | 本地拉起的会话能否被本人在 CLI 或桌面端直接接手且事件序号可靠 |
| [Claude Code Channels](https://code.claude.com/docs/en/channels-reference) | 支持向已开启会话推送事件、忙时排队与回复工具（research preview） | **非 MVP 阻塞项：** 组织/登录门槛及应用级回执表现，留作后续增强试验 |
| [Cursor deeplink](https://cursor.com/docs/reference/deeplinks) / [CLI](https://cursor.com/docs/cli/reference/parameters) / [Cloud API](https://cursor.com/docs/cloud-agent/api/endpoints.md) | deeplink 支持预填聊天；CLI 支持会话管理；Cloud API 运行在云端 worker | CLI 会话不会自动出现在 IDE 列表；Cloud API 不是本地原工作台执行 |

### 单客户端实测结论（已在本地隔离仓库跑通 T1—T6）

在本地隔离测试仓库（基线 `main @ b338bb1`）上对三种原生会话拉起路线及 T1—T6 矩阵进行了真实命令验证：

| 候选路线 | 实测命令（在新建 `git worktree` 目录下） | 实测结果与观察到的行为 | 结论 |
|---|---|---|---|
| **路线 A：`claude --bg`** | `claude --bg --name <name> "<prompt>"` | **退出码 `1`（受阻）：** `Workspace not trusted. Run claude in <worktree_path> once and accept the trust prompt`。因为每次派生的 `git worktree` 是新目录路径，未在 `~/.claude.json` 单独点击过交互式信任弹窗前无法后台静默拉起 | 不作为自动派发的首选启动方式 |
| **路线 B：`claude -p --session-id <uuid>` + `claude --resume <uuid>`** | 首轮：`claude -p --session-id 39fa4449-6440-4fd2-8a00-63a52764bb9a --permission-mode plan --output-format json ...`<br>续接：`claude --resume 39fa4449-6440-4fd2-8a00-63a52764bb9a` | **退出码 `0`（通过）：** 在新派生的 worktree 中无需预弹窗即可完成首轮并持久化会话 `39fa4449-6440-4fd2-8a00-63a52764bb9a`；第二轮通过 `--resume` 成功读取首轮 `MARK_1_CLAUDE_OK` 并拼接输出 `MARK_1_CLAUDE_OK+MARK_2_OWNER_CONTINUED`，所有者可在终端用 `claude --resume <uuid>` 原生接手同一会话 | **选为 Claude Code 适配器默认路线** |
| **路线 C：`codex exec --json -C <worktree>` + `codex resume <thread_id>`** | 首轮：`codex exec --json -s read-only -C <worktree_path> ...`<br>续接：`codex resume 01a20dec-5253-7932-aece-e312c4ff1937` | **退出码 `0`（通过）：** JSONL 事件流实时返回 `thread.started`（`01a20dec-5253-7932-aece-e312c4ff1937`）；第二轮 `resume` 成功输出 `MARK_1_CODEX_OK+MARK_2_OWNER_CONTINUED`，所有者可在终端用 `codex resume <thread_id>` 原生接手 | **选为 Codex 适配器默认路线** |

#### T1—T6 试验矩阵实测记录

| 试验编号 | 实测结果 | 观察到的真实证据 |
|---|---|---|
| **T1 手动唤起与只读问答** | **通过** | 未点击唤起前 `worktree_count=1`、`repo_dirty=false`；唤起只读模式（`--permission-mode plan` / `-s read-only`）仅引用 `#thread` 消息回答，未建工作卡、未改写仓库 |
| **T2 Worktree 派生与双端同源续接** | **通过** | 从 `main @ b338bb1` 派生 `melody/work-42-att-bakeoff`，Claude（`39fa4449-…`）与 Codex（`01a20dec-…`）均在各自原生 session 中跨轮保留 `MARK_1` 并拼接 `MARK_2_OWNER_CONTINUED` |
| **T3 同仓库并发 Worktree 隔离** | **通过** | `att-9f3a` 与 `att-7b2c` 各自派生独立 worktree 并提交（`head_commit: e85b336` vs `058a4da`），主仓库保持在基线且无脏文件；`git merge-tree --write-tree` 准确预检出 `CONFLICT (content): Merge conflict in order.py` 且未破坏任何工作区 |
| **T4 断线核对防重复开工** | **通过** | 重复投递同一 `attempt_id="att-9f3a"` 时，适配器命中本地 `adapter_state.json` 与 `.melody-attempt.json`（`reconciled_hit=true`），`worktree_count` 保持为 `2`，未创建第二个 worktree 或新会话 |
| **T5 真实取消回执** | **通过** | 对运行中会话进程组发送 `SIGTERM`（`os.killpg`），实测捕获退出码 `-15` 且 `os.kill(pid, 0)` 确认进程已消失后才更新为“已确认停止”，worktree 目录保留现场 |
| **T6 人工介入与结果验收分离** | **通过** | 执行结束状态停在 `pending_human_check`（不自动变已验收）；模拟旧尝试 `att-old-001` 的迟到事件被 `active_attempt_id` 校验拦截，未覆盖当前卡片 |

## 分阶段实施计划

| 阶段 | 目标与交付物 | 准出验证门槛 |
|---|---|---|
| **准备：规划与执行交接脚本试验（已完成）** | 产品目标、架构骨架、ADR-001 至 ADR-003；本地隔离仓库实测三条会话拉起路线与 T1—T6 矩阵 | 上文实测记录 |
| **交付阶段 1：事项卡、提醒与一键交给自己的 Agent（待推进）** | SQLite 存储、`Person` 与接入配置、事项卡及预留字段；melody 插件（skill、钩子、脚本）；inbox 页面、浏览器通知与 deep link 按钮 | N1—N6 通过；A 与 B 在真实项目上各完成一次问题卡与执行卡，全程无手工复制上下文或回复 |
| **交付阶段 2：企业微信入口与通知（待推进）** | 企业微信自建应用或智能机器人：一句话发起事项卡、推送按钮卡片、接收回调、更新同一张卡；卡片上可点“收到”和验收 | 按钮回调在 5 秒内响应；状态变化更新同一张卡；`response_code` 过期后能重发卡片或引导回 inbox |
| **交付阶段 3：方案确认与执行交接（待推进）** | 只读拟方案、不可变确认单、worktree 与客户端适配器、结果自动回传事项卡 | 本地端到端跑通“问题卡不进入确认”与“确认 → 派生 worktree 并拉起原工具 → 回执与结果回传 → 迟到事件不覆盖”；A 与 B 在真实项目完成一次执行交接 |

## Dev Note

本节非权威。卡片上展示「Agent 正在处理」属于低优先级交互，不进入交付阶段 1，记录在 [产品目标](product.md) 的 Dev Note。企业微信能力已核对官方文档但未在团队企业微信实测：群机器人 Webhook 能发模板卡片但按钮不回调、卡片不能更新；自建应用与智能机器人支持按钮回调和 `update_template_card`，回调需 5 秒内响应，`response_code` 单次使用且 72 小时过期；智能机器人另有长连接模式，可能免去公网回调地址；企业微信内能否直接打开 `claude-cli://` 等自定义链接未知，不能时由卡片先跳转 inbox 页面。Claude Code 插件可同时打包 skill 与钩子；Codex 能否以单个插件同时安装 skill 与钩子尚未核实，不能时需要分别配置。非开发角色在 inbox 页面直接新建事项卡的入口视试用反馈再定。
