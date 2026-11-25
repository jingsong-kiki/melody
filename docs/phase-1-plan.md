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

性能条在本机测量。失败线是 50 张卡的列表接口超过 100 毫秒。仓库里还没有服务，所以基线是「没有进程」。每个带接口的 PR 用同一条计时命令量自己的列表或等价读取。性能不放进功能测试里，避免一次变慢被别的断言盖住。

## 测试

测试按 [architecture.md](architecture.md) 的边界来写。每一层只断言调用方看得到的结果，也就是状态、HTTP 响应、命令输出和页面正文。不断言内部函数有没有被调用。换一种实现而对外结果不变时，测试应保持通过。

服务端和数据库用真实进程、临时的 SQLite 文件。测完删除。不把它们换成假对象。不连接操作者自己的 `MELODY_URL`。不调用模型，不启动 Claude Code、Codex 或浏览器通知。

| 层 | 怎么驱动 | 要看见 | 文件 | 从哪一截开始 |
|---|---|---|---|---|
| L1 状态 | 调用卡片模块的公开操作 | 状态转移，以及不允许的操作被拒绝后状态不变 | `tests/test_card.py` | `p1-schema` |
| L2 接口 | 临时端口上的真实 HTTP | 令牌、附带内容是否保存、钩子列表不改状态、SSE 收到新卡 | `tests/test_api.py` | `p1-api` |
| L3 命令行 | 子进程执行命令行，对面是真实服务 | 预览出现在写入之前，钩子的 stdout 和退出码 | `tests/test_cli.py` | `p1-cli` |
| L4 页面和链接 | 用 HTTP 取回 inbox 页面 | 人能读到的列表名、请求和附带内容。链接里没有正文 | `tests/test_inbox.py` | `p1-inbox`，链接在 `p1-deeplink` |
| L5 自动化闭环 | 同一次进程里走完一张卡 | [mvp.md 的自动化闭环](mvp.md#自动化闭环) | `tests/test_e2e.py` | `p1-cli` 起覆盖命令行路径，`p1-inbox` 起加上页面 |
| L6 操作者 | 人按 E1、E2、E3 操作 | 卡号和每一步原文 | 跑完后写 `docs/runs/phase-1.md` | 插件和 deep link 都落地之后 |

自动化部分一条命令：

```text
python -m unittest discover -s tests
```

退出码 0 才算过。当时还没有的层不在这轮的目录里，所以早期 PR 只跑已经落地的文件。`p1-cli` 合并之后，`tests/test_e2e.py` 必须在里面，并且退出码为 0。

L4 看的是页面返回的正文里有没有「待我处理」和这张卡的请求。不把页面源码里出现卡号当成浏览器通知已经弹出，也不当成 E1 通过。

插件那一层只检查配置里的钩子命令是 `melody inbox --hook`，并且没有参数把正文传进去。Claude 或 Codex 有没有把这句话放进上下文，只在 L6 看。

L6 的做法：

1. 先让上面的 unittest 退出码为 0。
2. 在操作者机器上起服务。A 和 B 的本机配置指向同一个 `MELODY_URL`。
3. 按 [E1](mvp.md#e1-执行卡claude-code) 做执行卡，再按 [E2](mvp.md#e2-问题卡网页回复) 做问题卡。Codex 按 [E3](mvp.md#e3-codex-上的同一路径)。
4. 把卡号和每一步看到的原文写进 `docs/runs/phase-1.md`，并在 mvp 的端到端验收下链到这个文件。

这个文件现在还没有。阶段 1 还没在操作者机器上跑过。

## p1-schema

- [ ] 依赖：无。从 `docs/initial-planning` 拉分支。
- [ ] 改这些文件：`melody/db.py`、`melody/card.py`、`tests/test_card.py`。
- [ ] 做这一件事：建 `persons`、`endpoints`、`cards`、`card_participants`、`card_attachments`、`card_entries`、`read_marks`。卡片状态只有待处理、已读、已回复、已关闭。接收人恰好一个。读者列表为空。关闭只能由发起人触发。
- [ ] 你能看见：测试进程里 A 发给 B 一张执行卡，B 读过后是已读，B 回复后是已回复，A 关闭后是已关闭，并且记下结论。
- [ ] 测试：L1。四次状态变化。接收人关闭被拒绝且状态不变。只读不改状态。
- [ ] 现场：`python -m unittest tests/test_card.py` 退出码 0。
- [ ] 性能：插入 50 张卡后列出 B 的待处理卡，计时。超过 100 毫秒算失败。

## p1-api

- [ ] 依赖：`p1-schema` 已合并。
- [ ] 改这些文件：`melody/server.py`、`tests/test_api.py`。
- [ ] 做这一件事：带个人令牌的 HTTP。创建卡、读取卡、回复、关闭、按角色列出。页面打开时用 SSE 推新卡。
- [ ] 你能看见：A 的 curl 创建 W-42，B 的 curl 在待处理列表里读到请求和附带内容。
- [ ] 测试：L2。真实 HTTP。令牌不对则拒绝，响应里没有正文。只保存列出的附带内容。钩子列表不改状态。打开的 SSE 能收到新卡。
- [ ] 现场：`python -m unittest tests/test_api.py` 退出码 0。行为以这条测试为准，不另维护一套只在手工 curl 里才检查的步骤。
- [ ] 性能：同一条 50 张卡的列表请求。超过 100 毫秒算失败。

## p1-cli

- [ ] 依赖：`p1-api` 已合并。
- [ ] 改这些文件：`melody/cli.py`、`tests/test_cli.py`。
- [ ] 做这一件事：`person add`、`ask`、`show`、`reply`、`inbox --hook`。`ask` 在写入前把附带和不附带的内容打到 stdout。`inbox --hook` 只打印数量、编号、标题和发起人。服务连不上时打印空内容并以 0 退出。
- [ ] 你能看见：两个 shell，A `ask` 给 B，B `show` 读到全文，B `reply` 之后 A 再 `show` 看到回复。
- [ ] 测试：L3。预览出现在写入之前。没有待处理卡时钩子 stdout 为空。服务不可达时钩子输出为空且退出码为 0。
- [ ] 现场：`python -m unittest tests/test_cli.py tests/test_e2e.py` 退出码 0。这一截的闭环还不断言页面。
- [ ] 性能：`--hook` 在服务不可达时 1 秒内返回。超过 1 秒算失败。

## p1-inbox

- [ ] 依赖：`p1-api` 已合并。等人看过页面再合并。
- [ ] 改这些文件：`melody/inbox.html`、`melody/server.py` 里提供该页面的路由、`tests/test_inbox.py`。
- [ ] 做这一件事：待我处理、我发出的、已完成。详情里有请求、附带、状态、往来和回复框。没有成员栏，没有新建卡。页面开着时新卡用浏览器通知。页面关着期间的卡，下次打开显示未读。
- [ ] 你能看见：B 开着页面时，A 发出的卡出现在待我处理，并弹出一次通知。
- [ ] 测试：L4。页面正文里有三列的名字、卡号、请求和附带内容，没有新建卡的入口。L5 加上同一条页面断言。
- [ ] 现场：人在浏览器里点开三列，回复一张卡，发起人点收到后它进入已完成。浏览器通知留到 L6。
- [ ] 性能：页面请求的卡片 JSON 与 `p1-api` 同一条失败线。

## p1-deeplink

- [ ] 依赖：`p1-inbox` 和 `p1-cli` 都已合并。等人点过按钮再合并。
- [ ] 改这些文件：`melody/inbox.html`、`melody/deeplink.py`。
- [ ] 做这一件事：详情页按钮「交给我的 Agent 处理」。链接只含「处理 melody 事项卡 <编号>」。Claude Code 与 Codex 带上由所属仓库和本地代码根拼出的目录。Cursor 不带目录，提示里写仓库名。链接不自动发送。
- [ ] 你能看见：点按钮后本机工具打开，输入框里是那句短提示，模型还没开始跑。
- [ ] 测试：L4。页面上的链接不含请求正文和附带内容。提示只有固定句式和卡号。
- [ ] 现场：在装了 Claude Code 或 Codex 的机器上点一次。按回车后，Agent 用 `show` 读到卡。没有这些客户端时，这一步记为未验证，链接文本测试不能代替它。
- [ ] 性能：无单独预算。生成链接是字符串拼接。

## p1-claude

- [ ] 依赖：`p1-cli` 已合并。等人在 Claude Code 里看过提醒再合并。
- [ ] 改这些文件：`plugins/claude/` 下的 skill 与 `SessionStart`、`UserPromptSubmit` 钩子配置。
- [ ] 做这一件事：skill 说明何时 `ask`、如何挑选附带内容、发送前展示预览、写回前要本人同意。钩子调用 `melody inbox --hook`。
- [ ] 你能看见：有未处理卡时，B 提交下一句提示，上下文里出现一句提醒。钩子本身不调用模型，也不改仓库。
- [ ] 测试：钩子配置的命令是 `melody inbox --hook`，没有把正文传进去的参数。
- [ ] 现场：在本机 Claude Code 里走 [mvp.md](mvp.md) 的 N1 与 N3。上下文里是否出现提醒，只在这里和 L6 看。
- [ ] 性能：沿用 `p1-cli` 的钩子超时。

## p1-codex

- [ ] 依赖：`p1-cli` 已合并。与 `p1-claude` 无关。等人在 Codex 里看过提醒再合并。
- [ ] 改这些文件：`plugins/codex/`。若一个插件装不上 skill 和钩子，就分成两份配置，并在该 PR 里写明。
- [ ] 做这一件事：与 `p1-claude` 相同的发起、读取、回复和提醒。
- [ ] 你能看见：Codex 里复现 N1 与 N4。
- [ ] 测试：钩子命令与 Claude 侧相同。
- [ ] 现场：在本机 Codex 里走一遍 N1 与 N4。
- [ ] 性能：沿用 `p1-cli` 的钩子超时。

## 端到端

两道都要过，定义在 [mvp.md 的端到端验收](mvp.md#交付阶段-1-端到端验收)。

自动化闭环是 `python -m unittest tests/test_e2e.py`。它证明命令行、服务和页面在同一次事项里对得上。它不证明浏览器通知，也不证明 Claude 或 Codex。

操作者一道按该文的 E1 和 E2 做。E3 在 Codex 上补做。记录写进 `docs/runs/phase-1.md`。没有这份记录，阶段 1 不算通过。

## 这批 PR 证明不了的

本仓库的环境没有操作者的 Claude Code、Codex 和浏览器通知权限。L6 和 `p1-deeplink`、`p1-claude`、`p1-codex` 的现场栏要在操作者机器上勾。L1 到 L5 可以在没有这些客户端的环境里跑。企业微信、分享、Agent 是否正在处理、隔离 worktree 不在这批 PR 里。
