#!/usr/bin/env python3
"""ResearchPilot deterministic CLI; semantic research is performed by Codex using SKILL.md."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from rp_contracts import KINDS, MODES, VERSION, RPError, require, validate
from rp_store import Store, atomic, dumps, inside, load, new_id, now, hashfile
from rp_materials import doctor, ingest, search, repo_map, remote_search, fetch
from rp_execute import run, record_external, recover
from rp_analysis import analyze

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='cmd',required=True)
    def command(name,help,project=True):
        x=sub.add_parser(name,help=help); x.add_argument('--json',action='store_true',help='Machine JSON stdout; errors stderr, nonzero exit')
        if project: x.add_argument('--project',required=name not in ('doctor',),help='Research project directory, never the installed Skill')
        return x
    x=command('doctor','Probe dependencies; add host observations with --host'); x.add_argument('--host',help='Host capability JSON, no secret values')
    x=command('init','Create isolated project without overwriting'); x.add_argument('--profile'); x.add_argument('--question'); x.add_argument('--mode',choices=MODES,default='pipeline'); x.add_argument('--depth',choices=['quick','standard','deep'],default='standard')
    x=command('ingest','Import text/PDF/structured Source without execution'); x.add_argument('path'); x.add_argument('--scope',choices=['metadata_only','abstract_only','partial_text','full_text'],default='partial_text'); x.add_argument('--title')
    x=command('search','Local lexical search; quoted FTS with Chinese characters'); x.add_argument('query'); x.add_argument('--limit',type=int,default=10)
    x=command('memory','Validate/save or list typed research records'); x.add_argument('action',choices=['put','list','get']); x.add_argument('--kind',choices=list(KINDS)); x.add_argument('--file'); x.add_argument('--id')
    x=command('plan','Validate and persist a full ExperimentPlan'); x.add_argument('file')
    x=command('run','Preview by default; --execute launches authorized local CPU job'); x.add_argument('experiment_id'); x.add_argument('--execute',action='store_true'); x.add_argument('--run-id')
    x=command('record','Register external actual execution manifest and hash-verified artifacts'); x.add_argument('file')
    x=command('artifact','Import/hash an actual report or non-run artifact'); x.add_argument('path'); x.add_argument('--role',default='research_report'); x.add_argument('--synthetic',action='store_true')
    x=command('analyze','Descriptive stats and optional matched independent-unit comparison'); x.add_argument('path'); x.add_argument('--metric',required=True); x.add_argument('--unit',required=True); x.add_argument('--group',default='group'); x.add_argument('--paired',action='store_true'); x.add_argument('--test',choices=['signflip']); x.add_argument('--synthetic',action='store_true'); x.add_argument('--run-id',action='append'); x.add_argument('--predefined',action='store_true')
    for cmd in ('status','resume'): command(cmd,'Restore concise persisted evidence, decisions, unfinished tasks and next action')
    x=command('recover','Cancel orphaned running record explicitly, without rerunning'); x.add_argument('run_id')
    command('validate','Check record schemas, references and source/artifact hashes')
    x=command('export','Export current records, source table and incomplete-safe BibTeX'); x.add_argument('--output',default='reports/export')
    x=command('repo','Static repository inventory and code symbol locations'); x.add_argument('path')
    x=command('remote','Bounded Crossref metadata search with real error logs'); x.add_argument('query'); x.add_argument('--purpose',choices=['literature','counterexample'],default='literature'); x.add_argument('--rows',type=int,default=5)
    x=command('fetch','Fetch allowlisted public HTTPS paper endpoint into project'); x.add_argument('url'); x.add_argument('--output',required=True)
    x=command('delete','Preview project removal; explicit --execute --confirm project_id required'); x.add_argument('--execute',action='store_true'); x.add_argument('--confirm')
    x=command('contract','Display machine-readable field contract',False); x.add_argument('--kind',choices=list(KINDS))
    return p

def bibtex(s):
    def esc(v): return str(v).replace('\\','\\textbackslash{}').replace('{','\\{').replace('}','\\}').replace('\n',' ')
    fields={'title':s['title']}
    if s['authors']: fields['author']=' and '.join(s['authors'])
    if s['year']: fields['year']=str(s['year'])
    for key in ('doi','url'):
        if s.get(key): fields[key]=s[key]
    missing=[k for k in ('authors','year','doi') if not s.get(k)]
    if missing: fields['note']='Incomplete verified metadata; missing '+', '.join(missing)
    return '@misc{'+s['id']+',\n'+',\n'.join('  '+k+' = {'+esc(v)+'}' for k,v in fields.items())+'\n}\n'

def export(store,output):
    inside(store.root,output+'/records.jsonl')
    rec=store.list()
    paths=[atomic(store.root,output+'/records.jsonl','\n'.join(dumps(r) for r in rec)+'\n')]
    sources=[r for r in rec if r['kind']=='Source']
    paths.append(atomic(store.root,output+'/references.bib','\n'.join(bibtex(s) for s in sources)))
    table='| source_id | title | scope | sha256 |\n|---|---|---|---|\n'
    table+='\n'.join('| '+ ' | '.join(str(s.get(k)).replace('|','\\|') for k in ('id','title','reading_scope','sha256'))+' |' for s in sources)
    paths.append(atomic(store.root,output+'/sources.md',table+'\n'))
    paths.append(atomic(store.root,output+'/checkpoint.json',dumps(store.checkpoint())+'\n'))
    return {'paths':paths,'records':len(rec),'sources':len(sources),'authority':'state.sqlite3; exports are rebuildable'}

def dispatch(a):
    if a.cmd=='contract':
        def typename(t): return [x.__name__ for x in t] if isinstance(t,tuple) else t.__name__
        return {'schema_version':VERSION,'required_fields':{k:{f:typename(t) for f,t in v.items()} for k,v in KINDS.items() if not a.kind or k==a.kind},'rules':'See references/contracts.md and rp_contracts.validate for enum and relationship rules'}
    if a.cmd=='doctor' and not a.project: return doctor(host=load(a.host) if a.host else None)
    if a.cmd=='init':
        root=Path(a.project).resolve()
        require(not root.exists() or not any(root.iterdir()),'init requires new or empty project directory')
        s=Store(root,create=True)
        try:
            d=load(a.profile) if a.profile else {'id':new_id('ProjectProfile'),'question':a.question or 'unknown','inputs':[],
               'domain':'unknown','deadline':None,'compute':{},'budget':{},'existing_results':[],'user_requirements':[],
               'observations':[],'assumptions':[],'authorization':{},'preferences':{'language':'zh','multi_agent':'auto'},'mode':a.mode,'depth':a.depth}
            s.init_profile(d); doctor(s); s.checkpoint(); return {'project':str(root),'profile':d,'schema_version':VERSION}
        finally: s.close()
    s=Store(a.project)
    try:
        if a.cmd=='doctor': return doctor(s,load(a.host) if a.host else None)
        if a.cmd=='ingest': return ingest(s,a.path,a.scope,a.title)
        if a.cmd=='search': return search(s,a.query,a.limit)
        if a.cmd=='memory':
            if a.action=='put':
                require(a.kind and a.file,'memory put needs --kind and --file'); d=load(a.file)
                if a.kind=='CodeMapping':
                    repo=s.get(d['repo_id'],'RepoMap'); info=next((f for f in repo['files'] if f['path']==d['code_path']),None)
                    require(info and info['sha256']==d['file_sha256'],'Code mapping must match actual RepoMap snapshot')
                    path=inside(Path(repo['root']),d['code_path'])
                    require(hashfile(path)==d['file_sha256'],'Repository file changed since snapshot; refresh RepoMap')
                    require(d['end_line']<=len(path.read_text(encoding='utf-8').splitlines()),'Code line outside file')
                result=s.put(a.kind,d); s.checkpoint(); return result
            if a.action=='get': require(a.id,'memory get needs --id'); return s.get(a.id,a.kind)
            return {'records':s.list(a.kind)}
        if a.cmd=='plan':
            d=load(a.file); validate('ExperimentPlan',d)
            for path in d['inputs']: require(inside(s.root,path).is_file(),'Plan input missing: '+path)
            for path in d['artifacts']: inside(s.root,path.replace('{run_dir}','runs/validation'))
            if d['cwd']!='.': require(inside(s.root,d['cwd']).is_dir(),'Plan cwd missing')
            result=s.put('ExperimentPlan',d); atomic(s.root,'experiments/'+d['id']+'.json',dumps(result)+'\n'); s.checkpoint(); return result
        if a.cmd=='run': return run(s,a.experiment_id,a.execute,a.run_id)
        if a.cmd=='record': return record_external(s,load(a.file))
        if a.cmd=='artifact':
            path=Path(a.path).resolve(); require(path.is_file(),'Artifact input missing')
            require(path.stat().st_size<=30*1024*1024,'Artifact exceeds 30 MiB limit')
            aid=new_id('Artifact'); target='reports/'+aid+path.suffix
            atomic(s.root,target,path.read_bytes())
            d={'id':aid,'run_id':None,'path':target,'sha256':hashfile(inside(s.root,target)),'role':a.role,'synthetic':a.synthetic}
            s.put('Artifact',d,internal=True); return d
        if a.cmd=='recover': return recover(s,a.run_id)
        if a.cmd=='analyze': return analyze(s,a.path,a.metric,a.unit,a.group,a.paired,a.test,a.synthetic,a.run_id,a.predefined)
        if a.cmd in ('status','resume'): return s.checkpoint()
        if a.cmd=='validate':
            result=s.integrity(); require(result['valid'],'Integrity errors: '+dumps(result['errors'])); return result
        if a.cmd=='export': return export(s,a.output)
        if a.cmd=='repo': return repo_map(s,a.path)
        if a.cmd=='remote':
            result=remote_search(s,a.query,a.purpose,a.rows)
            require(result['status']=='completed','Remote query failed and saved: '+result.get('error','unknown')); return result
        if a.cmd=='fetch':
            inside(s.root,a.output)
            raw,meta=fetch(s,a.url); return {'path':atomic(s.root,a.output,raw),'request':meta}
        if a.cmd=='delete':
            preview={'project':str(s.root),'project_id':s.project_id,'files':len(list(s.root.rglob('*'))),'executed':False}
            if a.execute:
                require(a.confirm==s.project_id,'Deletion requires --confirm exact project_id')
                root=s.root; s.close(); s=None
                require(root==Path(a.project).resolve() and root.name not in ('skills','researchpilot'),'Unsafe deletion target')
                shutil.rmtree(root); preview['executed']=True
            return preview
    finally:
        if s: s.close()

def main():
    a=parser().parse_args()
    try:
        result=dispatch(a)
        print(json.dumps(result,ensure_ascii=False,indent=None if a.json else 2,allow_nan=False))
        if a.cmd=='run' and result.get('run',{}).get('status') in ('failed','cancelled'): return 3
        return 0
    except (RPError,OSError,ValueError,KeyError,IndexError) as e:
        print('ResearchPilot error: '+str(e),file=sys.stderr); return 2

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr,'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
