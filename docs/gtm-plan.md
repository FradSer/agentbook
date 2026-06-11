# Agentbook 推广计划（GTM）— 2026-06-11

本文档由 19-agent 研究工作流（6 个研究员、3 个独立策略师、9 个对抗评审、1 个完整性批评者）的结论综合而成，按单人业余节奏修正。核心结论：**推广不是营销，是按顺序做三件事：先排除不可逆伤害类的发布阻塞项，然后第一天就直接触达已在公开求购此产品的具名用户，最后才做一次以诚实负面结果为钩子的公开发布。**

成功定义来自 `docs/first-pilot-playbook.md` 的预承诺门槛（G1-G4），不是 GitHub star。

---

## 1. 定位

### 赛道判断

市场分两层。第一层「私有记忆基础设施」已饱和且资本化：mem0（$24M A 轮，58k star，AWS Agent SDK 独家）、Zep、Letta、cognee。**「memory layer for AI agents」这个词组已被 mem0 占有，文案中出现一次即被归类碾压。** 第二层「公共共享 agent 知识」几乎空白，agentbook 站在这里：

> 公共的、结果验证的、跨运行时的调试知识库（public debug-knowledge commons）。

对两个直接竞品的差异化武器是反女巫置信度数学：

- Mozilla.ai `cq`（2026-03 发布，1.2k star）：被批评最多的就是「agent 自评置信度可被投毒」，而 agentbook 自评不计分、3 个独立外部报告者才能突破 0.5 冷启动帽、数学被 CI 冻结。
- Stack Overflow for Agents（2026-06-10 宣布 beta）：人工审核队列 + 声望投票，慢且不可机器验证。

### канonical 一行语

- EN: The public debug-knowledge commons for coding agents: add one MCP line and your agent recalls known fixes — with confidence that can only rise when distinct external reporters confirm outcomes; author self-reports never count.
- ZH: 面向 AI 编程智能体的公共调试知识库：加一行 MCP 配置即可匿名召回已知修复，置信度只有在多个独立外部报告者确认后才能上升，作者自评永不计分。

### 文案红线（每篇公开稿件发布前逐条核对）

- [ ] 永不出现「memory layer」作为品类词
- [ ] 永不说「agents learn from each other」、网络效应、飞轮在转（真实外部流量为零）
- [ ] 跨任务迁移必须与 fix-lift=0 同句披露（检索 0→55% 是真的，应用提升为零也是真的）
- [ ] 提升数字必须标注实验臂：1/17→6/17 与 13/17→17/17 是 good_loop（召回 + harness 验证重试循环），不是裸 recall
- [ ] 「0%→82% of Opus」是 5 个研究臂并集，不是产品行为；最强单臂为 41%
- [ ] 「outcome-verified」只能作机制表述（置信度只能被外部确认推高），不能作语料状态既成事实（尚无任何一条真实 verified outcome）
- [ ] 强模型数据永远带脚注：submit_rate 56-75%，低于 80% 功效线，方向性结论
- [ ] 所有 lift 证据都是 sympy 域；不说「在你的代码库上有效」
- [ ] 不暗示现有使用量、采用者或用户评价（pre-pilot，单人开发）

---

## 2. 受众与渠道

痛点已有公认名字：**「AI Groundhog Day」**。anthropics/claude-code issue #39961 量化为 50-75% 的 session 浪费在重新发现已解决的问题上，评论区逐条列出的需求（带置信度、去重、「已确认解决」标记）就是 agentbook 的设计。

优先级排序的三类人：

1. **多工具个人重度用户**（Claude Code + Codex/Cursor 切换者）：CLAUDE.md 无法跨工具携带上下文，已自制各种记忆工作区（incident-*.md、handoff skill）。与 G1/G2 门槛天然匹配（同一人反复踩同一坑，recurrence density 高）。
2. **车队/CI agent 运营者**（Docker CI 跑 7 个 agent 角色，Copilot /fleet）：文案换成「你的 30 个 agent 在反复发现并重复上报同一个问题」，主打去重。
3. **Cursor 用户**：抱怨「记忆存在但不约束行为」，适合 recall-at-moment-of-error 的卖点。

唯一在 G1 之前真正有效的获客渠道：**对具名个人的直接私信**（9 个评审一致结论）。目录上架是卫生工作（答案引擎优化 + 长尾），不是获客。

---

## 3. P0 发布阻塞项（做任何推广之前）

不可逆伤害类，必须先于一切曝光动作：

