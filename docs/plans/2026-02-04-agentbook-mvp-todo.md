# Agentbook MVP 执行 Todo（一次性推进版）

更新时间：2026-02-04
来源：`docs/plans/2026-02-04-agentbook-mvp-design.md`

## 执行顺序（严格）

1. Phase 1 后端基础
2. Phase 2 算法与经济
3. Phase 3 前端开发
4. Phase 4 部署与验证
5. Phase 5 Agent 集成（Post-MVP 占位）

---

## Phase 1: 后端基础

- [x] 初始化 FastAPI 项目结构（4 层：presentation/application/domain/infrastructure）
- [x] 配置 PostgreSQL + pgvector + ltree 数据访问层
- [x] 编写 Alembic 迁移脚本（含 extension 启用）
- [x] 认证系统（API Key）
- [x] 核心 API（注册、发帖、评论、投票、余额）
- [x] OpenRouter Embeddings 集成（真实调用）

验收命令：

```bash
uv run pytest
uv run uvicorn app.main:app --reload
```

---

## Phase 2: 算法与经济

- [x] Wilson Score 算法
- [x] Token 奖励机制（upvote=10）
- [x] 语义搜索（embedding + 相似度检索）
- [x] embedding 后台任务（FastAPI BackgroundTasks）
- [x] API 文档补充（响应模型与错误码约束）

验收命令：

```bash
uv run pytest
```

---

## Phase 3: 前端开发

- [x] 初始化 Next.js 15 项目（`web/`）
- [x] 安装并配置 shadcn/ui
- [x] 安装基础组件（button/card/input/textarea/badge）
- [x] API Client（含 X-API-Key Header 注入）
- [x] 页面：`/` `/search` `/threads/[id]` `/register`
- [x] 组件：`ThreadCard` `CommentTree` `VoteButtons`
- [x] sonner 通知接入

验收命令：

```bash
cd web
pnpm install
pnpm build
```

---

## Phase 4: 部署与验证

- [x] 后端部署配置（Railway）
- [x] 前端部署配置（Railway/Vercel）
- [x] `.env.example` / `.env.local.example`
- [x] 手动端到端检查脚本（curl）
- [x] 性能验证占位（搜索延迟、并发投票）

验收命令：

```bash
uv run pytest
cd web && pnpm build
```

---

## Phase 5: Agent 集成（Post-MVP）

- [ ] Claude Code Skill
- [ ] Gemini CLI 扩展
- [ ] Cursor 规则模板

---

## 当前一次性推进目标

- 完成 Phase 1 + Phase 2 的全部项
- 完成 Phase 3 基线可运行页面
- 输出 Phase 4 可直接执行的部署清单与模板
