# Autoresearch Feature Analysis

Comprehensive extraction of all core features, mechanisms, and design patterns from Karpathy's autoresearch repository.

**Analysis Date**: 2026-03-18
**Purpose**: Completeness check against agentbook implementation

---

## 1. Core Loop Mechanics

### 1.1 Research Loop Structure
- **Infinite hill-climbing loop**: modify → run → measure → keep/revert → repeat
- **Step-by-step workflow**:
  1. Read directives from `program.md` (human-written research direction)
  2. Modify `train.py` (the only mutable file)
  3. Execute training for exactly 5 minutes (300 seconds)
  4. Evaluate results against validation metric (val_bpb)
  5. Decide: keep or revert changes based on metric improvement
  6. Plan next experiment and repeat
- **Throughput**: ~12 experiments per hour, ~100 overnight, ~700 in 2 days
- **Autonomous operation**: No human intervention required during execution

### 1.2 Baseline Measurement
- Agent establishes baseline by creating new git branch
- Runs unmodified training script to record initial metric
- All subsequent experiments compare against this baseline

### 1.3 Continuous Execution
- "Never stop" philosophy: agent explores relentlessly without waiting for permission
- Loops immediately after processing until interrupted
- Designed for unattended overnight runs

---

## 2. Decision Mechanisms

### 2.1 Keep-or-Discard Logic
- **Binary decision**: if val_bpb improved → keep changes; if not improved → revert changes
- **Automatic rollback**: failed experiments revert within the 5-minute window
- **No subjective judgment**: purely metric-driven decisions
- **Strict improvement**: only successful modifications persist into next iteration

### 2.2 Hill-Climbing Semantics
- **Greedy hill-climbing**: each experiment either improves metric (retained) or fails (discarded)
- **No exploration of non-improving directions**: only successful modifications persist
- **Additive improvements**: changes stack on top of each other
- **Validation before stacking**: improvements validated via lower validation loss before combining

### 2.3 Transfer Validation
- Changes tested on smaller models (depth-12) transfer to larger models (depth-24)
- Demonstrates generalization across scales
- All 20 improvements "stacked together" successfully

---

## 3. Quality Controls

### 3.1 Simplicity Criterion
- **Fixed 5-minute wall-clock budget** per experiment
- Prevents agent from gaming metrics through extended runs
- Keeps search space tractable
- Forces discovery of configurations that train efficiently within constraints
- Platform-independent comparisons (same time budget regardless of hardware)

### 3.2 Crash Handling
- **Failure handling** enables systems to run for days without supervision
- **Keep-or-reset mechanism** turns chaotic exploration into clean evolutionary search
- Auto-revert mechanism serves as primary failure recovery
- System designed for robustness through evaluation isolation

### 3.3 Validation Rules
- **Evaluation harness locked**: prevents agent from gaming its own benchmark
- **Immutable eval set**: held-out validation set completely isolated from agent access
- Agent cannot train on it, touch it, or observe it during the loop
- **Constraints set in program.md**: humans define guardrails (parameter counts, tokenizer properties)
- Agent operates within these boundaries while iterating

### 3.4 Scope Constraints
- **Single-file modification**: agent only edits `train.py`
- Prevents scope creep and keeps diffs reviewable
- Limits debugging complexity
- 630-line codebase fits within LLM context windows
- Enables agent to "understand" entire system

---

## 4. Experiment Tracking

### 4.1 Git-Based Lab Notebook
- **Git log functions as lab notebook**: each commit = completed experiment with val_bpb score
- **Experiments run on git feature branches**: separate branch per experiment series
- **Each completed run committed**: creates perfect audit trail
- **Agent reviews branch history**: informs subsequent optimization attempts
- **Learning feedback loop**: git history enables agent to learn from past experiments

### 4.2 Metrics Tracked
- **Primary metric**: validation bits per byte (val_bpb)
  - Lower values = better performance
  - Vocabulary-size independent
  - Allows consistent comparison even when changing tokenizer or architecture
  - Enables fair architectural comparisons
- **Single optimization target**: agent "optimizes relentlessly" against this one metric

### 4.3 Experiment Logging
- **TSV logging**: requires zero infrastructure
- **Logged data**: prompts, model version, retrieval results, run IDs
- **Reproducibility**: all experiment parameters captured
- **Results format**: experiment ID, metric value, timestamp, commit hash

### 4.4 Performance Results
- **Karpathy's run**: ~700 experiments, 20 improvements found
  - Training time reduced from 2.02 to 1.80 hours (11% improvement)
  - Time to GPT-2 benchmark improved
- **Shopify (Tobi Lütke)**: 37 experiments overnight, 19% performance gain
  - 0.8B model outperformed 1.6B baseline

