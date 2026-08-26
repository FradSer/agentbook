---
name: railway-custom-domain-api
description: agentbook-api.frad.me restored 2026-08-26 - root cause was targetPort 8000 vs actual $PORT 8080, plus missing Cloudflare DNS records; Gemini+OpenRouter keys still need rotation
type: project
---

# Agentbook API 自定义域名（已恢复，2026-08-26）

## Why
前端 `NEXT_PUBLIC_API_URL` 指向 `https://agentbook-api.frad.me`。该域曾因两层问题完全不可用（HTTP:000→502），导致前端"数据库挂了"的表象；数据库与直连域一直正常。

## 根因与修复（两层叠加）
1. **Cloudflare 无 DNS 记录**：8/24 加自定义域后操作员侧 CNAME/TXT 从未创建。已补建：
   - CNAME `agentbook-api` → `9j6urmfh.up.railway.app`（proxied）——这是 Railway `domain status` 要求的目标
   - TXT `_railway-verify.agentbook-api` → `railway-verify=e95ea80c...cbd0`
2. **targetPort 错配（真正的 502 元凶）**：自定义域声明 targetPort=8000，但应用实际监听 Railway 注入的 `$PORT`=8080 → 边缘报 "Application failed to respond"。已改 targetPort=8080。
   - 教训：诊断自定义域 502 时先对 `domain status` 的 targetPort 与部署日志里 uvicorn 实际端口。

## 已知坑
- 旧别名 `9j6urmfh.up.railway.app` 曾返回边缘 404 "Application not found"（SNI 路由视角），但 `domain status` 仍要求它作为 CNAME 目标且证书 VALID——以 CLI status 为准，勿凭边缘探测否定目标。
- Host Header Origin Rule 需要 CF 付费版（free 报 not entitled）。
- 本地网络对 frad.me/googleapis/voyage 部分阻断：验证用 Cloudflare Workers 探针或 DoH(1.1.1.1 按 IP)。

## 待办（用户操作）
- 轮换失效 key：GEMINI_API_KEY（400 INVALID_ARGUMENT）、OPENROUTER_API_KEY（401 User not found）。Voyage 正常。FailoverEmbeddingProvider 会自动吸收新 key（60s 冷却后），无需重部署。
- 前端当前用直连域 agentbook-api-production.up.railway.app（立即恢复用）；frad.me 现已可用可切回。

**Related:** [[gtm-p0-checklist-status]]
