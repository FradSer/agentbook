# GOAL: 让小模型靠 agentbook 检索到的知识解决问题，逼近 Opus 4.7

> 本文件记录目标的精确定义、已验证的发现、以及通往目标的可执行路线。
> 详细评测在 `experiments/agentbook-ab/`（`REPORT.md` 主结果、`REFLECTION.md` 三方反思+LOO 实测）。
> 日期：2026-05-25。

## 1. agentbook 的价值链（目标场景）

```
AI 遇到问题 → 总结成知识 → autoresearcher agent 研究/爬坡/综合
            → 沉淀为高置信知识（canonical solution + 步骤 + lineage + confidence）
            → 小模型用 embedding/rerank 检索
            → 用这份知识「解决」问题
```

核心是**知识转移**。

## 2. 目标的精确定义（已澄清）

**小模型通过检索到的知识，自己解决问题** —— 而**不是**把记忆里的一份精确补丁原样 apply（那是「抄答案/缓存」，不是「解题」）。

- ✅ 目标 = 评测里的 `good` 臂：检索到知识（诊断+步骤），**模型自己推导并落地编辑**。
- ❌ 非目标 = `good_apply` 臂：记忆里直接带 Opus 对同题的验证补丁，模型只发一个 `APPLY_PATCH`，harness 落地。这是诊断用的**上界探针**，证明「瓶颈在执行而非知识」，不代表能力。

## 3. 已验证的发现（本地 Ollama gpt-oss:20b / gemma4:e4b，单模型驻留；Opus 4.7 via claude -p；防篡改打分，resolved-d0=0）

基底：17 个 Opus 解出的硬 sympy bug（38 个 RED 校验任务里 Opus=45% 的子集）。

### 3.1 五臂主结果（17 任务，pass@k）
| 臂 | gpt-oss:20b | gemma4:e4b | Opus | 含义 |
|---|---|---|---|---|
| control（无知识） | 0/17 | 1/17 | — | 小模型裸能力 |
| **good（检索同题知识，模型自己解）← 目标** | **4/17** | **6/17** | — | 靠知识解题：真实但弱 |
| oracle（直接给 gold diff，模型自己 bash 应用） | 2/17 | 2/17 | — | 给答案也落不了地 |
| good_apply（精确补丁 + harness 应用）= 抄答案 | 14/17 | 17/17 | — | 上界探针，非目标 |
| Opus 4.7（天花板） | — | — | 17/17 | — |

### 3.2 leave-one-out 真迁移（去掉同题记忆，只给同模块兄弟知识，9 个可测任务）
| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| control | 0/9 | 1/9 |
| **loo_sibling（相关知识，模型自己解）** | **0/9** | **2/9** |
| loo_sibling_apply（给兄弟补丁套用） | 0/9 | 1/9（harm=0） |
| good_apply（同题精确，参照） | 6/9 | 9/9 |

### 3.3 检索现状
当前 agentbook 检索**只顶得出近重复的同题记忆**（查任一题只返回自己 1 条 sim=1.0，其余记忆全在 0.25 相关性阈值下）。→ **新题上真实检索 = no_good_match = 退化成 control，零增益**。Layer-1 recall@1=1.0 只因 query 与记忆同源 BUG.md 文本。

## 4. 诚实结论

`完成率 ≈ 检索质量 × 知识的可执行表述 × 模型的执行/推理力`

1. **「靠知识解题」是真实的但当前很弱**：同题精确知识下 4-6/17；相关知识下 ≈0。
2. **两层瓶颈**（都不是「不知道」）：
   - **执行鸿沟**：给了正确诊断（甚至 gold），小模型也常把编辑做崩（oracle 2/17 < good 4/17 是铁证）。
   - **迁移推理鸿沟**：知识不精确时，模型还得自己定位+诊断+适配，这是小模型最缺的。
3. **good_apply 的 parity 是「抄同题答案」**，非能力；真正的跨问题迁移对小模型几乎不成立（gpt-oss 0、gemma 仅 +1/9）。
4. **安全**：盲目套用相关补丁 harm=0（git apply 失败即安全失败）。

## 5. 通往目标的路线（都不等于「抄补丁」）

1. **提升知识质量（autoresearcher 本职、agentbook 真价值）**：把原始解综合成**面向弱模型可执行的知识**——抽象修复模式 + 定位线索 + 验证方法；按 outcome/lineage 学「哪种表述弱模型最易落地」。证据：`good(4-6) > oracle(2)`，表述质量本身能提分。
2. **harness 作为执行脚手架（非替模型抄补丁）**：模型**根据知识自己决定编辑**、用结构化 SEARCH/REPLACE 表达，harness 负责可靠落地 + 跑测试 + 失败重试。把 `good` 从「执行地板」抬向「推理上限」——模型仍在解，只是手稳了。
3. **改进检索**：降相关性阈值 + 模块感知 + 多记忆 RRF/rerank，让新题能顶出兄弟知识；confidence/abstain 门控 + 失败记忆（相关但错的记忆会伤害弱模型，harm 必须一等指标）。
4. **诚实的天花板**：新题仍需模型自身的定位+诊断推理，记忆层补不了；可达「显著优于无知识基线、随知识库质量增长」，而非新题上与 Opus parity（gemma 比 gpt-oss 多迁移一题，方向上印证「模型越强迁移越多」）。

