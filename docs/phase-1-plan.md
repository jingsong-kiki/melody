---
description: "阶段 1 的落地顺序。每个 PR 只做一件事，并带上可勾选的验证。执行从操作者明确说开始之后才动手。"
---

# 阶段 1 实施计划

按 [mvp.md](mvp.md) 的交付阶段 1 做。部件、数据、不变量和接口以 [architecture.md](architecture.md) 为准，本文不另写一套。本文只排先做哪一块、改哪些文件、怎样验证。目标是 A 在 Claude Code 或 Codex 里一句话发出一张卡，B 在 inbox 里看到它，并可以自己回复，或点一下交给自己的 Agent，全程不复制内容。

这一阶段用一个 Python 进程加一个 SQLite 文件。标准库的 `sqlite3` 和 `http.server`，不引入 Web 框架，也不做常驻客户端、企业微信、分享、公告牌和 worktree。卡片是唯一的信息单位。`work_branch` 列先留空。

服务地址用环境变量 `MELODY_URL`。人用唯一名字互找。`melody person add <名字>` 打印一次个人令牌，令牌只存在本机配置里。

## 落地顺序

```text
p1-schema
  └── p1-api
        ├── p1-cli
        │     ├── p1-claude
        │     └── p1-codex
        └── p1-inbox
              └── p1-deeplink   （还依赖 p1-cli）
```

`p1-cli` 和 `p1-inbox` 都从 `p1-api` 长出来，可以分开做。`p1-deeplink` 等这两条都落地。`p1-claude` 和 `p1-codex` 互不依赖。

要等人看过再合并的是 `p1-inbox`、`p1-deeplink`、`p1-claude`、`p1-codex`。它们改的是人点、人看的界面。

性能条在本机测量。失败线是 50 张卡的列表接口超过 100 毫秒。仓库里还没有服务，所以基线是「没有进程」。每个带接口的 PR 用同一条计时命令量自己的列表或等价读取。

## p1-schema

- [ ] 依赖：无。从 `docs/initial-planning` 拉分支。
- [ ] 改这些文件：`melody/db.py`、`melody/card.py`、`tests/test_card.py`。
- [ ] 做这一件事：建 `persons`、`endpoints`、`cards`、`card_participants`、`card_attachments`、`card_entries`、`read_marks`。卡片状态只有待处理、已读、已回复、已关闭。接收人恰好一个。读者列表为空。关闭只能由发起人触发。
- [ ] 你能看见：测试进程里 A 发给 B 一张执行卡，B 读过后是已读，B 回复后是已回复，A 关闭后是已关闭，并且记下结论。
- [ ] 单测：上面四次状态变化，以及接收人不能关闭、钩子式的只读不改状态。
- [ ] 现场：`python -m unittest tests/test_card.py` 退出码 0。
- [ ] 性能：插入 50 张卡后列出 B 的待处理卡，计时。超过 100 毫秒算失败。

## p1-api

- [ ] 依赖：`p1-schema` 已合并。
- [ ] 改这些文件：`melody/server.py`、`tests/test_api.py`。
- [ ] 做这一件事：带个人令牌的 HTTP。创建卡、读取卡、回复、关闭、按角色列出。页面打开时用 SSE 推新卡。
- [ ] 你能看见：A 的 curl 创建 W-42，B 的 curl 在待处理列表里读到请求和附带内容。
- [ ] 单测：令牌不对返回 401。服务端只保存创建请求里列出的附带内容。
- [ ] 现场：起服务后，用 curl 走完创建、列表、回复、关闭。
- [ ] 性能：同一条 50 张卡的列表请求。超过 100 毫秒算失败。

## p1-cli

- [ ] 依赖：`p1-api` 已合并。
- [ ] 改这些文件：`melody/cli.py`、`tests/test_cli.py`。
- [ ] 做这一件事：`person add`、`ask`、`show`、`reply`、`inbox --hook`。`ask` 在写入前把附带和不附带的内容打到 stdout。`inbox --hook` 只打印数量、编号、标题和发起人。服务连不上时打印空内容并以 0 退出。
- [ ] 你能看见：两个 shell，A `ask` 给 B，B `show` 读到全文，B `reply` 之后 A 再 `show` 看到回复。
- [ ] 单测：预览文本包含附带项。`--hook` 在无待处理卡时 stdout 为空。
- [ ] 现场：按上面两个 shell 跑一遍，退出码 0。
- [ ] 性能：`--hook` 在服务不可达时 1 秒内返回。超过 1 秒算失败。

## p1-inbox

