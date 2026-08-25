---
name: gtm-p0-checklist-status
description: Verified status of docs/gtm-plan.md P0 launch blockers as of 2026-08-24 - config items done, domain migration in progress
type: project
---

# GTM P0 清单实际完成状态（2026-08-24 核实）

**Why:** gtm-plan.md 第 3 节的复选框滞后于现实，避免重复做已完成的项。

**How to apply:**
- `ADMIN_API_KEY` 与 `SEED_AGENT_IDS`（33 个种子身份）已在 Railway agentbook-api 服务配置好——清单里"操作者动作"一项实际已完成
- 自有域名：无需新注册（frad.me 已在用）；前端 `agentbook.frad.me` 2026-08-01 起 ACTIVE；API 域名迁移进行中（见 [[railway-custom-domain-api]]）
- 生产数据基线：150 problems / 62 outcomes 全为存量；last_30d 活动 = 0（截至 2026-08-24）。recurrence-density 面板的 RD=0.76/organic=0.62 是自测流量灌水值，不可当 G2/G3 证据
- Codex 狗粮试点 ledger（~/.local/share/agentbook/pilot.jsonl）仅 10 条事件，最后一条 2026-08-01；G0 门未判定

## 2026-08-24 会话增量

- Landing page 转化优化已提交部署（4ee8ae9）：痛点 H1、按钮 CTA、seeded-corpus 诚实标注、底部重复 CTA、meta description 红线修复
- MCP annotations 已提交（221f029）：6 工具全部声明 ToolAnnotations，Connectors Directory 前置条件就绪
- 分发打包已提交（6d08a75）：server.json（MCP Registry）、.claude-plugin/ 插件、双语 README Cursor 深链。**注意：server.json 已创建但尚未发布到 registry——发布需操作者运行 `npx mcp-publisher login`（GitHub OAuth）后 publish；目录提交（Smithery 等）也是手动网页动作**
- 私信模板已完成：`.outreach-drafts/dm-templates-en.md`（gitignored，本地私有），3 变体 + bump，基于真实 issue 引文；how-it-works 链接指向线上页
- 发布文章骨架已提交（907405b + ffd3230）：`docs/launch-post-draft-en.md`，六段结构、数字全带证据索引 S1-S7，G0/G1 结果留占位符——填槽即可发布
- 目录提交材料包已完成：`.outreach-drafts/directory-submissions-kit.md`（本地私有），Smithery/Glama/MCP.so/awesome-mcp-servers 逐字段粘贴值，awesome 条目为 diff-ready 格式

**Related:** [[railway-custom-domain-api]]
