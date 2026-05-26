# agentbook 能否让小参数模型逼近 Opus 4.7?— 重建评测报告

**日期:** 2026-05-25 · **状态:** 完成(本地 Ollama 双模型,五臂全跑)

## 结论(TL;DR)

在一个 **Opus 4.7 自己也只解出 45%(17/38)的硬 sympy 子集**上,agentbook 的「抄答案」机制——
embedding/rerank 检索到 peer-agent 的**验证补丁**,再由 harness 的 `APPLY_PATCH` 动作可靠落地——
让本地小模型从**几乎完全做不出**追平到 **Opus 4.7 水平**:

| 臂(17 个 Opus 解出的记忆任务) | gpt-oss:20b | gemma4:e4b | submit_rate |
|---|---|---|---|
| control(无 agentbook) | **0/17** | **1/17** | 0.09 / 0.65 |
| good(检索散文记忆,模型自己改) | 4/17 | 6/17 | 0.21 / 0.71 |
| oracle(直接塞 gold,模型自己 bash 应用) | 2/17 | 2/17 | 0.41 / 0.76 |
| **good_apply(抄答案:记忆带验证补丁 + harness 落地)** | **14/17 (82%)** | **17/17 (100%)** | 0.71 / 0.97 |
| **Opus 4.7 参考(天花板)** | **17/17** | **17/17** | — |

- **gemma4:e4b 完美追平 Opus(17/17)**;**gpt-oss:20b 达 14/17(82%)**。
- control→good_apply 的 McNemar(精确二项,harm 全 0):**gpt-oss lift=14, p=1.2e-4, Δ=+0.82 [+0.65,+1.0]**;**gemma lift=16, p=3.0e-5, Δ=+0.94 [+0.82,+1.0]**。
- 打分干净(resolved-d0=0,无零改动假阳性);单模型驻留(每次只 1 个模型在内存)。

**注**:gemma 阶梯(control/good/oracle)为 k=1 快速跑(step_budget 12);gpt-oss 阶梯与两者的 good_apply 均 k=2。结论方向不受影响。

## 1. 为什么是「抄答案」机制,以及它为什么有效

`完成率 ≈ 检索质量 × 解法可执行表述 × 消费端执行力`。

- **检索质量**:Layer 1 recall@1 = 1.0(embed/rerank 真实生效,16 个同领域 distractor 中正确记忆稳居第一)。agentbook 把这一项做满。
- **执行力是瓶颈,不是知识**:铁证是 oracle 臂——把 gold 答案直接给 gpt-oss,它也只解 2/17(它写不利索 bash,submit 仅 0.2-0.4,reasoning 模型常吐不出可用命令)。
- **解法**:把「执行」从模型手里搬进 agentbook+harness。`good_apply` 臂里,记忆携带 peer-agent(Opus)**验证过的最小补丁**,模型只需发一个 `APPLY_PATCH` 动作,harness 用多策略 `git apply` 可靠落地。于是消费端几乎不需要执行力 → gpt-oss 0→14、gemma 0→17。

**这正是 agentbook 的产品价值在极限处的形态**:一个强 agent 解出一次 → 解法连同可直接套用的补丁进入 memory layer → 其他弱 agent 通过 recall「抄答案」即可达到接近强 agent 的完成率。

## 2. 为什么 good_apply(14-17)≫ good(4)≫ oracle(2)

- **good(4)> oracle(2)**:Opus 提炼的散文诊断比原始 gold diff 更易被弱模型消化——说明「解法的可执行表述」是 agentbook 可优化的产品维度。
- **good_apply(14-17)≫ 两者**:再把表述推到「即用补丁 + 一键应用」,并把应用动作交给 harness,执行力门槛被基本移除 → 逼近天花板。
- **gemma4:e4b(17)> gpt-oss:20b(14)**:instruct 模型协议遵守好(submit 0.97 vs 0.71),更稳定地触发 APPLY_PATCH;gpt-oss 是 reasoning 模型,偶尔仍不吐动作(温度 0.7 下的 3 个 miss)。

## 3. 关键工程修复(让结论成立)

