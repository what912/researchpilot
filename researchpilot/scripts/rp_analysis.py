"""Transparent independent-unit aggregation and optional paired bootstrap/sign-flip."""
import csv
import json
import math
import random
import statistics as st
from pathlib import Path
from rp_contracts import require
from rp_store import atomic, dumps, hashfile, new_id, now

def rows_from(path):
    p=Path(path)
    if p.suffix.lower()=='.csv':
        with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    elif p.suffix.lower()=='.jsonl': rows=[json.loads(line) for line in p.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    else:
        obj=json.loads(p.read_text(encoding='utf-8-sig')); rows=obj.get('rows') if isinstance(obj,dict) else obj
    require(isinstance(rows,list) and all(isinstance(r,dict) for r in rows),'Results must contain a list of row objects')
    return rows

def percentile(values,q):
    xs=sorted(values); pos=(len(xs)-1)*q; lo=int(pos); hi=min(lo+1,len(xs)-1)
    return xs[lo]+(xs[hi]-xs[lo])*(pos-lo)

def bootstrap(xs,rng,iterations=2000):
    if len(xs)<2: return None
    samples=[st.mean(rng.choices(xs,k=len(xs))) for _ in range(iterations)]
    return [percentile(samples,.025),percentile(samples,.975)]

def analyze(store,path,metric,unit,group='group',paired=False,test=None,synthetic=False,run_ids=None,predefined=False):
    rows=rows_from(path); units={}; failed=0; missing=0; reasons=[]
    require(len(rows)<=100000,'V1 analysis row limit 100000')
    for index,r in enumerate(rows):
        if r.get('status','completed')!='completed': failed+=1; continue
        require(group in r and unit in r,f'Row {index} needs {group} and independent-unit column {unit}')
        value=r.get(metric)
        try: v=float(value) if value is not None and str(value).strip() else None
        except (TypeError,ValueError): v=None
        if v is None or not math.isfinite(v): missing+=1; reasons.append(index); continue
        key=(str(r[group]),str(r[unit])); units.setdefault(key,[]).append(v)
    aggregated={key:st.mean(v) for key,v in units.items()}
    groups=sorted({g for g,_ in aggregated}); rng=random.Random(42); descriptive={}
    for g in groups:
        xs=[v for (label,_),v in aggregated.items() if label==g]
        descriptive[g]={'independent_units':len(xs),'observed_rows':sum(len(v) for (label,_),v in units.items() if label==g),
                        'mean':st.mean(xs),'median':st.median(xs),'sd':st.stdev(xs) if len(xs)>1 else None,
                        'min':min(xs),'max':max(xs),'bootstrap_mean_ci95':bootstrap(xs,rng)}
    comparison=None
    if paired:
        require(len(groups)==2,'Paired comparison requires exactly two groups')
        a,b=groups; ua={u for g,u in aggregated if g==a}; ub={u for g,u in aggregated if g==b}
        keys=sorted(ua&ub); require(keys,'No matched independent units')
        differences=[aggregated[(b,u)]-aggregated[(a,u)] for u in keys]
        sd=st.stdev(differences) if len(keys)>1 else None
        comparison={'contrast':b+' - '+a,'paired_units':len(keys),'matched_unit_ids':keys,
                    'unmatched_units':{a:sorted(ua-ub),b:sorted(ub-ua)},'mean_difference':st.mean(differences),
                    'bootstrap_difference_ci95':bootstrap(differences,rng),
                    'cohen_dz':st.mean(differences)/sd if sd else None,'test':None}
        if test:
            require(test=='signflip','Supported explicit paired test: signflip')
            require(len(keys)>=2,'At least two independent paired units required for a test')
            threshold=abs(st.mean(differences)); n=len(keys)
            if n<=16:
                permutations=[abs(st.mean([x if mask&(1<<i) else -x for i,x in enumerate(differences)])) for mask in range(1<<n)]
                p=sum(x>=threshold-1e-12 for x in permutations)/len(permutations); method='exact'
            else:
                permutations=[abs(st.mean([x*rng.choice((-1,1)) for x in differences])) for _ in range(10000)]
                p=(1+sum(x>=threshold-1e-12 for x in permutations))/(len(permutations)+1); method='monte_carlo'
            comparison['test']={'name':'paired sign-flip','method':method,'two_sided_p':p,'assumption':'Independent units; paired null differences sign-exchangeable'}
    elif test: require(False,'Test requires explicit --paired')
    runs=[]
    allowed_input_hashes=set()
    for rid in run_ids or []:
        run=store.get(rid,'RunRecord'); require(run['status']=='completed','Analysis link requires completed run')
        for aid in run['artifact_ids']:
            artifact=store.get(aid,'Artifact'); store.verify_artifact(artifact)
            allowed_input_hashes.add(artifact['sha256'])
        runs.append(run)
    if runs:
        require(hashfile(path) in allowed_input_hashes,'Analysis input is not a verified artifact of linked runs; omit run links for provenance-limited external/derived data')
    tier='code_chain_runnable' if runs and all(r['stage']=='smoke' for r in runs) else 'directional_signal'
    warnings=['Bootstrap resamples declared independent units; row repeats are first averaged.',
              'Scientific interpretation and confounder assessment require Codex and the experimental protocol.']
    if any(d['independent_units']<5 for d in descriptive.values()): warnings.append('Few independent units; interval and effect estimates are unstable.')
    if synthetic: warnings.append('SYNTHETIC TEST DATA: no real scientific performance claim.')
    if not runs: warnings.append('Imported file is observed, but execution provenance is not linked to a run.')
    report={'generated_at':now(),'input_path':str(Path(path).resolve()),'input_sha256':hashfile(path),
            'metric':metric,'independent_unit':unit,'aggregation':'Mean within group/unit, then equal weight per independent unit',
            'total_rows':len(rows),'failed_rows':failed,'missing_metric_rows':missing,'missing_row_indexes':reasons,
            'seed_count':len({str(r['seed']) for r in rows if r.get('seed') is not None}),
            'descriptive':descriptive,'paired':comparison,'analysis_type':'predefined' if predefined else 'exploratory',
            'synthetic':synthetic,'run_ids':run_ids or [],'conclusion_tier':tier,'warnings':warnings}
    aid=new_id('Artifact'); rel='reports/'+aid+'.json'
    atomic(store.root,rel,dumps(report)+'\n')
    atomic(store.root,'reports/'+aid+'.md','# Result analysis\n\n'+ ('SYNTHETIC TEST DATA\n\n' if synthetic else '')+'```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n')
    store.put('Artifact',{'id':aid,'run_id':None,'path':rel,'sha256':hashfile(store.root/rel),'role':'analysis_report','synthetic':synthetic},internal=True)
    return {'artifact_id':aid,'report_path':str(store.root/rel),'report':report}
