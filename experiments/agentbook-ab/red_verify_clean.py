"""Re-RED-verify every manifest task against its OWN base (clean venv).
A task is valid iff base+test_patch FAILS and gold+test_patch PASSES."""
import json, subprocess, sys, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0, '.')
from cell_workspace import prepare_run_dir
from benchmark.paths import VENV_PY, TASKS, ORACLE, DEFAULT_MANIFEST
ROOT_TMP = Path(tempfile.gettempdir()) / "redverify"

def run_ftp(meta, repo):
    cmd=[str(VENV_PY),'-m','pytest',*meta['fail_to_pass'],'-q','--no-header','-p','no:cacheprovider']
    try:
        r=subprocess.run(cmd,cwd=repo,capture_output=True,text=True,timeout=180)
        return r.returncode==0
    except subprocess.TimeoutExpired:
        return False

def prep(iid, tag, gold=False):
    rd=prepare_run_dir(iid,tag,runs_dir=ROOT_TMP)
    meta=json.loads((TASKS/iid/'META.json').read_text())
    for tf in meta['test_files']:
        s=TASKS/iid/'repo'/tf; d=rd/tf
        d.parent.mkdir(parents=True,exist_ok=True)
        if s.exists(): shutil.copy2(s,d)
    if gold:
        gp=(ORACLE/iid/'gold.patch').read_text(); (rd/'_g.patch').write_text(gp)
        subprocess.run(['git','apply','_g.patch'],cwd=rd,capture_output=True); (rd/'_g.patch').unlink()
    tp=(ORACLE/iid/'test.patch').read_text(); (rd/'_t.patch').write_text(tp)
    ap=subprocess.run(['git','apply','--include=*','_t.patch'],cwd=rd,capture_output=True,text=True)
    (rd/'_t.patch').unlink(missing_ok=True)
    return meta, rd, ap.returncode

def check(iid):
    try:
        meta,rdb,apb=prep(iid,'base',gold=False); base_pass=run_ftp(meta,rdb)
        meta,rdg,apg=prep(iid,'gold',gold=True); gold_pass=run_ftp(meta,rdg)
        red = (not base_pass) and gold_pass
        return iid,{'base_pass':base_pass,'gold_pass':gold_pass,'gold_apply_rc':apg,'red':red}
    except Exception as e:
        return iid,{'error':str(e)[:120],'red':False}

man=json.loads(Path(DEFAULT_MANIFEST).read_text())
ids=[e['instance_id'] for e in man]
out={}
with ThreadPoolExecutor(max_workers=8) as ex:
    for fut in as_completed([ex.submit(check,i) for i in ids]):
        iid,res=fut.result(); out[iid]=res
        print(f"{iid.split('-')[-1]}: red={res.get('red')} base_pass={res.get('base_pass')} gold_pass={res.get('gold_pass')} {res.get('error','')}",flush=True)
Path('_oracle/red_clean.json').write_text(json.dumps(out,indent=2)+"\n")
red=[i for i,r in out.items() if r.get('red')]
print(f"\nGENUINELY RED: {len(red)}/{len(ids)}")
print("valid:", sorted(i.split('-')[-1] for i in red))