---

## 5. Human Guidance

### 5.1 Program.md Interface
- **Human-agent interface**: markdown file serves as communication channel
- **Research objectives**: humans define high-level goals without modifying code
- **Constraint specifications**: parameter bounds, tokenizer properties, architectural limits
- **Agent instructions**: defines optimization rules and experimental parameters
- **"Research org code"**: meta-instructions that guide autonomous discovery
- **Programmable research**: treats research as programmable through markdown instructions

### 5.2 Example Objectives
- **Primary goal**: "Achieve the lowest possible validation bits per byte (val_bpb) in fixed 5-minute training runs"
- **Constraint examples**:
  - Maintain parameter count within specified bounds
  - Preserve tokenizer properties
  - Hardware accessibility (single-GPU setup)
  - Time boundaries (fixed 5-minute windows)

### 5.3 Agent-Interpretable Parameters
Agents can modify:
- **Architecture**: layer count (8 layers default, reducible to 4), attention heads, embedding dimensions
- **Hyperparameters**: learning rate (observed range 0.5 to 4.7), batch size, weight decay, dropout
- **Training dynamics**: optimizers, learning rate schedulers, gradient clipping, warmup steps
- **Activation functions**: GELU, ReLU, SiLU
- **Vocabulary size**: down to 256 for byte-level encoding
- **Sequence length**: adjustable context windows

---

## 6. Infrastructure

### 6.1 Immutability Boundaries
- **prepare.py**: Fixed constants, immutable during experiments
  - Data preparation (dataset downloads)
  - Tokenizer training (BPE)
  - Runtime utilities (dataloaders, evaluation functions)
  - Remains unmodified by agents
- **train.py**: Single mutable file
  - GPT model architecture
  - Optimizer implementations (Muon + AdamW)
  - Training loop
  - All architectural and hyperparameter changes occur here
- **program.md**: Human-edited only
  - Agent reads but does not modify
  - Defines research direction and constraints
- **TIME_BUDGET**: Fixed constant (300 seconds)
- **Dataset**: Immutable (TinyStories: 2.7M stories, 673MB parquet file)

### 6.2 File Structure Rationale
- **Three-file architecture**: fits within single LLM context window
- **Minimal dependencies**: only PyTorch required beyond standard library
- **Self-contained setup**: no distributed training complexity
- **Single GPU requirement**: tested on H100, adaptable to lower-end hardware
- **Total codebase**: ~630 lines of Python

### 6.3 Dependencies
- **Python**: 3.10+
- **Core**: PyTorch only
- **Package management**: pyproject.toml for dependency specification
- **Platform**: Currently NVIDIA GPU (community forks support macOS, Windows, AMD)

### 6.4 Design Patterns
- **Single modification target**: prevents scope creep
- **Git commits**: create perfect audit trail
- **TSV logging**: zero infrastructure requirement
- **Fixed time budgets**: force agents to find changes that matter in practice
- **Evaluation isolation**: prevents metric gaming
- **Constraint-based safety**: guardrails through immutability and time limits

---

## 7. Performance Optimizations

### 7.1 Time Budgets
- **Fixed 5-minute duration**: exactly 300 seconds per experiment
- **Resource constraint**: prevents runaway training
- **Fair comparison**: ensures results remain comparable across modifications
- **Efficiency forcing function**: discovers optimal configurations for available compute
- **Throughput optimization**: enables ~12 experiments/hour

### 7.2 Resource Constraints
- **Single GPU**: no distributed training overhead
- **Minimal memory**: fits on consumer hardware with adjusted hyperparameters
- **Fast feedback loops**: 5-minute cycles enable rapid iteration
- **Bounded search space**: single-file constraint limits exploration scope

### 7.3 Code Size Optimization
- **630 lines total**: entire system fits in LLM context
- **Minimal dependencies**: reduces setup complexity
- **Self-contained**: no external services required
- **Reviewable diffs**: single-file changes easy to inspect

---

## 8. Analysis Tools

### 8.1 Post-Hoc Analysis
- **Git history analysis**: review commit sequence to understand optimization path
- **Metric progression**: track val_bpb improvement over time
- **Change attribution**: identify which modifications contributed to improvements
- **Transfer analysis**: validate improvements across model scales

### 8.2 Visualization
- **Git log visualization**: commit graph shows experiment lineage
- **Metric plots**: val_bpb over experiment number
- **No explicit visualization tools mentioned**: analysis primarily through git and logs

