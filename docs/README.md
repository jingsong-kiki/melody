---
description: "melody 事项卡 inbox 的产品目标、分阶段 MVP 范围与线框、架构方案及决策记录导航。"
---

# melody：事项卡 inbox 文档入口

melody 让团队成员在原有 coding 客户端一句话把一件事发成事项卡，交给同事的 Personal Agent 回答或执行，结果回到同一张卡上验收；它不是新的聊天软件，只提供承载事项卡的 inbox 页面。当前交付范围是交付阶段 1：事项卡创建、inbox 展示与通知。

- [产品目标](product.md)：连接层定位、问题卡与执行卡、原工具 / inbox / 企业微信三个界面分工、用户旅程与三个交付阶段。
- [当前 MVP 与分阶段交付](mvp.md)：已拍板决策、交付阶段 1 的范围、线框与试验矩阵，执行交接单客户端实测记录与阶段计划。
- [架构方案](architecture.md)：事项卡数据关系与状态、创建与通知链路及钩子契约、企业微信通道接入点、`WorktreeProvenance` 与适配器幂等接口。
- [决策记录 ADR-001](adr/0001-thread-collaboration-and-native-handoff.md)：手动唤起、新建原生可见会话、本地 `attempt_id` 防重与 `git worktree` 透明隔离的依据；其 `#thread` 载体已被 ADR-002 取代。
- [决策记录 ADR-002](adr/0002-inbox-cards-instead-of-chat.md)：为何用事项卡 inbox 取代自建对话板，以及企业微信联动后置到交付阶段 2。

文档维护规则见 [AGENTS.md](AGENTS.md)。早期“云端 Docker 沙箱单仓库修复”方向的历史规格已归档至 [archive/cloud-sandbox-v0/](archive/cloud-sandbox-v0/)，不作为当前交付目标。
