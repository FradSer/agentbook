---
name: railway-custom-domain-api
description: Production API custom domain migration status - agentbook-api.frad.me added on Railway, DNS records pending operator action
type: project
---

# Agentbook API 自定义域名迁移（进行中）

2026-08-24 为消除 GTM P0 减分项（信任类产品发布在 *.up.railway.app 上），给 agentbook-api 服务添加了自定义域名。

**Why:** 前端已用 `agentbook.frad.me`（CF 代理模式，2026-08-01 起），API 却还在 `agentbook-api-production.up.railway.app`，违反 docs/gtm-plan.md 的 P0 清单。

**How to apply:**
- Railway 侧已完成：customDomain id `19c5c28e-f579-4941-9e41-604565a7919c`，targetPort 8000，syncStatus ACTIVE
- 待用户在 Cloudflare（zone `4aad4336a4481ec91855e7737cefd30e`，frad.me）创建：
  - CNAME `agentbook-api` → `9j6urmfh.up.railway.app`（proxied，与前端惯例一致）
  - TXT `_railway-verify.agentbook-api` → `railway-verify=e95ea80c5dbbd344830fc5bad1680b9f45d6f20b9aa89b5312aab9d58cc5cbd0`
- 验证命令：`RAILWAY_CALLER=skill:use-railway@1.3.6 railway domain status agentbook-api.frad.me --service <api-id>`，Verified 变 yes 后用 `curl https://agentbook-api.frad.me/v1/search?q=test` 冒烟
- 生效后需把仓库内引用 `agentbook-api-production.up.railway.app` 的公开文案/技能逐步迁到新域名（旧域名继续可用）

**Related:** [[gtm-p0-checklist-status]]
