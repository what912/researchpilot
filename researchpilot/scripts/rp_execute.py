"""Reviewed local CPU runs. Hard wall timeout and process-tree termination; no paid/GPU/download jobs."""
import ctypes
import importlib.metadata
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from rp_contracts import require, RPError
from rp_store import atomic, dumps, hashfile, inside, load, new_id, now, sha

class ProcessTree:
    def __init__(self,p):
        self.p=p; self.job=None
        if os.name=='nt':
            from ctypes import wintypes as w
            class Basic(ctypes.Structure):
                _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',w.DWORD),
                          ('Min',ctypes.c_size_t),('Max',ctypes.c_size_t),('Processes',w.DWORD),
                          ('Affinity',ctypes.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
            class IO(ctypes.Structure):
                _fields_=[(name,ctypes.c_uint64) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
            class Extended(ctypes.Structure):
                _fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
            self.api=ctypes.WinDLL('kernel32',use_last_error=True)
            self.api.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]; self.api.CreateJobObjectW.restype=w.HANDLE
            self.api.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]; self.api.SetInformationJobObject.restype=w.BOOL
            self.api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]; self.api.AssignProcessToJobObject.restype=w.BOOL
            self.api.TerminateJobObject.argtypes=[w.HANDLE,w.UINT]; self.api.TerminateJobObject.restype=w.BOOL
            self.api.CloseHandle.argtypes=[w.HANDLE]; self.api.CloseHandle.restype=w.BOOL
            job=self.api.CreateJobObjectW(None,None)
            require(bool(job),'Cannot create Windows job; refusing unbounded execution')
            info=Extended(); info.Basic.Flags=0x2000  # KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)) or not self.api.AssignProcessToJobObject(job,w.HANDLE(int(p._handle))):
                err=ctypes.get_last_error(); self.api.CloseHandle(job); p.kill(); p.wait()
                raise RPError('Cannot bind process tree to Windows job: '+str(err))
            self.job=job
    def stop(self):
        if self.job: self.api.TerminateJobObject(self.job,1)
        elif os.name!='nt':
            try: os.killpg(self.p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        elif self.p.poll() is None: self.p.kill()
    def close(self):
        if self.job: self.api.CloseHandle(self.job); self.job=None
        elif os.name!='nt': self.stop()

def environment():
    deps={}
    for name in ('pypdf','pdfplumber','numpy','torch'):
        try: deps[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: pass
    return {'python':sys.version.split()[0],'executable':sys.executable,'platform':platform.platform(),'dependencies':deps}

def prepare(store,plan,run_id):
    rel='runs/'+run_id
    replacements={'{python}':sys.executable,'{project}':str(store.root),'{run_dir}':str(inside(store.root,rel)),
                  '{samples}':str(plan['requested']['samples']),'{seed}':str(plan['seeds'][0] if plan['seeds'] else 0)}
    argv=[]
    for arg in plan['command']:
        for key,value in replacements.items(): arg=arg.replace(key,value)
        argv.append(arg)
    artifacts=[p.replace('{run_dir}',rel) for p in plan['artifacts']]
    for p in artifacts: inside(store.root,p)
    cwd=store.root if plan['cwd']=='.' else inside(store.root,plan['cwd'])
    require(cwd.is_dir(),'cwd not found')
    hashes={p:hashfile(inside(store.root,p)) for p in plan['inputs']}
    return argv,cwd,artifacts,hashes,rel

def run(store,experiment_id, execute=False, run_id=None):
    plan=store.get(experiment_id,'ExperimentPlan')
    if run_id:
        prior=store.get(run_id,'RunRecord')
        require(prior['experiment_id']==experiment_id,'run_id belongs to different experiment')
        return {'executed':False,'existing_run':prior,'message':'Existing run never automatically rerun; create a new run for an explicit retry'}
    rid=new_id('RunRecord'); argv,cwd,paths,hashes,rel=prepare(store,plan,rid)
    preview={'executed':False,'run_id':rid,'command':argv,'cwd':str(cwd),'budget':plan['budget'],
             'requested':plan['requested'],'artifacts':paths,'config_sha256':sha(dumps(plan).encode()),'input_hashes':hashes}
    if not execute: return {**preview,'stage':'dry-run','message':'No subprocess launched and no RunRecord created'}
    require(plan['authorization'].get('local_execute') is True and plan['authorization'].get('reviewed_code') is True,'Execution needs plan authorization.local_execute and reviewed_code=true plus --execute')
    for k in ('gpu_seconds','api_usd','download_mb'):
        require(plan['requested'][k]==0,'V1 cannot observe/enforce '+k+'; use provider-enforced/host-controlled execution and record results')
    require(plan['authorization'].get('resource_profile')=='local_cpu_no_network','Only reviewed local_cpu_no_network profile supported; this is an authorization assertion, not an OS sandbox')
    samples=plan['requested']['samples']
    if samples:
        require('--samples' in argv and argv[argv.index('--samples')+1]==str(samples),'Positive sample budget requires explicit --samples argument; reviewed code must honor it')
    require(all(not inside(store.root,p).exists() for p in paths),'Expected output already exists; use {run_dir} for fresh run outputs')
    require(not inside(store.root,'execution.lock').exists(),'Another writer/run owns execution.lock; inspect status and owner before recovery')
    lock=inside(store.root,'execution.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,dumps({'pid':os.getpid(),'run_id':rid,'started_at':now()}).encode()); os.close(fd)
    record={'id':rid,'experiment_id':experiment_id,'stage':plan['stage'],'status':'planned','command':argv,
            'config_sha256':preview['config_sha256'],'input_hashes':hashes,'seed':plan['seeds'][0] if plan['seeds'] else None,
            'environment':environment(),'started_at':None,'ended_at':None,'exit_code':None,
            'stdout':rel+'/stdout.log','stderr':rel+'/stderr.log','artifact_ids':[],'metrics':{},'reason':None,
            'provenance':'ResearchPilot local subprocess; reviewed code, not sandboxed'}
    proc=None; tree=None
    try:
        store.put('RunRecord',record,internal=True)
        atomic(store.root,rel+'/config.json',dumps(plan))
        record.update(status='running',started_at=now())
        store.put('RunRecord',record,internal=True)
        env=os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES='',RP_RUN_DIR=str(inside(store.root,rel)),RP_SAMPLES=str(samples),RP_SEED=str(record['seed']),PYTHONUTF8='1')
        with inside(store.root,record['stdout']).open('wb') as out, inside(store.root,record['stderr']).open('wb') as err:
            proc=subprocess.Popen(argv,cwd=cwd,stdout=out,stderr=err,env=env,start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
            tree=ProcessTree(proc)
            begin=time.monotonic(); limit=min(plan['budget']['time_seconds'],plan['requested']['time_seconds'])
            require(limit>0,'requested.time_seconds must be positive for execution')
            reason=None
            while proc.poll() is None:
                if time.monotonic()-begin>=limit: reason='wall_time_budget'; break
                if out.tell()+err.tell()>8*1024*1024: reason='log_size_limit'; break
                time.sleep(.02)
            if reason:
                tree.stop(); proc.wait(timeout=5)
                record.update(status='cancelled',reason=reason)
            else:
                proc.wait()
                record.update(status='completed' if proc.returncode==0 else 'failed',reason=None if proc.returncode==0 else 'nonzero_exit')
            record['exit_code']=proc.returncode
        if tree: tree.close(); tree=None
        record['ended_at']=now()
        if record['status']=='completed':
            require(all(hashfile(inside(store.root,p))==digest for p,digest in hashes.items()),'Inputs changed during execution; cannot attribute completed result to starting hashes')
            require(all(inside(store.root,p).is_file() for p in paths),'Process exited 0 but expected artifact missing')
            for p in paths:
                aid=new_id('Artifact')
                artifact={'id':aid,'run_id':rid,'path':p,'sha256':hashfile(inside(store.root,p)),
                          'role':'experiment_output','synthetic':bool(plan.get('synthetic',False))}
                store.put('Artifact',artifact,internal=True); record['artifact_ids'].append(aid)
                if p.endswith('.json'):
                    obj=load(inside(store.root,p))
                    if isinstance(obj,dict): record['metrics'].update(obj)
            if samples and 'samples' in record['metrics']:
                require(record['metrics']['samples']<=plan['budget']['samples'],'Reported sample budget exceeded')
        store.put('RunRecord',record,internal=True)
    except (Exception,KeyboardInterrupt) as e:
        if tree: tree.stop()
        elif proc and proc.poll() is None: proc.kill()
        if proc:
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: pass
        if store.db.execute('SELECT id FROM records WHERE id=?',(rid,)).fetchone():
            saved=store.get(rid,'RunRecord')
            if saved['status']=='running':
                record.update(status='cancelled' if isinstance(e,KeyboardInterrupt) else 'failed',reason=str(e) or 'keyboard_interrupt',ended_at=now(),exit_code=proc.returncode if proc else None)
                store.put('RunRecord',record,internal=True)
            elif saved['status']=='planned':
                record.update(status='running',started_at=now()); store.put('RunRecord',record,internal=True)
                record.update(status='failed',reason=str(e),ended_at=now()); store.put('RunRecord',record,internal=True)
        else: raise
    finally:
        if tree: tree.close()
        if lock.exists(): lock.unlink()
    store.checkpoint()
    return {'executed':True,'run':store.get(rid,'RunRecord')}

def record_external(store,manifest):
    plan=store.get(manifest.get('experiment_id',''),'ExperimentPlan')
    for field in ('command','started_at','ended_at','exit_code','artifacts','stdout','stderr','input_hashes','environment'):
        require(field in manifest,'External manifest missing '+field)
    require(manifest['artifacts'],'External result requires original artifacts')
    require(isinstance(manifest['command'],list) and all(isinstance(x,str) for x in manifest['command']),'External command must be argv strings')
    require(isinstance(manifest['environment'],dict) and isinstance(manifest['input_hashes'],dict),'External environment/input_hashes must be objects')
    from datetime import datetime
    started=datetime.fromisoformat(manifest['started_at'].replace('Z','+00:00'))
    ended=datetime.fromisoformat(manifest['ended_at'].replace('Z','+00:00'))
    require(ended>=started,'External end time precedes start')
    require(type(manifest['exit_code']) is int,'External exit_code must be integer')
    for field in ('stdout','stderr'): require(Path(manifest[field]).is_file(),'External log missing: '+field)
    for entry in manifest['artifacts']:
        require(isinstance(entry,dict) and entry.get('path') and entry.get('sha256'),'External artifact requires path and expected sha256')
        require(Path(entry['path']).is_file() and hashfile(entry['path'])==entry['sha256'],'External artifact hash mismatch')
    rid=new_id('RunRecord'); rel='runs/'+rid
    d={'id':rid,'experiment_id':plan['id'],'stage':plan['stage'],'status':'planned','command':manifest['command'],
       'config_sha256':sha(dumps(plan).encode()),'input_hashes':manifest['input_hashes'],'seed':manifest.get('seed'),
       'environment':manifest['environment'],'started_at':None,'ended_at':None,'exit_code':None,
       'stdout':rel+'/stdout.log','stderr':rel+'/stderr.log','artifact_ids':[],'metrics':manifest.get('metrics',{}),
       'reason':None,'provenance':'External user-supplied execution manifest; copied artifacts verified, execution not independently observed'}
    store.put('RunRecord',d,internal=True)
    d.update(status='running',started_at=manifest['started_at']); store.put('RunRecord',d,internal=True)
    for field in ('stdout','stderr'): atomic(store.root,d[field],Path(manifest[field]).read_bytes())
    for index,entry in enumerate(manifest['artifacts']):
        require(isinstance(entry,dict) and entry.get('path') and entry.get('sha256'),'External artifact requires path and expected sha256')
        p=Path(entry['path']); require(hashfile(p)==entry['sha256'],'External artifact hash mismatch')
        target=rel+'/external_'+str(index)+p.suffix
        atomic(store.root,target,p.read_bytes()); aid=new_id('Artifact')
        store.put('Artifact',{'id':aid,'run_id':rid,'path':target,'sha256':entry['sha256'],'role':'external_result','synthetic':bool(manifest.get('synthetic',False))},internal=True)
        d['artifact_ids'].append(aid)
    d.update(status='completed' if manifest['exit_code']==0 else 'failed',ended_at=manifest['ended_at'],exit_code=manifest['exit_code'])
    store.put('RunRecord',d,internal=True); store.checkpoint()
    return d

def recover(store,run_id):
    d=store.get(run_id,'RunRecord')
    if d['status']!='running': return {'changed':False,'run':d}
    lock=inside(store.root,'execution.lock')
    if lock.exists():
        owner=load(lock)
        try: os.kill(owner['pid'],0); alive=True
        except (ProcessLookupError,OSError): alive=False
        require(not alive,'Owner process still exists; cannot cancel another active run')
    d.update(status='cancelled',reason='orphaned_interrupted_run; no automatic rerun',ended_at=now())
    store.put('RunRecord',d,internal=True)
    if lock.exists(): lock.unlink()
    return {'changed':True,'run':d}
