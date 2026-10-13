"""Project-local transactional authority, versioned records, recoverable exports."""
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from rp_contracts import VERSION, KINDS, PREFIX, RPError, require, validate, references

def now(): return datetime.now(timezone.utc).isoformat()
def dumps(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False)
def sha(data): return hashlib.sha256(data).hexdigest()
def hashfile(p): return sha(Path(p).read_bytes())
def new_id(kind): return PREFIX[kind]+'_'+uuid.uuid4().hex[:16]
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def inside(root, relative):
    root = Path(root).resolve()
    raw = Path(relative)
    require(not raw.is_absolute() and '..' not in raw.parts and ':' not in str(raw), 'Path must be relative inside project: '+str(relative))
    p = (root/raw).resolve()
    require(p.is_relative_to(root) and p != root, 'Path escapes project: '+str(relative))
    return p

def atomic(root, relative, data):
    p = inside(root,relative)
    p.parent.mkdir(parents=True,exist_ok=True)
    # Resolve again after mkdir; a symlink parent may not redirect writes.
    p = inside(root,relative)
    temp = inside(root,str(p.relative_to(Path(root).resolve()))+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_bytes(data if isinstance(data,bytes) else data.encode('utf-8'))
        os.replace(temp,p)
    finally:
        if temp.exists(): temp.unlink()
    return str(p)

class Store:
    def __init__(self, root, create=False):
        self.root = Path(root).resolve()
        require(create or inside(self.root,'state.sqlite3').exists(), 'Not a ResearchPilot project; run init first')
        self.root.mkdir(parents=True,exist_ok=True)
        for sibling in ('state.sqlite3-wal','state.sqlite3-shm','state.sqlite3-journal'):
            inside(self.root,sibling)  # Existing sidecar symlinks must not redirect SQLite writes.
        self.db = sqlite3.connect(inside(self.root,'state.sqlite3'), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        v = self.db.execute('PRAGMA user_version').fetchone()[0]
        require(v <= VERSION, 'Database newer than this CLI')
        with self.db:
            if v == 0:
                self.db.executescript('''
                CREATE TABLE projects(id TEXT PRIMARY KEY, profile TEXT NOT NULL);
                CREATE TABLE records(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                  kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE record_refs(owner TEXT NOT NULL REFERENCES records(id),
                  target TEXT NOT NULL REFERENCES records(id), PRIMARY KEY(owner,target));
                CREATE TABLE chunks(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES records(id),
                  project_id TEXT NOT NULL REFERENCES projects(id), locator TEXT NOT NULL, text TEXT NOT NULL, tokens TEXT NOT NULL);
                CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT REFERENCES projects(id),
                  event TEXT NOT NULL, created_at TEXT NOT NULL, details TEXT NOT NULL);
                PRAGMA user_version=1;
                ''')
                v=1
            if v == 1:
                self.db.execute('ALTER TABLE records ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
                self.db.execute('CREATE TABLE record_versions(id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, changed_at TEXT NOT NULL, PRIMARY KEY(id,revision))')
                self.db.execute('INSERT INTO record_versions SELECT id,revision,payload,created_at FROM records')
                self.db.execute('PRAGMA user_version=2')
                self.db.execute('INSERT INTO events(event,created_at,details) VALUES(?,?,?)',('migration',now(),dumps({'from':1,'to':2})))
        self.fts = True
        try:
            with self.db:
                self.db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(id UNINDEXED, tokens)')
                if self.db.execute('SELECT count(*) FROM chunk_fts').fetchone()[0] != self.db.execute('SELECT count(*) FROM chunks').fetchone()[0]:
                    self.db.execute('DELETE FROM chunk_fts')
                    self.db.execute('INSERT INTO chunk_fts SELECT id,tokens FROM chunks')
        except sqlite3.OperationalError: self.fts=False
        rows=self.db.execute('SELECT id FROM projects').fetchall()
        require(len(rows)<=1,'Project database contains multiple projects')
        self.project_id=rows[0]['id'] if rows else None

    def close(self): self.db.close()
    def event(self, name, details):
        self.db.execute('INSERT INTO events(project_id,event,created_at,details) VALUES(?,?,?,?)',(self.project_id,name,now(),dumps(details)))
    def get(self, id, kind=None):
        r=self.db.execute('SELECT * FROM records WHERE id=? AND project_id=?',(id,self.project_id)).fetchone()
        require(r is not None and (kind is None or r['kind']==kind), 'Missing/wrong project record: '+id)
        return json.loads(r['payload'])
    def list(self, kind=None):
        rows=self.db.execute('SELECT * FROM records WHERE project_id=?'+(' AND kind=?' if kind else '')+' ORDER BY created_at,id', (self.project_id,kind) if kind else (self.project_id,)).fetchall()
        return [{'kind':r['kind'],**json.loads(r['payload'])} for r in rows]
    def put(self, kind, d, internal=False):
        validate(kind,d)
        require(self.project_id is not None, 'No project profile')
        require(d.get('project_id',self.project_id)==self.project_id,'Cross-project record rejected')
        d={**d,'project_id':self.project_id,'schema_version':VERSION}
        if kind in ('RunRecord','Artifact') and not internal:
            raise RPError('Use run/record to create execution records and artifacts')
        refs=references(kind,d)
        for rid,target in refs:
            x=self.get(rid,target)
            if kind=='Claim' and d['category']=='measured_result' and target=='RunRecord':
                require(x['status']=='completed','Measured claim requires completed run')
                for aid in x['artifact_ids']: self.verify_artifact(self.get(aid,'Artifact'))
            if kind=='IdeaCard' and d['novelty_status']=='differentiated' and target=='SearchLog':
                require(x['status']=='completed' and x['purpose']=='counterexample','Active completed counterexample search required')
        old=self.db.execute('SELECT * FROM records WHERE id=?',(d['id'],)).fetchone()
        require(not old or old['kind']==kind,'Record ID kind conflict')
        if old and kind not in ('RunRecord',):
            require(json.loads(old['payload'])==d,'Immutable record; use a new id with supersedes to correct it')
            return d
        if old and kind=='RunRecord':
            prior=json.loads(old['payload'])
            allowed={'planned':{'running'},'running':{'completed','failed','cancelled'},'completed':set(),'failed':set(),'cancelled':set()}
            require(d['status'] in allowed[prior['status']], 'Illegal run transition')
        revision=(old['revision']+1) if old else 1
        if kind=='ProjectProfile' and d['id']!=self.project_id:
            current=self.profile()
            require(d.get('supersedes')==current['id'],'Profile revision must supersede current profile')
        with self.db:
            self.db.execute('INSERT INTO records(id,project_id,kind,payload,created_at,revision) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision',(d['id'],self.project_id,kind,dumps(d),old['created_at'] if old else now(),revision))
            self.db.execute('DELETE FROM record_refs WHERE owner=?',(d['id'],))
            self.db.executemany('INSERT OR IGNORE INTO record_refs VALUES(?,?)',[(d['id'],v[0]) for v in refs])
            self.db.execute('INSERT INTO record_versions VALUES(?,?,?,?)',(d['id'],revision,dumps(d),now()))
            if kind=='ProjectProfile':
                self.db.execute('UPDATE projects SET profile=? WHERE id=?',(dumps(d),self.project_id))
            self.event('saved',{'id':d['id'],'kind':kind,'revision':revision})
        if kind=='ProjectProfile': atomic(self.root,'project.json',dumps(d)+'\n')
        return d
    def verify_artifact(self, d):
        p=inside(self.root,d['path'])
        require(p.is_file() and hashfile(p)==d['sha256'],'Missing/changed artifact: '+d['path'])
    def profile(self):
        require(self.project_id,'No profile')
        return json.loads(self.db.execute('SELECT profile FROM projects WHERE id=?',(self.project_id,)).fetchone()[0])
    def init_profile(self,d):
        validate('ProjectProfile',d)
        require(not self.project_id,'Project already initialized')
        self.project_id=d['id']
        with self.db: self.db.execute('INSERT INTO projects VALUES(?,?)',(d['id'],dumps(d)))
        self.put('ProjectProfile',d)
        atomic(self.root,'project.json',dumps(d)+'\n')
    def checkpoint(self):
        rec=self.list()
        superseded={x['supersedes'] for x in rec if x.get('supersedes')}
        active=[x for x in rec if x['id'] not in superseded]
        data={'project':self.profile(),'schema_version':VERSION,'generated_at':now(),
              'counts':{k:sum(x['kind']==k for x in active) for k in KINDS},
              'recent_decisions':[x for x in active if x['kind']=='Decision'][-5:],
              'ideas':[x for x in active if x['kind']=='IdeaCard'],
              'hypotheses':[x for x in active if x['kind']=='Hypothesis'],
              'open_questions':[x for x in active if x['kind']=='OpenQuestion'],
              'unfinished_runs':[x for x in active if x['kind']=='RunRecord' and x['status']!='completed'],
              'experiments':[x for x in active if x['kind']=='ExperimentPlan'],
              'claims':[x for x in active if x['kind']=='Claim'],
              'evidence_integrity':self.integrity(),
              'next_action':next((x['next_action'] for x in reversed(active) if x['kind']=='Decision'),'unknown'),
              'resume_policy':'Inspect running owner first; never rerun completed or interrupted runs automatically'}
        atomic(self.root,'checkpoint.json',dumps(data)+'\n')
        atomic(self.root,'checkpoint.md','# ResearchPilot checkpoint\n\n'+dumps(data)+'\n')
        return data
    def integrity(self):
        errors=[]
        for r in self.list():
            kind=r.pop('kind')
            try:
                validate(kind,r)
                for rid,target in references(kind,r): self.get(rid,target)
                if kind=='Artifact': self.verify_artifact(r)
                if kind=='RunRecord' and r['status']=='completed':
                    for aid in r['artifact_ids']: self.verify_artifact(self.get(aid,'Artifact'))
                if kind=='Source' and r.get('original_path'):
                    require(hashfile(inside(self.root,r['original_path']))==r['sha256'],'Source snapshot hash changed')
            except (RPError,OSError) as e: errors.append({'id':r['id'],'error':str(e)})
        errors.extend({'error':str(tuple(r))} for r in self.db.execute('PRAGMA foreign_key_check'))
        return {'valid':not errors,'errors':errors,'schema_version':VERSION,'fts5':self.fts}
