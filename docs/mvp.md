---
description: "界定团队 Agent 协作对话板 MVP 的必做范围、低保真界面线框、worktree 可见性规则、单客户端试验矩阵与分阶段计划。"
---

# MVP：团队 Agent 协作对话板最小闭环与试验设计

## 摘要

本文供产品与开发人员确认当前 MVP 的交付范围、低保真线框与验收判据。MVP 聚焦两个人和各自 Personal Agent 在同一 `#thread` 完成问答澄清与代码执行交接：所有者手动唤起响应、确认批准快照、在来源清晰的隔离 `git worktree` 中拉起原客户端可见会话、本人接手操作，并将状态与结果回传原 `#thread`。

状态：MVP 规划与试验设计草案，尚未实现生产代码，原客户端联动待按本文试验矩阵实测。

## 目录

- [已拍板的核心决策](#已拍板的核心决策)
- [必做范围与不做项](#必做范围与不做项)
- [低保真界面线框](#低保真界面线框)
- [单客户端试验设计](#单客户端试验设计)
- [分阶段实施计划](#分阶段实施计划)
- [Dev Note](#dev-note)

## 已拍板的核心决策

| 编号 | 决策项 | 已确认方案 |
|---|---|---|
| D1 | 协作容器命名 | 统一使用 `#thread`（如 `#订单列表退款状态`），一件事一个 `#thread`，不使用 `topic` |
| D2 | `@Agent` 响应与拟方案触发 | MVP 采用**所有者手动唤起**：收到 `@B-Agent` 后不自动后台跑模型，由所有者 B 点击唤起本地客户端读取 `#thread` 并输出回答或方案草案，杜绝配额暗耗与未授权偷跑 |
| D3 | 原客户端会话交接路线 | **不把“插入已打开的既有活跃 session”作为阻塞项。** MVP 基准路线为：每次获批工作拉起一个带原生 session ID 的新会话（或原生后台会话），B 在原工具 `attach` 或 `resume` 接手；同一工作卡的后续补充复用该 session ID |
| D4 | 断线与重试防重复开工 | 投递携带唯一 `attempt_id` 落盘到本地适配器状态与 worktree 元数据；重连后先核对本地是否已有对应 `attempt_id` 的会话或进程，查不到才启动，无法核对时停在“状态未知”由 B 决定 |
| D5 | 并发隔离与 worktree 来源透明 | 代码执行默认使用独立的 `git worktree`；在确认页、执行卡和交接页**必须让人一眼看明白该 worktree 从哪个主仓库、哪个基准分支/commit 派生，以及对应的本地目录和工作分支名** |

## 必做范围与不做项

### 必须交付

- **身份与 `#thread`：** 持久保存 `Person`、`PersonalAgent` 稳定身份及默认客户端接入配置；同一 `#thread` 支持人、Agent 混合发言与 `@` 寻址，Agent 继承所有者的 `#thread` 可读范围。
- **两条协作路径：** 普通问答直接由 B 手动唤起 B-Agent 基于 `#thread` 上下文回复并标注引用消息编号，不建工作卡；需要改代码或跑命令时生成工作方案与唯一状态卡。
- **不可变批准快照与 worktree 来源展示：** 所有者确认页固化任务目标、完成条件、引用消息内容快照、主仓库路径、基线分支与 commit、派生 worktree 路径及工作分支名。
- **原工具同源交接与回传：** 适配器在指定 worktree 拉起原客户端可见会话，返回接收、执行中、待本人介入、停止、完成等真实回执；执行完成后回传结论、验证结果及 worktree 分支/commit 供发起人在 `#thread` 直接验收。

### 本轮不做

大协作空间与项目分类树、后台无人值守自动唤醒 LLM、强行注入已打开的 GUI 既有会话（作为非阻塞增强）、平台自建 IDE 或全面执行控制台、自动合并代码与冲突自动消解、跨客户端私有上下文无损迁移、定时调度与通用工作流引擎。

### MVP 成功与失败判据

| 必须观察到的行为 | 失败信号 |
|---|---|
| A 在 `#thread` 提问 `@B-Agent`，B 唤起后 B-Agent 依据 `#thread` 消息回答并给出来源 | B 必须把团队聊天手工复制粘贴到另一个窗口才能回答 |
| 只需澄清的对话以消息结论结束 | 普通问答被强制转成审批单或待验收任务卡 |
| B 确认前看清范围、消息依据与 worktree 派生来源，确认后原工具出现对应会话 | 被 `@` 自动改代码，或看不出 worktree 从哪来、改在哪个目录 |
| B 在原工具 attach/resume 同一会话继续操作，结果与 worktree 分支回传原 `#thread` | 平台后台另跑不可见黑盒进程，或人要手动复制结果回聊天 |
| 断线重连、重复投递、请求停止呈现真实核对状态 | 重连开出两个会话重复改代码、无宿主证据却显示“已停止” |
| 发起人可在 `#thread` 直接确认结果或要求继续 | 执行结束被系统自动标记为人工验收通过 |

## 低保真界面线框

三张视图采用手机可读的单列结构，核心状态与操作不依赖悬停；worktree 派生关系在确认前、执行中、回传后保持一致可见。

### 1. `#thread` 协作流（含普通问答与工作状态卡）

```text
┌────────────────────────────────────┐
│ ‹ #订单列表退款状态              ⋯ │
│ 成员：A  A-Agent  B  B-Agent   [+] │
├────────────────────────────────────┤
│ A：@B-Agent 退款状态含部分退款吗？ │
│                                    │
│ B-Agent（由 B 唤起 · 引用 #3 #5）：│
│ 包含 partial_refunded，见消息 #5   │
│ 接口约定。                         │
│                                    │
│ A：收到。@B-Agent 请补这个字段接口 │
│ 和单测，附字段说明：[展开]         │
│ 状态：等待 B 唤起 B-Agent 拟方案   │
│ [B 可见：唤起 B-Agent 拟定方案]    │
│                                    │
│ B-Agent：建议修改 order-service    │
│ ┌ 工作：退款状态接口 ────────────┐ │
│ │ 状态：等待 B 确认（方案 v1）   │ │
│ │ 仓库：~/code/order-service     │ │
│ │ 基线：main @ a1b2c3d           │ │
│ │ 隔离：将新建 worktree          │ │
│ │ [查看确认单 / B 确认]          │ │
│ └────────────────────────────────┘ │
│                                    │
│ （执行完成后，同一张卡片更新：）   │
│ ┌ 工作：退款状态接口 ────────────┐ │
│ │ 状态：结果已回传 · 待人工检查  │ │
│ │ 结论：已新增字段并通过 4 项单测│ │
│ │ 来源 worktree：                │ │
│ │   主仓库 ~/code/order-service  │ │
│ │   派生自 main @ a1b2c3d        │ │
│ │   目录   …/wt-refund-attempt-1 │ │
│ │   分支   melody/refund-status  │ │
│ │   最新   commit f9e8d7c (+2 files)│
│ │ [在原工具查看会话] [验证输出]  │ │
│ └────────────────────────────────┘ │
│ A：已检查，分支可以直接提 PR       │
├────────────────────────────────────┤
│ @人或Agent，输入消息…              │
│ [发送]              [+ 请求协助]   │
└────────────────────────────────────┘
```

### 2. 所有者确认单（突出 worktree 来龙去脉）

```text
┌────────────────────────────────────┐
│ ‹ B 确认工作：退款状态接口         │
│ 来自 #订单列表退款状态 · A 请托    │
├────────────────────────────────────┤
│ 做什么：新增 partial_refunded 字段 │
│         及单元与接口测试           │
│ 完成条件：pytest tests/order 通过  │
│ 依据快照：消息 #8 #9（已固化版本） │
│                                    │
│ ── 执行环境与 Worktree 来源 ───── │
│ 客户端：Claude Code（B 默认接入）  │
│ 会话方式：新建原生可见会话         │
│ 主仓库：~/code/order-service       │
│ 派生基线：main (commit a1b2c3d)    │
│ 隔离目录：~/code/.melody-wt/       │
│           order-service-work-42-1  │
│ 工作分支：melody/work-42-attempt-1 │
│ 创建方式：确认后由本地适配器通过   │
│           git worktree add 自动派生│
│ 合并策略：仅保留分支与变更，不自动 │
│           合并回 main              │
│                                    │
│ 允许操作：读写上述 worktree、跑测试│
│ 工具权限：沿用原客户端本地权限门槛 │
│ 说明：后续群聊不改变本次已批准范围 │
├────────────────────────────────────┤
│ [需 A 补充]   [拒绝]               │
│ [确认：创建 Worktree 并拉起原工具] │
└────────────────────────────────────┘
```

### 3. 接入配置与原工具交接页

```text
┌────────────────────────────────────┐
│ ‹ B-Agent · 接入与原工具交接       │
├────────────────────────────────────┤
│ 默认客户端：Claude Code (本地 CLI) │
│ 默认仓库根：~/code/                │
│ 响应触发：所有者手动点击唤起       │
│ 连接状态：在线 · 已验证            │
│ [编辑默认接入]                     │
├────────────────────────────────────┤
│ 当前工作：退款状态接口 · 尝试 #1   │
│ ✓ B 已批准方案 v1 (attempt_id: 9f3a)│
│ ✓ 已从 ~/code/order-service        │
│   (main @ a1b2c3d) 派生 worktree   │
│ ✓ 原生会话已拉起 (session: cc_781) │
│ ● 执行中 · 需要 B 在原工具确认权限 │
│                                    │
│ Worktree 路径：                    │
│ ~/code/.melody-wt/order-service-…  │
│ 工作分支：melody/work-42-attempt-1 │
│ 原工具接手命令 / 入口：            │
│ `claude --resume cc_781`  [复制]   │
│ [在原工具打开]      [请求停止执行] │
│                                    │
│ 子执行与本地重试记录 (0)    [展开] │
└────────────────────────────────────┘
```

## 单客户端试验设计

### 候选客户端证据分级

以下文档事实已核对官方公开资料，但均未在当前 MacBook Air 实测端到端行为；Matt Pocock 原帖（`https://x.com/mattpocockuk/status/2124797717834543167`）读取返回 `403`，其“人与 Agent 私有 Slack、身份互 `@`、离线队列、chat 而非新 Jira”定位按用户提供的调研摘要对标。

| 候选路线 | 官方文档已描述的事实 | 待实测验证项（不能仅凭文档认定） |
|---|---|---|
| [Claude 原生后台会话](https://code.claude.com/docs/en/agent-view)与[会话管理](https://code.claude.com/docs/en/sessions) | 支持 `claude --bg` 启动、在 `claude agents` 查看并 attach，或按 session ID `resume` | 适配器在指定 worktree 拉起后，B 能否在本地终端流畅 attach/resume 继续同一会话且状态可回传 |
| [Codex App Server](https://developers.openai.com/codex/app-server) | 提供 thread 新建/恢复、turn 推进与事件流，CLI 支持 `--remote` 连接同一后端 | 本地拉起的会话能否被本人在 CLI 或桌面端直接接手且事件序号可靠 |
| [Claude Code Channels](https://code.claude.com/docs/en/channels-reference) | 支持向已开启会话推送事件、忙时排队与回复工具（research preview） | **非 MVP 阻塞项：** 组织/登录门槛及应用级回执表现，留作后续增强试验 |
| [Cursor deeplink](https://cursor.com/docs/reference/deeplinks) / [CLI](https://cursor.com/docs/cli/reference/parameters) / [Cloud API](https://cursor.com/docs/cloud-agent/api/endpoints.md) | deeplink 支持预填聊天；CLI 支持会话管理；Cloud API 运行在云端 worker | CLI 会话不会自动出现在 IDE 列表；Cloud API 不是本地原工作台执行 |

### 阶段 2 单客户端实测结论（已在本地隔离仓库跑通 T1—T6）

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
| **阶段 1：规划与规格基线（已完成）** | 完成产品目标、MVP 规格、架构骨架、ADR-001 及旧云端沙箱文档归档 | 用户确认 `#thread`、手动唤起、新建原生可见会话、worktree 来源展示及防重规则 |
| **阶段 2：单客户端交接脚本试验（已实测通过）** | 在本地隔离仓库实测三路线对比与 T1—T6 矩阵 | 实测排除 `claude --bg` 新目录 trust 阻塞，跑通 `claude -p --session-id` / `codex exec --json` + 原生 `--resume` 接手、worktree 隔离与 `attempt_id` 防重 |
| **阶段 3：最小协作对话板实现（待推进）** | 实现 SQLite 存储、`Person/PersonalAgent`、`#thread` 消息流、手动唤起拟方案、审批快照、Worktree+客户端适配器与三张核心页面 | 本地端到端跑通“普通问答不建卡”与“确认 -> 派生 worktree 并拉起原工具 -> 回执与结果回传 -> 迟到事件不覆盖” |
| **阶段 4：两人真实协作验收（待推进）** | A 与 B 在真实项目上走完一次问答澄清与一次代码修改交接 | 全程零手工复制粘贴上下文；worktree 分支与 commit 清晰可查；A 在 `#thread` 完成结果验收并留存运行证据 |

## Dev Note

本节非权威。阶段 2 实测发现 `claude --bg` 在新派生的 `git worktree` 目录上受交互式 `Workspace not trusted` 弹窗限制，而 `claude -p --session-id <uuid>`（配合 `claude --resume <uuid>` 交互式接手）以及 `codex exec --json -C <worktree>`（配合 `codex resume <thread_id>` 交互式接手）在新建 worktree 上均可直接跑通并保持同一原生 session ID。阶段 3 适配器实现直接采用这两条经实测验证的命令路径。