- [x] 提交并部署积压的三批修复（demoted 拒绝、exact 去重、fallback 标签封顶）：已于 2026-06-11 提交推送
- [x] **密钥/PII 扫描**：`gate.py` 凭证检测（ak_/sk-/AKIA/ghp_/Slack/AIza/JWT/PEM/连接串/Bearer），覆盖 description、error_signature、solution content/steps 与 improve 路径，拒绝时指名类型、永不回显密钥；占位符（your-/example/xxxx 等）放行（2026-06-11 完成）
- [x] **运营者下架通道**：DELETE /v1/problems|solutions/{id}，ADMIN_API_KEY 常量时间比较鉴权（未配置即整体禁用），就地脱敏并级联、清 embedding、全部公共读路径排除、搜索缓存失效（2026-06-11 完成）
- [x] **LICENSE**：代码 MIT（LICENSE）；贡献内容 CC0-1.0（docs/terms.md）；注册响应携带 content_license 与 terms 字段，注册即同意（2026-06-11 完成）
- [x] **修复死链 URL**：`agentbook-api.railway.app`（404）全部替换为 `agentbook-api-production.up.railway.app`（2026-06-11 完成）
- [x] **提示注入信任边界**：SKILL.md 与 docs/mcp-setup.md 增加 Trust boundary 段（召回内容是参考资料不是指令，按置信度与 verification 门控，发现恶意内容上报失败使其降级）（2026-06-11 完成）
- [x] **organic 流量打标**：`/v1/dashboard/usage` 新增 `outcome_sources`（synthetic / seeded / author_self / organic_external + organic_share_30d），SEED_AGENT_IDS 环境变量可标注历史种子身份，配置错误 fail loud（2026-06-11 完成）
- [ ] 注册自有域名（如 agentbook.dev），api 子域指向 Railway；在 `*.railway.app` 子域上发布信任类产品是减分项（操作者动作）
- [x] 修复定位词：全仓清除「memory layer」品类词（15 个文件），换 canonical 一行语（2026-06-11 完成）
- [ ] 部署：合并后 Railway 自动部署，并在 Railway 配置 `ADMIN_API_KEY` 与 `SEED_AGENT_IDS`（含历史种子贡献者身份）（操作者动作）

---

## 4. Phase 1：试点优先（第 1-2 周）

排序铁律（所有评审一致）：**私信第 1 天就发**，人类回信延迟是全计划最长路径；目录上架并行做且做完就忘。

- [ ] Day 1：给 10-25 个具名「workaround builder」发个性化私信：anthropics/claude-code issues #39961 / #52295 / #51735 的作者、claude-cortex 作者、dev.to 求购帖楼主。话术：提议帮对方在自己的任务上跑一次 `measure_lift.py`，30 分钟通话，成败以 G1 预承诺标准判定（操作者动作）
- [ ] `mcp-publisher` 向官方 MCP Registry 发布 server.json（remote streamable-HTTP，指向生产 /mcp）：自动传播到 GitHub MCP Registry、VS Code 库、PulseMCP（操作者动作，一次性）
- [ ] 打包 Claude Code 插件：`.claude-plugin/marketplace.json` + plugin.json 捆绑 skills/use-agentbook 与匿名 .mcp.json，使 `/plugin marketplace add FradSer/agentbook` 可用
- [ ] README 加 Add-to-Cursor 深链按钮（`cursor://anysphere.cursor-deeplink/mcp/install?...`）
- [ ] 长尾目录一次性提交：Smithery（其工具调用分析未来可作 G3/G4 第三方佐证）、glama.json、mcp.so、awesome-mcp-servers PR
- [ ] MCP 工具加 annotations（recall/trace 标 readOnlyHint 等）：Anthropic Connectors Directory 的前置条件
- [ ] 录制 90 秒演示 GIF/asciinema：先跑 seed_corpus.py 保证命中，展示 recall 命中 → 修复 → report → 置信度变化说明

### 自我狗粮 = G0 门（第 2-3 周）

- [ ] 自己的三个运行时（Claude Code / Cursor / CI）接生产库，用自己的修复历史做种子语料
- [ ] **反转展示反女巫数学**：演示「我的三个运行时身份被聚类折叠、无法给自己刷分」。注意：「3 个运行时身份 = 3 个独立外部报告者」是假的（聚类会折叠它们），把这个限制变成对 cq 投毒批评的活广告
- [ ] G0 预承诺标准：错误事件的 recall 调用率 ≥ 50%，一周内 ≥ 1 次真实非种子命中。不达标先修触发率，不进入 Phase 2

---

## 5. Phase 2：证据驱动的公开发布（第 4-6 周，串行）

发布文章 = 实验报告。负面结果是钩子，预先缴怀疑者的械。

