# agentbook 反思:小模型能否在外部知识+harness 下逼近 Opus 4.7

综合三个独立反思 agent(效度红队 / 跨问题泛化架构 / 分工与 harness 协同)+ 已验证评测结果。日期 2026-05-25。

## 1. 当前结果的诚实定性

`good_apply`(gemma4:e4b 17/17、gpt-oss:20b 14/17,追平 Opus 17/17)是 **"答案缓存+中继"** 结果,**不是小模型能力提升**。红队从产物逐 cell 验证:gpt-oss good_apply 里 `resolved` 与"模型是否吐出 `APPLY_PATCH` 这一个 token"**完全等价**——模型对每个 win 的全部贡献就是一个触发词,harness 再 git-apply 的是 **Opus 对同一道题的验证补丁**(prompt 里就放着)。检索 recall@1=1.0 也只因 query 与记忆是同一段 BUG.md 文本(近重复),非真实检索。

- **可辩护的主张**:当 agentbook 已含某问题的**验证可用补丁**,小模型+应用型 harness 能近天花板地把它投递落地;瓶颈是协议遵守,不是知识。这是**缓存/dispatch 系统**的结论。
- **要避免的夸大**:"小模型在硬 SWE-bench 上达到 Opus 能力"——假;模型没解任何题,它中继了被放进 prompt 的 Opus 同题验证补丁。

## 2. 经得起批判的两个真发现

1. **执行(不是知识)是小模型主瓶颈**。铁证:**oracle(2/17)< good(4-6/17)**——把 gold 直接给它让它自己 bash 应用,反而比给散文诊断更差(transcript:它拿着正确 diff 反复写崩 heredoc)。"上下文里有答案" ≠ "修复落地"。
2. **把"应用"搬进 harness 能可靠投递已知修复**。oracle→good_apply 在同等知识下 +12/+15,差别只在"谁来应用"。

打分本身可信(防篡改、editable-finder 剥离、resolved-d0=0)。是**实验框架**(同题记忆、平凡检索、Opus 派生记忆、n=17 单仓、按"Opus 赢且 control 输"挑任务)在过度声称。

## 3. 通往"真正逼近 Opus"的难度阶梯

关键设计杠杆:**把 query 任务与记忆任务解耦**。

| 阶梯 | 记忆含什么 | 模型必须贡献什么 | 预期可达 Opus 的比例 |
|---|---|---|---|
| **R1 exact-match**(=good_apply,已做) | 同题验证补丁 | 一个 APPLY_PATCH | **parity(已证)** |
| **R2 同族**(同文件/同根因类,如 pycode×3、mod×2) | 兄弟 bug 的补丁+诊断 | 轻量适配(改符号/移行) | synthesis+retry 下 **70–90%** |
| **R3 同模块类比** | 同模块**不同** bug,只有策略可迁移 | 自己定位故障 + 在新位点实例化修复 | **~50%**,卡在**故障定位**(不可卸载) |
| **R4 全新题+仅相关记忆** | 多条不同问题的记忆,需综合 | 多信号合成 + 判别该用哪条/拒绝干扰 | **仅小幅超 control**,远不及 parity(Voyager 0/3→1-2/3 量级) |

## 4. 能力分工(谁该负责什么)

| 能力 | 归属 | 依据 |
|---|---|---|
| 应用编辑 / 跑测试 / 回滚 / 判完成 / 重试控制流 | **harness(确定性,不可放模型)** | oracle→good_apply +12~15;`submit=True/resolved=False` 是模型谎报完成;有 transcript 把整个源文件 heredoc 覆盖掉 |
| 故障定位 | agentbook(有精确/相关记忆时)→ 模型(全新时回退) | recall 命中即给文件+符号;相关记忆缩小搜索域 |
| 根因诊断 + 编辑合成 | agentbook(精确时)→ **模型(全新时不可约)** | good>oracle:Opus 散文诊断比 gold diff 更易消化;但全新题这步是模型推理,无法卸载 |

**差距分解(硬子集,gpt-oss):** 执行/协议差距(control 0→good_apply 14,≈+14)**可被 harness 完全闭合**;全新题上知识+harness 可再闭合 **~25–40%**(把 good 从执行地板抬向其推理上限),**剩 ~60–75% 是模型不可约的诊断/合成推理**,任何记忆层都消不掉。

