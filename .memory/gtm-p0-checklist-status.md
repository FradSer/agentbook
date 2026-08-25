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

**Related:** [[railway-custom-domain-api]]