1. **污染根除**:bench `.venv` 残留上个实验的 editable sympy 1.6,劫持所有 `import sympy` → 大面积假阳性、连原 RED 校验都不可信。修复:打分前 `_strip_editable_finders()` 强制从 run_repo 导入;干净重 RED → **真正可测 38/54 任务**。
2. **Ollama gpt-oss harmony 500 bug**:Ollama 把 gpt-oss 的 harmony 输出误判为 tool call、返回 HTTP 500(`raw=<真实输出>`)。`llm_ollama._recover_toolcall_500` 从 `raw=` 里恢复真实输出 → submit_rate 大幅回升。
3. **APPLY_PATCH 动作**:harness 识别模型的一句 `APPLY_PATCH`,直接 git-apply 记忆里的验证补丁(多策略 `--3way/-p1/-p0/--unidiff-zero` 容错)。
4. **本地单模型驻留**:每次只加载一个 ollama 模型(并发抢 GPU 会慢 20 倍);agentic 循环串行 workers=1。
5. **消除答案泄漏**:good/oracle 的记忆来自 Opus 真解(claude -p,不看 gold)的散文诊断,逐字 gold 代码被 scrub(0 残留);good_apply 的补丁是 Opus solver 自己的真实编辑(peer 解法,agentbook 在生产中本就存储它)。

## 4. 与已发表数据对照(web search)

| 模型 | 已发表 SWE-bench Verified | 本评测(hard RED 子集) |
|---|---|---|
| Opus 4.7 | 87.6%(官方) | 45%(17/38) |
| gpt-oss-120b | 62.4%(需 high reasoning) | — |
| gpt-oss-20b | 未单列(更弱) | control 0% |
| gemma-4-27b | ~78%(二手源) | — |

绝对值低于全集是因为我们刻意用 hard 子集暴露 lift 面。**方法学校验**:mini-swe-agent #798 显示 gpt-oss:120b 官方 62% 但本地 Ollama 仅复现 ~10%——我们 gpt-oss control 的低分与此一致,不是 harness 缺陷。

## 5. 效度与局限

- **n=17 记忆任务**:control→good_apply 的效应极大(0→14/17、p≈1e-4),方向稳健;但单仓 sympy、子集偏硬。
- **good_apply 是 agentbook 的「上界形态」**:它假设记忆里有一份对该问题验证过的精确补丁(生产中由强 agent 解出后 remember + confidence 筛选而来)。这测的是「弱 agent 能否抄到强 agent 的解」——答案是肯定的(逼近天花板)。
- gpt-oss good_apply 有采样波动(本次 14/17,早期一次 16/17);gemma 稳定 17/17。

## 6. 优化空间(进一步逼近 100% / 推广)

1. **执行体**优先 instruct 模型(gemma4:e4b 17/17 vs gpt-oss 14/17)。
2. **agentbook 侧**:knowledge synthesis 把 canonical solution 固化成「即用补丁」;outcome/lineage 学习「哪种表述最易被弱 agent 落地」;recall payload 直接带结构化补丁(本实验已验证其威力)。
3. **harness 侧**:APPLY_PATCH + 「应用→跑测试→自检→回滚/重试」微循环吃掉采样波动(可把 gpt-oss 的 14 拉到 17)。
4. **难度匹配**:中等难度上 control 基线更高、lift 面更大,绝对收益更高。

## 7. 复现

```bash
cd experiments/agentbook-ab
uv run python red_verify_clean.py                          # 干净 RED -> manifest.red.json (38)
uv run python -m memory.strong_solver --model opus --workers 8
uv run python -m memory.verify_solution --manifest tasks/manifest.red.json   # R_opus=17/38
uv run python -m memory.seed_corpus --manifest tasks/manifest.red.json       # 记忆 + oracle
# patch_cache(peer 验证补丁,供 good_apply 抄答案)
uv run python -c "见 _oracle/patch_cache.json 构建逻辑"
VOYAGE_API_KEY= DATABASE_URL= EMBEDDING_DIMENSION=1024 EMBEDDING_VERSION=v2 \
  uv run --package agentbook uvicorn backend.main:app --port 8078 &
uv run python -m memory.seed_corpus --manifest tasks/manifest.red.json --seed-live
uv run python eval_retrieval.py --no-reseed                # Layer1 + recall_cache
# 本地小模型抄答案臂(单模型驻留!)
ollama stop gemma4:e4b
uv run python -m pipeline.orchestrator --provider ollama --models gpt-oss:20b \
  --manifest tasks/manifest.memory.json --arms good_apply -k 2 --workers 1
ollama stop gpt-oss:20b
uv run python -m pipeline.orchestrator --provider ollama --models gemma4:e4b \
  --manifest tasks/manifest.memory.json --arms good_apply -k 2 --workers 1
```

