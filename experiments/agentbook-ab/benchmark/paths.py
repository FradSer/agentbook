from pathlib import Path

EXP_ROOT = Path(__file__).resolve().parent.parent
TASKS = EXP_ROOT / "tasks"
ORACLE = EXP_ROOT / "_oracle"
RUNS = EXP_ROOT / "runs"
DATA = EXP_ROOT / "_data"
REPO_DIR = EXP_ROOT / "_repo"
VENV_PY = EXP_ROOT / ".venv" / "bin" / "python"
DEFAULT_MANIFEST = TASKS / "manifest.json"
CORPUS_SEED = ORACLE / "corpus.seed.json"
CORPUS_HAND = ORACLE / "corpus.json"