## 6. 下一步（对齐目标的实验）

新增 **`good_synth` 臂**：记忆 = autoresearcher 风格的**综合/抽象知识**（根因模式 + 定位线索 + 验证方法，**非补丁、非裸散文**），配**结构化编辑 + apply→测试→重试 harness**，**模型自己合成并落地编辑**。在同题/同模块/纯新题三档上测，把 `good` 的 4-6/17 能抬到多少——这是「小模型靠知识解题」能力曲线的真实测量。

### 6.1 实现状态（2026-05-25，已建，暂未评测）
- **知识缓存**：`memory/synthesize.py` 用 `claude -p`(Opus) 把 17 条 leak-free prose 记忆综合为结构化知识 → `_oracle/synth_cache.json`（每条 = `root_cause_pattern` + `localization_cues` + `verification_method`，**无补丁、无散文**；对 gold 二次擦洗，19637 命中 2 行已中和，其余 0 泄漏）。
- **臂**：`pipeline/arm_context.py` 新增 `good_synth` 分支（读 synth_cache，注入「根因模式/定位线索/验证方法」块，无补丁）；`pipeline/orchestrator.py` 按 synth_cache 键门控该臂。
- **执行脚手架**：harness 新增**空白不敏感的结构化 SEARCH/REPLACE 编辑**（` ```edit ` 块，`harness/sandbox.py:apply_search_replace` + `harness/prompts.py:extract_edits`，对全臂生效，比 git-apply diff 对弱模型更稳）；保留 ` ```diff ` 与 apply→观察→重试循环。单测 `harness/tests/test_search_replace.py`（7 项）全绿。
- **复现**：`uv run python -m pipeline.orchestrator --arms control good good_synth --models <gpt-oss:20b|gemma4:e4b> --provider ollama -k <n>`，再 `stats.aggregate`。

### 6.2 评测结果（2026-05-26，新 harness，同题记忆，k=1，已跑完）

| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| control（无知识） | 0/17（复用天花板） | 2/17 |
| good（散文召回） | **4/17** | **5/17** |
| good_synth（综合抽象知识） | **4/17** | 3/17 |
| **good ∪ good_synth（并集）** | **6/17** | **6/17** |
| harm（good_synth 改坏 control 能过的） | 0 | 1（16886） |

（gpt-oss 高推理 step30；gemma step12。gpt-oss 高推理下单 cell 常跑满 8000 token，个别 10-19 分钟。）

**两条结论：**
1. **综合抽象知识不抬升 baseline**：good_synth 单臂**不优于**散文 good——gpt-oss 持平（4=4），gemma 反而更低（3<5）。把解法从「具体散文诊断（含文件 + 具体修法）」抽象成「模式 + 线索」对小模型不是增益。印证 §4-5：弱模型缺的是「从抽象模式推导出具体编辑」的不可约推理；可执行表述的甜区是**具体**，不是抽象。§6 的「综合/抽象」设想被证伪。
2. **但具体与抽象互补**：good 和 good_synth **各自解出 2 道对方没解出的题**（两模型皆然），**并集 6/17 > 任一单臂**（gpt-oss 4→6、gemma 5→6）——两种表述命中不同失败模式。⇒ 正确产品方向不是「用抽象替代具体」，而是**多表述并存/按模型择优**，且把 synthesis 推向 §5.5「结构化即用补丁」（good_apply 已证 14-17/17），而非去具体化。

### 6.3 good_loop：执行/验证条件（2026-05-26，已跑完）—— 真正的能力杠杆

不窄化知识：`good_loop` = **与 good_synth 完全相同的通用抽象知识**，但 harness **拥有 apply→跑公开 repro 验证→读失败→重试→done-gate→回滚** 的控制流（`harness/agent_loop.py` + `sandbox.run_verification/git_checkpoint/git_reset_to`；验证用 `synth_cache` 里 Opus 抽取的 `verification_command/expected/buggy`，**公开 repro 非隐藏评分测试**）。只改「执行条件」，知识不变。

| 臂 | gpt-oss:20b | gemma4:e4b | 知识 | 执行 |
|---|---|---|---|---|
| control | 0/17 | 2/17 | 无 | 模型 |
| good（散文） | 4/17 | 5/17 | 具体 | 模型 |
| good_synth（抽象） | 4/17 | 3/17 | 抽象通用 | 模型 |
| **good_loop（抽象 + 验证循环）** | **7/17** | **5/17** | 抽象通用 | **harness 验证+重试+回滚** |
| good_apply（缓存，非目标） | 14/17 | 17/17 | 同题精确补丁 | harness 应用 |
| Opus 4.7（天花板） | 17/17 | 17/17 | — | — |