## 5. 可执行路线(按性价比排序)

**Harness 硬化(便宜、可证伪,先做):**
1. **把"手动 git apply"拦截为隐式 APPLY_PATCH**,并从 apply 臂 prompt 里去掉逐字补丁(展示 diff 反而诱导手动应用)。假设:gpt-oss good_apply 14→16-17、submit 0.71→≥0.9(直接救回 17139/17318/19954 三个手动应用失败 cell)。
2. **done-gate(跑可见测试才算完成)+ 引入新失败则自动回滚**。把"自信却改坏"类失败(如 17318 覆盖整文件)转为可恢复循环。
3. **apply→跑测试→读失败→重试 微循环**(harness 拥有控制流)。吃掉 gpt-oss 14↔16 的采样波动。
4. **模糊结构化编辑工具(EDIT/SEARCH/REPLACE,空白不敏感)** 替代手写 sed/heredoc,用于 good/control 臂。假设:good 臂 gpt-oss 4→7-9、gemma 6→9-11(量出 good 差距里"执行" vs "推理"各占多少)。

**agentbook 侧:**
5. **knowledge synthesis 把记忆固化成结构化即用补丁**(非散文),用 outcome/lineage 学"弱 agent 最易落地的表述";加 `good_structured` 臂(结构化但**非同题**)隔离"表述质量"单独的增益。
6. **confidence/abstain 门控 + 失败记忆**:`no_good_match`/低置信时抑制记忆回退到 control —— SWE-Bench-CL 证实"相关但错的记忆会主动伤害弱模型",**harm 必须是一等指标**。

**关键实验(同基底,本地 gpt-oss:20b/gemma4:e4b + claude -p Opus):**
- **实验1 leave-one-out(头号迁移测试)**:对每个held-out任务,只 seed 其余 N-1 任务的记忆、**去掉同题记忆**;真实 `eval_retrieval.py` 量出 recall@1(将远低于 1.0)。臂:control / loo_recall / loo_recall_apply / loo_synth / Opus。所有臂加 **harm 计数器**(control 能过但加记忆后改坏)。
- **实验2 同族分层 + synthesis 消融**:同模块簇内用兄弟记忆;`sibling_abstract`(剥离行号的模式)vs `sibling_concrete`(逐字补丁)——证明综合/抽象在位点不同时优于裸补丁召回。
- **实验3 检索精度+abstain k 扫描**;**实验4 跨仓负控**(只 seed sympy 记忆查 sklearn,验证"无关记忆时安全失败,harm≈0")。

## 6. 给用户目标的诚实结论

"小模型 + 外部知识 + harness 逼近 Opus 4.7":
- **复发/同题问题:已达 parity**(R1,把执行搬进 harness + agentbook 存验证补丁)——这是 agentbook 价值最大化的场景,产品应**主动扩大 exact-match 覆盖**(把解综合成即用补丁)。
- **同族/同模块问题:可"逼近"(70-90% / ~50%)**,这是值得下一步攻的"接近顶尖模型"的现实胜利——靠 synthesis + harness 重试 + 模糊应用。
- **真正全新题:只能小幅超自身 baseline,远不及 parity** —— 因为根因诊断+编辑合成是模型不可约的推理。

**正确的成功判据不是"全新题上 parity",而是"正向、无伤害的迁移,且随记忆库的模式重叠度而增长" + "在复发问题上匹配 Opus"。** 实验1/2 是最便宜的把它量化的方式。

## 参考(各 agent web search)
Voyager(技能库迁移 0/3→1-2/3)、DS-Agent(CBR 开发/部署分离)、SWE-Bench-CL & SWE-ContextBench(跨 issue 迁移,naive 检索会伤害)、ReMe/Memp(强模型程序性记忆蒸馏给小模型)、RAG-Fusion/RRF 重排、aider 统一 diff & Diff-XYZ(search/replace 对弱模型更可靠)、SWE-agent ACI(无效编辑丢弃重试 +3pp)、Agentless(测试投票选 patch)。