- [ ] 依赖：`p1-api` 已合并。等人看过页面再合并。
- [ ] 改这些文件：`melody/inbox.html`、`melody/server.py` 里提供该页面的路由、`tests/test_inbox.py`。
- [ ] 做这一件事：待我处理、我发出的、已完成。详情里有请求、附带、状态、往来和回复框。没有成员栏，没有新建卡。页面开着时新卡用浏览器通知。页面关着期间的卡，下次打开显示未读。
- [ ] 你能看见：B 开着页面时，A 发出的卡出现在待我处理，并弹出一次通知。
- [ ] 单测：列表 HTML 含卡号和请求摘要。
- [ ] 现场：浏览器里点开三列，回复一张卡，发起人点收到后它进入已完成。
- [ ] 性能：页面请求的卡片 JSON 与 `p1-api` 同一条失败线。

## p1-deeplink

- [ ] 依赖：`p1-inbox` 和 `p1-cli` 都已合并。等人点过按钮再合并。
- [ ] 改这些文件：`melody/inbox.html`、`melody/deeplink.py`。
- [ ] 做这一件事：详情页按钮「交给我的 Agent 处理」。链接只含「处理 melody 事项卡 <编号>」。Claude Code 与 Codex 带上由所属仓库和本地代码根拼出的目录。Cursor 不带目录，提示里写仓库名。链接不自动发送。
- [ ] 你能看见：点按钮后本机工具打开，输入框里是那句短提示，模型还没开始跑。
- [ ] 单测：生成的 URL 不含请求正文和附带内容。
- [ ] 现场：在装了 Claude Code 或 Codex 的机器上点一次。按回车后，Agent 用 `show` 读到卡。这一步在没有这些客户端的环境里做不到。
- [ ] 性能：无单独预算。生成链接是字符串拼接。

## p1-claude

- [ ] 依赖：`p1-cli` 已合并。等人在 Claude Code 里看过提醒再合并。
- [ ] 改这些文件：`plugins/claude/` 下的 skill 与 `SessionStart`、`UserPromptSubmit` 钩子配置。
- [ ] 做这一件事：skill 说明何时 `ask`、如何挑选附带内容、发送前展示预览、写回前要本人同意。钩子调用 `melody inbox --hook`。
- [ ] 你能看见：有未处理卡时，B 提交下一句提示，上下文里出现一句提醒。钩子本身不调用模型，也不改仓库。
- [ ] 单测：钩子命令行就是 `melody inbox --hook`，没有别的参数把正文传进去。
- [ ] 现场：在本机 Claude Code 里走 [mvp.md](mvp.md) 的 N1 与 N3。
- [ ] 性能：沿用 `p1-cli` 的钩子超时。

## p1-codex

- [ ] 依赖：`p1-cli` 已合并。与 `p1-claude` 无关。等人在 Codex 里看过提醒再合并。
- [ ] 改这些文件：`plugins/codex/`。若一个插件装不上 skill 和钩子，就分成两份配置，并在该 PR 里写明。
- [ ] 做这一件事：与 `p1-claude` 相同的发起、读取、回复和提醒。
- [ ] 你能看见：Codex 里复现 N1 与 N4。
- [ ] 单测：钩子命令与 Claude 侧相同。
- [ ] 现场：在本机 Codex 里走一遍。
- [ ] 性能：沿用 `p1-cli` 的钩子超时。

## 端到端

各 PR 的单测和 curl 只证明那一截。阶段 1 算做完，要在操作者机器上按 [mvp.md 的端到端验收](mvp.md#交付阶段-1-端到端验收) 跑通 E1 和 E2。E3 在 Codex 上补做。

通过时能看见这一条效果。A 在 Claude Code 里发出执行卡。B 开着的 inbox 出现这张卡并通知一次。B 下一句无关提示里只有一行卡号提醒。B 点按钮后工具只填好卡号，按回车后 Agent 读到全文并写回回复。A 点「收到」，卡进入已完成，结论就是那句回复。全程没有人把请求或回复从网页抄到工具里。问题卡由 B 在网页上直接回复并被 A 关闭，不打开 Agent。

E1 和 E2 的运行记录要留下卡号和每一步的原文。没有这份记录，阶段 1 不算通过。

## 这批 PR 证明不了的

本仓库的环境没有操作者的 Claude Code、Codex 和浏览器通知权限，所以上面的端到端不在这里跑。`p1-deeplink`、`p1-claude`、`p1-codex` 的现场栏也要在操作者机器上勾。企业微信、分享、Agent 是否正在处理、隔离 worktree 不在这批 PR 里。