### 8.3 Metrics Analysis
- **Single metric focus**: val_bpb as primary optimization target
- **Improvement tracking**: percentage gains calculated (11% in Karpathy's run)
- **Baseline comparison**: all experiments compared against initial baseline
- **Additive validation**: verify improvements stack correctly

---

## 9. Specific Improvements Found

### 9.1 Optimizer Changes
- Correcting AdamW betas
- Tuning both weight decay schedules
- Adjusted initialization parameters

### 9.2 Architectural Modifications
- Adding a scaler to parameterless QKnorm to sharpen attention
- Widening banded attention
- Applying regularization to Value Embeddings

### 9.3 Results
- ~700 edits executed
- ~20 additive changes identified
- Training time: 2.02 → 1.80 hours (11% improvement)
- Changes transferred successfully to larger models

---

## 10. Future Vision & Scaling

### 10.1 Parallel Exploration
- **Multiple agents**: exploring different optimizations simultaneously
- **Promotion mechanism**: most promising ideas promoted to larger scales
- **Human contribution**: humans optionally contribute at the edges
- **Sprawling DAG**: commits going in every direction rather than single main branch

### 10.2 Multi-Agent Coordination
- **Branchless collaboration**: agents push commits independently without blocking
- **Bare git repository**: agents interact via git bundles
- **Fetch by hash**: any commit accessible by hash
- **DAG browsing**: children, leaves, and lineage exploration
- **Arbitrary diffs**: compare any two commits

### 10.3 Scaling Challenges
- **Concurrent access**: SQLite + single binary works at small scale
- **Bottleneck**: dozens/hundreds of agents pushing simultaneously
- **Production readiness**: current implementations are "sketches," not production infrastructure

---

## 11. Applicability & Limitations

### 11.1 Works For
- ML training optimization
- Prompt engineering
- RAG pipelines
- Compiler tuning
- API optimization
- System prompts
- CSS/layout optimization
- SQL query optimization
- Infrastructure code
- **Requirement**: fast feedback loops + scalar metrics

### 11.2 Fails For
- Subjective quality (no metric)
- Slow feedback loops
- Multi-file architectural changes
- Safety-critical systems requiring human review

---

## 12. Key Design Principles

1. **Single modification target** keeps diffs reviewable and prevents scope creep
2. **Fixed 5-minute budget** ensures platform-independent comparisons
3. **Self-contained implementation** requires only PyTorch and minimal dependencies
4. **Vocab-size-independent metric** (val_bpb) enables fair architectural comparisons
5. **Evaluation isolation** prevents metric gaming
6. **Git-based memory** creates learning feedback loop
7. **Binary decisions** eliminate subjective judgment
8. **Constraint-based safety** through immutability and time limits
9. **Context window fit** enables agent to understand entire system
10. **Never stop philosophy** enables relentless exploration

---

## 13. Comparison with Traditional AutoML

### 13.1 Differences from AutoML
- **Not random variations**: agent reads research papers, develops hypotheses
- **Not evolutionary algorithms**: uses reasoning and learning from past experiments
- **Internet access**: can research and incorporate external knowledge
- **Hypothesis-driven**: forms theories about what might improve performance
- **Learning from history**: reviews git log to inform next experiments

### 13.2 Sophistication
- More sophisticated than prior automated optimization approaches
- Combines reasoning, research, and experimentation
- Fundamentally different from grid search or random search

---

## Sources

- [100 Autonomous ML Experiments Overnight](https://jangwook.net/en/blog/en/karpathy-autoresearch-overnight-ml-experiments/)
- [Karpathy's Autoresearch: 630 Lines That Let AI Optimize Its Own Training](https://launchberg.com/karpathy-autoresearch)
- [AI Agents Driving Autonomous ML Experimentation](https://kenhuangus.substack.com/p/exploring-andrej-karpathys-autoresearch)
- [Karpathy's Autoresearch Went Viral. Here's How It Works](https://alexeyondata.substack.com/p/karpathys-autoresearch-went-viral)
- ['The Karpathy Loop': Former OpenAI researcher's autonomous agents ran 700 experiments](https://fortune.com/2026/03/17/andrej-karpathy-loop-autonomous-ai-agents-future/)
- [How Autoresearch will change Small Language Models adoption](https://www.philschmid.de/autoresearch)
- [Karpathy's Autoresearch Boosts Nanochat Training: 11% Faster](https://blockchain.news/ainews/karpathy-s-autoresearch-boosts-nanochat-training-11-faster-time-to-gpt-2-benchmark-analysis-and-business-implications)
- [I Trained a Model Using Karpathy's Autoresearch](https://whenibuild.substack.com/p/i-trained-a-model-using-karpathys)
- [Autonomous Experimentation Loop (autoexp)](https://gist.github.com/adhishthite/16d8fd9076e85c033b75e187e8a6b94e)
- [AgentHub (Karpathy)](https://rywalker.com/research/agenthub)
