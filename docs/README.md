---
description: "melody 团队 Agent 协作对话板的产品目标、MVP 范围与线框、架构方案及决策记录导航。"
---

# melody：团队 Agent 协作对话板文档入口

melody 让团队成员与各自的 Personal Agent 在同一个 `#thread` 直接交流、澄清和交接工作，并在所有者确认后通过隔离 `git worktree` 交给原有 coding 客户端执行。当前文档已完成规划评审与关键决策拍板，等待授权启动单客户端联动试验。

- [产品目标](product.md)：`#thread` 人机协作定位、两条协作路径（问答 vs 执行）、完整用户旅程与演进方向。
- [当前 MVP 与试验设计](mvp.md)：已拍板的 5 项核心决策、必做与不做边界、3 张手机可读低保真线框（突出 worktree 来源展示）、单客户端试验矩阵与四阶段计划。
- [架构方案](architecture.md)：最小数据关系与状态流转、`WorktreeProvenance` 五项来源透明规则、最小适配器幂等接口与断线防重契约。
- [决策记录 ADR-001](adr/0001-thread-collaboration-and-native-handoff.md)：为何转向 `#thread` 协作对话板，以及手动唤起、新建原生可见会话、本地 `attempt_id` 防重与 `git worktree` 透明隔离的拍板依据。

文档维护规则见 [AGENTS.md](AGENTS.md)。早期“云端 Docker 沙箱单仓库修复”方向的历史规格已归档至 [archive/cloud-sandbox-v0/](archive/cloud-sandbox-v0/)，早期底座调研保留在 [conductor-base-eval/](../conductor-base-eval/)，均不作为当前交付目标。