**核心结论（正面，回答用户目标）：知识保持通用（不窄化），单靠加「可验证 + harness 拥有迭代」的执行条件，把 good_synth 抬升 +3（gpt-oss 4→7）/ +2（gemma 3→5），且在**更弱的 gpt-oss 上抬得最多**。good_loop 7/17 是**最强的非缓存臂**，在 gpt-oss 上**超过散文 good（4）**。这证明 §1-2 的判断：小模型逼近大模型的杠杆是**执行/迭代的条件**，不是把知识变窄成查表。`oracle→good_apply` 的 +12-15 是「同题缓存」版本，`good_synth→good_loop` 的 +2/+3 是「通用知识」版本——同一杠杆。

**诚实边界（repro vs 隐藏评分 双向 gap）：** gemma 公开 repro 过了 9 题但只 resolved 5（repro 欠定 → 过拟合，典型如 15017 需改 4 个构造点、repro 只测 1 个）；gpt-oss resolved 7 但我的子串检查只判过 5（2 题实修对了、检查假阴）。即**公开 repro 是必要非充分的驱动信号**，净正但不完美。天花板仍受不可约的「多点定位+诊断」推理限制（good_loop 5-7 ≪ Opus 17）。

**成功判据达成度：** 「小模型在(综合)知识 + 执行脚手架下，自解成功率**显著高于无知识基线**（gpt-oss 0→7、gemma 2→5），并随**执行条件质量**增长」——达成；「新题逼近 Opus」——未达成（也非修正后的判据）。

### 6.4 good_loop v2：多 repro（2026-05-26 夜）—— 不对称 + 互补

把 §6.3 的单 repro 升级为**每条记忆按 localization_cues 派生 2-5 个独立 repro**（`memory/extract_verification.py` Opus 二轮抽取，17 条 → 68 个 repro），harness 改为 `run_verifications`（**所有 repro 都过才算通过**）+ 期望支持「任一备选子串命中」（修 v1 的子串假阴）。知识依旧通用，不窄化。

| 臂 | gpt-oss:20b | gemma4:e4b |
|---|---|---|
| control | 0/17 | 2/17 |
| good（散文） | 4/17 | 5/17 |
| good_synth（抽象） | 4/17 | 3/17 |
| good_loop v1（单 repro） | **7/17** | 5/17 |
| good_loop v2（多 repro） | 5/17 | **7/17** |
| **good_loop v1 ∪ v2** | **10/17** | **9/17** |
| **全臂并集（good ∪ synth ∪ v1 ∪ v2）** | **12/17** | **10/17** |
| Opus 4.7（天花板） | 17/17 | 17/17 |

**核心发现一：多 repro 的效应**与模型**不对称**——
- gemma（instruct，可靠）：5 → **7**（+2），多 repro 强制覆盖全部位点（如 15017 4 个构造点全修），上抬明显。
- gpt-oss（reasoning，flaky）：7 → 5（−2），stricter all-pass 门槛把它原本就常见的 parse_failures 放大，单点能解的题反而被严苛 verify 拖出预算（丢了 16792/17318/18189/18211/19954 五个 v1 win）。
- ⇒ **「更强验证」不是单调更好**——它惩罚不稳定模型的额外迭代成本。

**核心发现二（更重要、产品决定级）：不同验证/表述命中不同失败模式，互补极强。**
- v1 ∪ v2：**gpt-oss 10/17**（v1 only 5、v2 only 3、both 2）、**gemma 9/17**（v1 only 2、v2 only 4、both 3）——两个验证制度合起来比任一单臂多 3-4 道。
- 加上 good 散文与 good_synth 抽象的并集：**gpt-oss 12/17（=Opus 17/17 的 71%）、gemma 10/17（59%）**——**仍是同一份通用知识**，只是用了不同表述 + 不同验证。

**修正后的下一步（取代 §6.3 末尾的「强化单一验证」）：**
不再追求「找到最优的单臂」，而是**集成多臂 / 路由**：
1. **`good_multi_loop`**：一个 prompt 里同时拿散文 good 和抽象 good_synth 两份知识，配多 repro 循环，跑一次拿到接近并集的成绩；
2. **arm-router**（产品形态）：agentbook 在 recall 时按 outcome/lineage 学到的「这类任务+这类模型最易落地的表述」，**动态选择**单 repro / 多 repro / 散文 / 抽象 / 混合，把假阴和过严问题做成可学习的策略。

**诚实边界：** 即便全臂并集 12/17，仍距 Opus 17/17 有 5 题 gap——属于 §3 R4「真正全新」的不可约推理；这部分无法靠表述/验证补，要么换更强的小模型，要么接受这是天花板。

**harm 低**（gemma 1、gpt-oss 0），抽象知识没有系统性伤害弱模型。

## 成功判据（修正后）
不是「新题上与 Opus parity」，而是：
**小模型在检索到的(经综合的)知识 + 执行脚手架帮助下，自己解题的成功率显著高于无知识基线，并随知识库质量与覆盖度持续增长；在复发/同题问题上接近 Opus。**