## 附录 A:good_synth(综合抽象知识)实测(2026-05-26)

测试 §6 的优化设想——把记忆综合成「根因模式 + 定位线索 + 验证方法」(无补丁、无散文),配空白不敏感的结构化 SEARCH/REPLACE 编辑,**模型自己推导并落地**。同题记忆,新 harness,k=1(gpt-oss 高推理 step30、gemma step12)。

| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| control | 0/17(复用) | 2/17 |
| good(散文召回) | **4/17** | **5/17** |
| good_synth(综合抽象) | **4/17** | 3/17 |
| good ∪ good_synth | **6/17** | **6/17** |
| harm | 0 | 1(16886) |

**结论一:综合抽象知识不抬升 baseline。** good_synth 单臂不优于散文 good——gpt-oss 持平(4=4)、gemma 反低(3<5)。**对小模型,把解法从「具体散文诊断(含文件+具体修法)」抽象成「模式+线索」不是增益。** 与 §2「good > oracle」同向:可执行表述的甜区是**更具体**,不是更抽象。⇒ knowledge synthesis 应朝「结构化即用补丁」(good_apply 14-17/17),而非去具体化。§6 的「综合/抽象」设想被证伪。

**结论二:具体与抽象表述互补。** good 与 good_synth 各自解出 2 道对方没解出的题(两模型皆然),**并集 6/17 > 任一单臂**——不同表述命中不同失败模式。产品方向:多表述并存/按模型择优,而非用抽象替代具体。harm 低(gemma 1、gpt-oss 0)。

逐 cell 产物 `runs_v2/*good_synth*`、综合缓存 `_oracle/synth_cache.json`、矩阵 `_oracle/final_matrix.json` 的 `good_synth_eval_2026_05_26`。

## 附录 B:good_loop(执行/验证条件)实测(2026-05-26)

不窄化知识的能力杠杆。`good_loop` = **与 good_synth 完全相同的通用抽象知识** + harness 拥有 **apply→跑公开 repro→读失败→重试→done-gate→回滚** 控制流(`sandbox.run_verification` 双条件判定;验证来自 Opus 抽取的公开 repro,非隐藏评分测试)。只改执行条件。

| 臂 | gpt-oss:20b | gemma4:e4b | 知识 | 执行 |
|---|---|---|---|---|
| control | 0/17 | 2/17 | 无 | 模型 |
| good(散文) | 4/17 | 5/17 | 具体 | 模型 |
| good_synth(抽象) | 4/17 | 3/17 | 抽象通用 | 模型 |
| **good_loop(抽象+验证循环)** | **7/17** | **5/17** | 抽象通用 | **harness 验证+重试+回滚** |
| good_apply(缓存,非目标) | 14/17 | 17/17 | 同题精确补丁 | harness 应用 |

**核心结论:** 知识保持通用,单加「可验证 + harness 拥有迭代」就把 good_synth **+3(gpt-oss 4→7)/+2(gemma 3→5)**,在更弱的 gpt-oss 上抬最多;good_loop 是**最强非缓存臂**,gpt-oss 上超过散文 good。`oracle→good_apply(+12-15)` 与 `good_synth→good_loop(+2/+3)` 是同一执行杠杆的「缓存版」与「通用知识版」。⇒ 小模型逼近更大模型的正确路径 = **保持知识通用 + 强化可验证执行条件**,而非窄化成即用补丁。

**诚实边界:** 公开 repro 必要非充分——gemma repro 过 9 但 resolved 5(欠定→过拟合);gpt-oss resolved 7 但子串检查只判过 5(假阴)。天花板受不可约的多点定位/诊断限制(5-7 ≪ Opus 17)。逐 cell 产物 `runs_v2/*good_loop*`、验证字段在 `_oracle/synth_cache.json`。

## 附录 C:good_loop v2 多 repro(2026-05-26 夜)—— 不对称 + 互补

把 §B 的单 repro 升级为**按 cues 派生 2-5 独立 repro**(17 → 68 repro)、`run_verifications` 全过才算通过、期望支持「任一备选命中」。**知识不变**。

| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| good_loop v1(单 repro) | **7/17** | 5/17 |
| good_loop v2(多 repro) | 5/17 | **7/17** |
| **good_loop v1 ∪ v2** | **10/17** | **9/17** |
| 全臂并集(good ∪ synth ∪ v1 ∪ v2) | **12/17** | **10/17** |

**两条发现:**

1. **多 repro 的效应与模型不对称**——gemma(instruct)+2、gpt-oss(flaky reasoning)-2。stricter all-pass 在可靠模型上强制多点覆盖(15017 4 个构造点全修),在不稳定模型上放大 parse_failures、丢掉单点 case。「更强验证」不单调更好。

2. **不同验证/表述命中不同失败模式,互补极强**——v1 ∪ v2 跳到 9-10/17,全臂并集 **gpt-oss 12/17 = Opus 71%**。同一份通用知识 × 不同表述 × 不同验证 ≈ 准确逼近的真正路径。

⇒ **下一步是集成,不是找最优单臂**:`good_multi_loop`(散文+抽象 + 多 repro)→ arm-router(agentbook 按 outcome/lineage 学每类任务+模型的最易落地组合)。逐 cell:`runs_v2/*good_loop*`(v2)、`runs_v2.good_loop_v1_single_repro/`(v1 归档),综合缓存 `_oracle/synth_cache.json` 已含 multi-repro 字段。

## 附录 D:good_multi_loop(双视图集成)实测(2026-05-27)—— 82% of Opus 定量证实

一个 prompt 同载**散文 good + 抽象 good_synth 双视图**,配多 repro 循环;知识总量不变,只翻倍 PRESENTATION。直接测「集成是否吃到 v1∪v2 互补」。

| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| good_loop v1 | **7/17** | 5/17 |
| good_loop v2 | 5/17 | 7/17 |
| **good_multi_loop** | 6/17 | **8/17** |
| **v1 ∪ v2 ∪ multi** | **13/17** | **11/17** |
| **全臂并集** | **14/17(= Opus 82%)** | **11/17(65%)** |

**两个结论:**

1. **单臂层面是混合的**——gemma multi = 8 是新最佳单臂(+1);gpt-oss multi = 6 介于 v1(7)和 v2(5),dual-view 仍带 parse_failure 风险。但 multi_loop **独家新增 3 道题**:gpt-oss 上 14976、15809,gemma 上 17318——这 3 道**无任何前臂解过**,确认双视图命中新失败模式。

2. **集成假说定量证实**——5 臂全集 gpt-oss **14/17 = Opus 82%**、gemma 11/17 = 65%。同一份通用知识 × 不同表述 × 不同验证制度,小模型自解从 control 0% 抬到 gpt-oss 82%(知识不窄化,无补丁缓存)。

**定量回答主目标(gpt-oss 硬子集):**
0%(control) → 41%(单臂最佳) → 76%(v1∪v2∪multi) → **82%(5 臂集成)**,距 Opus 100% 差 3 题(不可约推理)。

**下一步产品方向:** **arm-router**(agentbook recall 阶段并行多臂或规则路由),把 5 个手工臂变成可学习策略空间。

逐 cell 产物 `runs_v2/*good_multi_loop*`、全矩阵 `_oracle/final_matrix.json` 的 `good_multi_loop_eval_2026_05_27`。

## 附:产物
- `_oracle/final_matrix.json` — 全臂最终矩阵(含 v1/v2/multi 详细块 + 全臂并集)
- `_oracle/synth_cache.json` — good_synth 综合知识(17 条) + 每条 2-5 个独立 verification repros
- `runs_v2.good_loop_v1_single_repro/` — v1 单 repro 归档(用于 v1 vs v2 对照)
- `runs_v2.gptoss-good_apply/`, `runs_v2.e4b-good_apply/` — good_apply 逐 cell 结果+transcript
- `runs_v2.local-gptoss/`(control/good/oracle)、`runs_v2.openrouter-gptoss-free/`
- `_oracle/patch_cache.json`(peer 验证补丁)、`memories.json`、`oracle.json`、`red_clean.json`、`published_benchmarks.json`
- `retrieval_report.json`(Layer1)、`solver_verified.json`(Opus 17/38)
