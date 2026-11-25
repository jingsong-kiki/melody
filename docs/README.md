---
description: "melody 事项卡 inbox 的产品目标、分阶段 MVP 范围与线框、架构方案及决策记录导航。"
---

# melody：事项卡 inbox 文档入口

melody 让团队成员在原有 coding 客户端一句话把一件事发成事项卡交给同事；同事自己回答，或一键交给自己 coding 客户端里的 Agent 处理，结果回到同一张卡上。它不是新的聊天软件，只提供承载事项卡的 inbox 页面。当前交付范围是交付阶段 1：插件创建事项卡、inbox 展示与浏览器通知、钩子提醒、一键交给自己的 Agent。

- [产品目标](product.md)：连接层定位、问题卡与执行卡、接收人的三种处理方式、界面分工、用户旅程、三个交付阶段与知识沉淀等后续方向。
- [当前 MVP 与分阶段交付](mvp.md)：已拍板决策、交付阶段 1 的范围、线框与试验矩阵，执行交接单客户端实测记录与阶段计划。
- [阶段 1 实施计划](phase-1-plan.md)：先做哪一块、改哪些文件、用什么命令验证。部件设计见架构。
- [架构](architecture.md)：状态放在哪、部件职责、事项卡数据与不变量、状态机，以及插件、inbox、企业微信和本机执行适配器的接口。落地顺序不在这里。
- [决策记录 ADR-001](adr/0001-thread-collaboration-and-native-handoff.md)：手动唤起、新建原生可见会话、本地 `attempt_id` 防重与 `git worktree` 透明隔离的依据；其 `#thread` 载体与 Agent 独立身份已被后续 ADR 取代。
- [决策记录 ADR-002](adr/0002-inbox-cards-instead-of-chat.md)：为何用事项卡 inbox 取代自建对话板，以及企业微信联动后置。
- [决策记录 ADR-003](adr/0003-cards-addressed-to-people.md)：为何事项卡发给人、去掉个人总代理，以及用 deep link 一键交给自己的 Agent。

文档维护规则见 [AGENTS.md](AGENTS.md)。早期“云端 Docker 沙箱单仓库修复”方向的历史规格已归档至 [archive/cloud-sandbox-v0/](archive/cloud-sandbox-v0/)，不作为当前交付目标。