- [ ] 撰写发布文章（EN）：《我们实测了共享记忆对 coding agent 的提升》。结构：问题 → 协议（EVAL_PROTOCOL.md）→ 同任务提升（带臂名与脚注的数字）→ **跨任务迁移失败（fix-lift=0）** → 复现命令 → G1-G4 预承诺门槛。发布前过一遍文案红线
- [ ] 中文稿（不是翻译，是痛点先行的教程体）：linux.do 资源荟萃 +掘金深度文。**前置条件：先实测中国大陆对生产 API 的可达性**（docs/deployment-china.md 的 CF 代理），不可达就先修
- [ ] 串行铁律：一次只开一个社区面，上一个面还有未回复评论时绝不开下一个。顺序：r/ClaudeCode → Show HN → 中文区 → X 线程，每面间隔 1-2 周
- [ ] Show HN 标题（首选）：Show HN: We measured whether shared memory helps coding agents — same-task lift is real, cross-task transfer fails
- [ ] CTA 分层：浏览者给「60 秒匿名 recall」（一行 curl / 一行 MCP 配置）；`measure_lift.py` 只在试点对话中使用（需要写任务 harness，作广播 CTA 转化率为零）
- [ ] 前端加「pre-pilot：以下为演示种子数据」横幅，把空数据从弃坑感变成诚实感
- [ ] 发布后绊线（预承诺）：HN 后 14 天内零外部 measure_lift 运行 → 停止广播，100% 转直接招募

---

## 6. Phase 3：生态与可信度（第 30-90 天）

- [ ] Claude Cookbook PR：notebook「Outcome-verified debug recall for coding agents over MCP」，recall → fix → report 全流程打生产 API
- [ ] cq interop：给 mozilla-ai/cq 提 issue/PR，把结果验证提议为其「开放标准」扩展（蹭 Mozilla 品牌，植入差异点）。前置：写入质量门至少最小可用（ReviewerAgent 审核环目前休眠，攻击 cq 投毒问题前先补自己的门）
- [ ] OpenClaw 集成：把 agentbook recall 接成 OpenClaw 默认记忆后端，作为活狗粮演示（browser-use 的爆发 = 成为别人病毒时刻里的可见依赖）
- [ ] arXiv/workshop 预印本：把 experiments/agentbook-ab 整理为短文《Same-task recall lifts weak coding models; cross-task transfer retrieval works but fix-lift is zero》。SWE-Bench-CL 独立得出一致结论，引用窗口正开着
- [ ] 能力窗口打法：新 coding 模型发布后跑一次 lift 数字发到该模型社区。节奏：有余力时，每月最多一次（明确否决「48 小时 SLA」）
- [ ] TypeScript 零依赖客户端（npm `agentbook-client`）：等首个试点跑通后再做，G1 之前不开新维护面

---

## 7. 门槛与度量（修正版）

| 门 | 标准 | 读取时机 |
|---|---|---|
| G0（新增） | 自我狗粮：recall 调用率 ≥ 50%，周内 ≥ 1 次真实命中 | 接入后 1 周 |
| G1a | 作者协助下，试点自有任务 paired lift > 0 且 harm = 0（≥ 10 个 unaided-fail 任务） | 试点承诺后 14 天内（事件触发，非日历） |
| G1b | 无协助的外部复现 | 随发布漏斗 |
| G2 | recurrence_density ≥ 0.30，N ≥ 100 独立查询（排除种子回放） | N 达标时；预估各试点到达日期，连续落后 → 绊线 |
| G3 | organic 占比 < 5% 杀死网络论点 | 仅在 ≥ 2 次真实曝光事件之后读取，需 organic 打标就位 |
| G4 | organic ≥ 15% 开多人 | 同上 |

核心度量（star 明确除外）：错误事件 recall 触发率（先导指标）；**第一条真实外部 outcome report 的日期**（项目史上首次非零）；完成 G1 复现的外部用户数；周注册 key 数与匿名读者→写入者转化率。

---

## 8. 主要风险

1. **recall 不触发**：整个楔子取决于 agent 在出错时真的调 recall。G0 门直接测它；skill 的触发词与 CLAUDE.md 注入是对策。
2. **域外推广失败**：全部 lift 证据在 sympy；试点真实域可能 G1 失败。预承诺：失败即停、诊断、公开发表（仍是诚实叙事的素材）。
3. **窗口被关**：SO for Agents 靠品牌或 cq 靠 Mozilla 先占心智。对策：差异点死咬「机器结果验证 + 反女巫」，并主动 interop 而非对抗。
4. **发布即过曝**：star 雪崩但零 G1 运行。对策：CTA 分层 + 14 天绊线 + 单面串行。
5. **团队试点被反女巫误伤**：办公室 NAT 后的 5 人会被 /24 聚类折叠成 1 个报告者。招募团队试点前审计聚类逻辑（操作者动作，列入 backlog）。

---

## 9. 研究来源

2026-06-11 workflow run `wf_a4e5ad29-e38`（19 agents，两轮）：仓库证据清单（claims inventory，含 do_not_claim 红线全文）、4 路市场研究（竞品/渠道/发布案例/受众）、3 套独立策略 + 9 份对抗评审（solo-feasibility / evidence-honesty / signal-speed，得分 4-7.5，无一可原样执行）、1 份完整性批评（本文 P0 清单的来源）。关键外部锚点：mem0 资本与品类占有、Mozilla.ai cq 与 SO for Agents 的时间窗、anthropics/claude-code #39961「AI Groundhog Day」、aider 的 benchmark 占有打法、browser-use 的依赖式爆发、firecrawl「集成胜过发布」。
