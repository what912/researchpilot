"""Behavioral offline acceptance tests. Temporary fixtures are always synthetic."""
import copy
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'researchpilot/scripts'))
from rp_store import Store, inside, load, hashfile
from rp_contracts import RPError, validate
from rp_materials import ingest, search, repo_map
from rp_execute import run, recover, record_external
from rp_analysis import analyze
from fixtures import setup, idea, hypothesis, plan

CLI=Path(__file__).resolve().parents[1]/'researchpilot/scripts/researchpilot.py'

class ResearchPilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ResearchPilot 中文 空格 ')
        self.root=Path(self.tmp.name); self.project=self.root/'project'
        cp=subprocess.run([sys.executable,str(CLI),'init','--project',str(self.project),'--question','Synthetic test','--json'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(cp.returncode,0,cp.stderr)
        setup(self.project); self.s=Store(self.project)
        self.s.put('IdeaCard',idea()); self.s.put('Hypothesis',hypothesis())
    def tearDown(self): self.s.close(); self.tmp.cleanup()
    def put_plan(self,d=None):
        d=d or plan(); self.s.put('ExperimentPlan',d); return d
    def test_bilingual_dedup_scope_and_injection(self):
        x=ingest(self.s,self.project/'paper.json'); y=ingest(self.s,self.project/'paper.json')
        self.assertTrue(y['duplicate']); self.assertEqual(len(self.s.list('Source')),1)
        self.assertTrue(search(self.s,'玩具')['results']); self.assertTrue(search(self.s,'sequential gate')['results'])
        for q in ["' OR 1=1 --",'中文 * NEAR("x")','"; DROP TABLE chunks;--','空 格 # $ %','!']:
            search(self.s,q)
        self.s.fts=False; self.assertTrue(search(self.s,'玩具')['results'])
        self.assertFalse((self.project/'PWNED.txt').exists()); self.assertTrue(x['source']['sha256'])
        p=self.project/'abstract.json'; p.write_text(json.dumps({'title':'Abstract only','reading_scope':'abstract_only','text':'An abstract.'}),encoding='utf-8')
        self.assertEqual(ingest(self.s,p)['source']['reading_scope'],'abstract_only')
    def test_source_pdf_chinese_english_and_unread_figures(self):
        if not importlib.util.find_spec('reportlab'): self.skipTest('reportlab fixture generator unavailable')
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        p=self.project/'中文 English.pdf'; c=canvas.Canvas(str(p)); c.setFont('STSong-Light',12)
        c.drawString(50,700,'中文科研测试 English retrieval'); c.save()
        x=ingest(self.s,p); self.assertTrue(search(self.s,'English')['results']); self.assertTrue(search(self.s,'中文')['results'])
        self.assertIn('figures',x['source']['unread_elements']); self.assertIn('page 1',search(self.s,'English')['results'][0]['locator'])
    def test_contract_references_and_project_isolation(self):
        with self.assertRaises(RPError): self.s.put('Hypothesis',{**hypothesis('hyp_missing'),'idea_id':'idea_nonexistent'})
        with self.assertRaises(RPError): validate('Claim',{'id':'claim_bad'})
        c={'id':'claim_bad','text':'Unsupported','category':'source_fact','confidence':'low','confidence_basis':'none',
           'references':[{'source_id':'src_missing','locator':'page 1'}],'run_ids':[],'attribution':'author_claim'}
        with self.assertRaises(RPError): self.s.put('Claim',c)
        c.update(category='measured_result',references=[],run_ids=['run_missing'])
        with self.assertRaises(RPError): self.s.put('Claim',c)
        other=self.root/'other'; subprocess.run([sys.executable,str(CLI),'init','--project',str(other),'--json'],capture_output=True,check=True)
        o=Store(other)
        try:
            self.assertEqual(o.list('IdeaCard'),[])
            with self.assertRaises(RPError): o.get('idea_demo')
            with self.assertRaises(RPError): o.put('IdeaCard',{**idea('idea_cross'),'project_id':self.s.project_id})
        finally: o.close()
    def test_repo_mapping_actual_files_and_no_execution(self):
        d=repo_map(self.s,self.project/'repo'); self.assertIsNone(d['commit']); self.assertIn('AGENTS.md',d['instructions'])
        toy=next(f for f in d['files'] if f['path']=='toy.py'); self.assertTrue(any(s['name']=='predict' for s in toy['symbols']))
        self.assertFalse(list(self.project.glob('runs/*/metrics.json')))
    def test_novelty_check_requires_countersearch_and_can_withdraw(self):
        with self.assertRaises(RPError): self.s.put('IdeaCard',idea('idea_unchecked',status='differentiated'))
        d=idea('idea_withdrawn',status='withdrawn'); d['supersedes']='idea_demo'; self.s.put('IdeaCard',d)
        self.assertEqual(self.s.checkpoint()['ideas'][0]['novelty_status'],'withdrawn')
    def test_dry_smoke_completed_hashes_and_resume_no_rerun(self):
        p=self.put_plan(); dry=run(self.s,p['id']); self.assertFalse(dry['executed']); self.assertEqual(self.s.list('RunRecord'),[])
        r=run(self.s,p['id'],True)['run']; self.assertEqual(r['status'],'completed',r)
        self.assertEqual(r['exit_code'],0); self.assertEqual(r['metrics']['samples'],12)
        self.assertTrue(self.s.integrity()['valid']); before=len(self.s.list('RunRecord'))
        again=run(self.s,p['id'],True,r['id']); self.assertFalse(again['executed']); self.assertEqual(len(self.s.list('RunRecord')),before)
        cp=subprocess.run([sys.executable,str(CLI),'resume','--project',str(self.project),'--json'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(cp.returncode,0,cp.stderr); self.assertEqual(json.loads(cp.stdout)['counts']['RunRecord'],1)
        art=self.s.get(r['artifact_ids'][0]); (self.project/art['path']).write_text('changed',encoding='utf-8')
        self.assertFalse(self.s.integrity()['valid'])
    def test_failure_missing_artifacts_timeout_tree_and_budget(self):
        p=plan('exp_failure'); p['command']=['{python}','-c','raise SystemExit(7)']; p['requested']['samples']=0
        self.put_plan(p); self.assertEqual(run(self.s,p['id'],True)['run']['status'],'failed')
        p=plan('exp_missing'); p['command']=['{python}','-c','print(1)']; p['requested']['samples']=0
        self.put_plan(p); self.assertEqual(run(self.s,p['id'],True)['run']['status'],'failed')
        target=self.project/'child_survived.txt'
        child='import time; from pathlib import Path; time.sleep(1); Path('+repr(str(target))+').write_text("survived")'
        parent='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr(child)+']); time.sleep(5)'
        p=plan('exp_timeout',seconds=.2); p['command']=['{python}','-c',parent]; p['requested']['samples']=0
        self.put_plan(p); r=run(self.s,p['id'],True)['run']; self.assertEqual(r['status'],'cancelled',r)
        time.sleep(1.1); self.assertFalse(target.exists(),'Descendant process survived timeout')
        p=plan('exp_budget'); p['requested']['api_usd']=1
        with self.assertRaises(RPError): validate('ExperimentPlan',p)
        p['budget']['api_usd']=1; self.put_plan(p)
        with self.assertRaises(RPError): run(self.s,p['id'],True)
    def test_orphan_recovery(self):
        p=self.put_plan(); r=run(self.s,p['id'],True)['run']
        # Construct an actual interrupted state by replaying the saved planned/running versions in an isolated DB fixture.
        self.s.db.execute('UPDATE records SET payload=? WHERE id=?',(json.dumps({**r,'status':'running','ended_at':None,'exit_code':None,'artifact_ids':[]}),r['id'])); self.s.db.commit()
        (self.project/'execution.lock').write_text(json.dumps({'pid':99999999,'run_id':r['id']}),encoding='utf-8')
        self.assertEqual(recover(self.s,r['id'])['run']['status'],'cancelled')
        self.assertFalse(recover(self.s,r['id'])['changed'])
    def test_statistics_missing_failed_pairing_independent_units(self):
        rows=[{'group':g,'seed':i,'score':v,'status':'completed'} for g,vs in [('A',[1,2,3]),('B',[2,3,4])] for i,v in enumerate(vs)]
        rows += [{'group':'A','seed':0,'score':1}, {'group':'B','seed':7,'score':None},{'group':'B','seed':8,'score':0,'status':'failed'}]
        p=self.project/'synthetic.json'; p.write_text(json.dumps(rows),encoding='utf-8')
        r=analyze(self.s,p,'score','seed',paired=True,test='signflip',synthetic=True)['report']
        self.assertEqual(r['descriptive']['A']['independent_units'],3); self.assertEqual(r['paired']['mean_difference'],1)
        self.assertEqual(r['failed_rows'],1); self.assertEqual(r['missing_metric_rows'],1)
        self.assertTrue(r['synthetic']); self.assertEqual(r['paired']['test']['two_sided_p'],.25)
    def test_paths_symlink_and_export(self):
        for p in ('../outside','C:/outside','runs/../../outside','C:relative'):
            with self.assertRaises(RPError): inside(self.project,p)
        link=self.project/'escape'
        try: link.symlink_to(self.root,target_is_directory=True)
        except OSError: pass
        else:
            with self.assertRaises(RPError): inside(self.project,'escape/outside')
            link.unlink()
        ingest(self.s,self.project/'paper.json')
        cp=subprocess.run([sys.executable,str(CLI),'export','--project',str(self.project),'--json'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(cp.returncode,0,cp.stderr); self.assertIn('Incomplete', (self.project/'reports/export/references.bib').read_text(encoding='utf-8'))
    def test_v1_migration_preserves_records(self):
        self.s.close(); db=sqlite3.connect(self.project/'state.sqlite3')
        before=db.execute('SELECT id,payload FROM records ORDER BY id').fetchall()
        db.execute('DROP TABLE record_versions'); db.execute('ALTER TABLE records DROP COLUMN revision'); db.execute('PRAGMA user_version=1'); db.commit(); db.close()
        self.s=Store(self.project); after=self.s.db.execute('SELECT id,payload FROM records ORDER BY id').fetchall()
        self.assertEqual(before,[tuple(x) for x in after]); self.assertEqual(self.s.db.execute('PRAGMA user_version').fetchone()[0],2)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM record_versions').fetchone()[0],len(before))
    def test_external_record_provenance_and_real_hashes(self):
        p=self.put_plan(); data=self.project/'external.json'; data.write_text('{"score":0}',encoding='utf-8')
        out=self.project/'external.stdout'; out.write_text('actual imported fixture output',encoding='utf-8')
        err=self.project/'external.stderr'; err.write_text('',encoding='utf-8')
        manifest={'experiment_id':p['id'],'command':['external fixture'],'started_at':'2026-10-13T00:00:00Z','ended_at':'2026-10-13T00:00:01Z','exit_code':0,
                  'environment':{'synthetic':True},'input_hashes':{},'stdout':str(out),'stderr':str(err),'artifacts':[{'path':str(data),'sha256':hashfile(data)}],'synthetic':True}
        r=record_external(self.s,manifest); self.assertEqual(r['status'],'completed'); self.assertIn('not independently observed',r['provenance'])
        manifest['artifacts'][0]['sha256']='0'*64
        with self.assertRaises(RPError): record_external(self.s,manifest)
    def test_profile_revision_resume_and_stale_evidence(self):
        original=self.s.profile(); revised={**original,'id':'project_revision','supersedes':original['id'],'question':'Revised actual goal'}
        self.s.put('ProjectProfile',revised)
        self.assertEqual(self.s.checkpoint()['project']['question'],'Revised actual goal')
        p=self.put_plan(); r=run(self.s,p['id'],True)['run']; a=self.s.get(r['artifact_ids'][0])
        (self.project/a['path']).write_text('tampered',encoding='utf-8')
        self.assertFalse(self.s.checkpoint()['evidence_integrity']['valid'])
    def test_unauthorized_execution_and_invalid_download_protocol(self):
        from rp_materials import check_url
        p=plan('exp_denied'); p['authorization']['local_execute']=False; self.put_plan(p)
        with self.assertRaises(RPError): run(self.s,p['id'],True)
        self.assertEqual(self.s.list('RunRecord'),[])
        for url in ('http://arxiv.org/pdf/1','https://127.0.0.1/private','file:///secret','https://user:password@arxiv.org/abs/1'):
            with self.assertRaises(RPError): check_url(url)
    def test_cli_code_mapping_rejects_changed_snapshot(self):
        source=ingest(self.s,self.project/'paper.json')['source_id']; repo=repo_map(self.s,self.project/'repo')
        file=next(f for f in repo['files'] if f['path']=='toy.py')
        data={'id':'map_bad','source_id':source,'repo_id':repo['id'],'paper_locator':'Method','code_path':'toy.py',
              'start_line':1,'end_line':2,'symbol':'predict','implementation_type':'synthetic fixture','status':'static','discrepancy':'unknown','file_sha256':file['sha256']}
        path=self.project/'mapping.json'; path.write_text(json.dumps(data),encoding='utf-8')
        (self.project/'repo/toy.py').write_text('# changed snapshot\n',encoding='utf-8')
        cp=subprocess.run([sys.executable,str(CLI),'memory','--project',str(self.project),'put','--kind','CodeMapping','--file',str(path),'--json'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(cp.returncode,2); self.assertEqual(cp.stdout,''); self.assertIn('changed',cp.stderr)
    def test_delete_preview_confirmation_and_other_project_survives(self):
        target=self.root/'delete_me'
        subprocess.run([sys.executable,str(CLI),'init','--project',str(target),'--json'],capture_output=True,check=True)
        preview=subprocess.run([sys.executable,str(CLI),'delete','--project',str(target),'--json'],capture_output=True,text=True,encoding='utf-8')
        obj=json.loads(preview.stdout); self.assertFalse(obj['executed']); self.assertTrue(target.exists())
        denied=subprocess.run([sys.executable,str(CLI),'delete','--project',str(target),'--execute','--confirm','wrong','--json'],capture_output=True)
        self.assertEqual(denied.returncode,2); self.assertTrue(target.exists())
        deleted=subprocess.run([sys.executable,str(CLI),'delete','--project',str(target),'--execute','--confirm',obj['project_id'],'--json'],capture_output=True)
        self.assertEqual(deleted.returncode,0); self.assertFalse(target.exists()); self.assertTrue(self.project.exists())
    def test_actual_git_commit_dirty_inventory(self):
        import shutil
        if not shutil.which('git'): self.skipTest('Git unavailable')
        repo=self.project/'repo'
        for args in (['init'],['add','toy.py','LICENSE','AGENTS.md'],['-c','user.name=Synthetic Fixture','-c','user.email=fixture@example.invalid','commit','-m','Synthetic fixture']):
            cp=subprocess.run(['git','-C',str(repo),*args],capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stderr)
        d=repo_map(self.s,repo); self.assertIsNotNone(d['commit']); self.assertFalse(d['dirty'])
        (repo/'new-config.json').write_text('{}',encoding='utf-8')
        self.assertTrue(repo_map(self.s,repo)['dirty'])
    def test_analysis_run_link_rejects_unrelated_real_file(self):
        p=self.put_plan(); r=run(self.s,p['id'],True)['run']
        fake=self.project/'unrelated.json'; fake.write_text('[{"group":"A","seed":0,"score":100}]',encoding='utf-8')
        with self.assertRaises(RPError): analyze(self.s,fake,'score','seed',run_ids=[r['id']])
        result=analyze(self.s,self.project/'runs'/r['id']/'rows.csv','score','seed',synthetic=True,run_ids=[r['id']])
        self.assertEqual(result['report']['conclusion_tier'],'code_chain_runnable')

if __name__=='__main__': unittest.main(verbosity=2)
