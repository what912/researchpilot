"""Non-executing imports, safe lexical queries, static repository snapshots, bounded public APIs."""
import ast
import importlib.util
import importlib
import ipaddress
import json
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from rp_contracts import RPError, require
from rp_store import atomic, dumps, hashfile, inside, load, new_id, now, sha

def tokenize(s):
    # Individual Han characters plus Latin words. This is lexical, not embedding search.
    return re.findall(r'[\u3400-\u9fff]|[a-z0-9_]+',s.lower())

def pdf_backend():
    errors=[]
    for m in ('pypdf','pdfplumber'):
        try:
            importlib.import_module(m)
            return m,errors
        except (ImportError,OSError) as e: errors.append(m+': '+str(e))
    return None,errors

def doctor(store=None, host=None):
    caps={}
    def add(k,state,evidence): caps[k]={'status':state,'evidence':evidence}
    add('file_read','available','Python pathlib active')
    if store:
        atomic(store.root,'evidence/write_probe.txt','write probe\n')
        add('file_write','available',str(store.root/'evidence/write_probe.txt'))
    else: add('file_write','not_checked','No project supplied')
    pdf,pdf_errors=pdf_backend()
    add('pdf_text','available' if pdf else 'unavailable',pdf or 'Install optional PDF dependency in a venv. '+ '; '.join(pdf_errors))
    add('python','available',sys.version.split()[0]+' '+sys.executable)
    add('git','available' if shutil.which('git') else 'unavailable',shutil.which('git') or 'Not on PATH')
    add('code_search','available','Python static scan; rg='+str(bool(shutil.which('rg'))))
    add('local_cpu_execution','available','subprocess; reviewed trusted commands only; not an OS sandbox')
    for k in ('page_read','ocr','public_web_search','paper_metadata','fulltext_access','repository_download',
              'subagents','gpu','training_framework','paid_api','network_policy','upload_policy'):
        add(k,'not_checked','Must be checked by host or explicit probe; no secret environment enumeration')
    add('vector_search','unavailable','V1 uses lexical FTS5 / bounded substring fallback')
    if host:
        for key,item in host.items():
            require(key in caps and isinstance(item,dict) and item.get('status') in ('available','unavailable','not_checked') and isinstance(item.get('evidence'),str),'Invalid host capability override')
            caps[key]=item
    data={'checked_at':now(),'platform':platform.platform(),'capabilities':caps}
    if store: atomic(store.root,'capabilities.json',dumps(data)+'\n')
    return data

def extract(path):
    suffix=path.suffix.lower()
    if suffix in ('.txt','.md','.markdown'):
        return [(None,path.read_text(encoding='utf-8-sig'))],[]
    require(suffix=='.pdf','Supported text formats: TXT, Markdown, text PDF, Source JSON')
    backend,errors=pdf_backend()
    if backend=='pypdf':
        from pypdf import PdfReader
        reader=PdfReader(path)
        pages=[]; warnings=[]
        for i,p in enumerate(reader.pages,1):
            try: pages.append((i,p.extract_text() or ''))
            except Exception as e: warnings.append({'page':i,'error':str(e)})
    elif backend=='pdfplumber':
        import pdfplumber
        pages=[]; warnings=[]
        with pdfplumber.open(path) as pdf:
            for i,p in enumerate(pdf.pages,1):
                try: pages.append((i,p.extract_text() or ''))
                except Exception as e: warnings.append({'page':i,'error':str(e)})
    else: raise RPError('PDF extractor unavailable; use text, working bundled Python, or optional pypdf in a venv. '+ '; '.join(errors))
    if not any(t.strip() for _,t in pages): warnings.append({'error':'No text extracted; scanned PDF requires host page reading/OCR'})
    return pages,warnings

def ingest(store, path, scope='partial_text', title=None):
    p=Path(path).resolve(); require(p.is_file(),'Input not found: '+str(p))
    require(p.stat().st_size <= 30*1024*1024,'Input exceeds V1 30 MiB import limit')
    raw=p.read_bytes(); digest=sha(raw); sid='src_'+digest[:24]
    existing=store.db.execute('SELECT id FROM records WHERE id=? AND project_id=?',(sid,store.project_id)).fetchone()
    if existing: return {'source_id':sid,'duplicate':True,'source':store.get(sid,'Source')}
    metadata={}; warnings=[]
    if p.suffix.lower()=='.json':
        metadata=load(p)
        require(isinstance(metadata,dict),'Source JSON must be an object')
        require(metadata.get('title'),'Source JSON needs title')
        scope=metadata.get('reading_scope','metadata_only')
        text=metadata.get('text','')
        require(isinstance(text,str),'Source.text must be string')
        if scope=='metadata_only': require(not text,'metadata_only Source cannot contain paper text')
        pages=[(None,text)]
    else: pages,warnings=extract(p)
    original='papers/'+sid+'/original'+p.suffix.lower()
    atomic(store.root,original,raw)
    fulltext='\n\n'.join(t for _,t in pages)
    if not fulltext.strip(): scope='metadata_only'
    source={'id':sid,'title':title or metadata.get('title') or p.stem,
            'authors':metadata.get('authors'),'year':metadata.get('year'),'url':metadata.get('url'),
            'doi':metadata.get('doi'),'arxiv_id':metadata.get('arxiv_id'),
            'source_type':metadata.get('source_type', 'local_pdf' if p.suffix.lower()=='.pdf' else 'local_text'),
            'reading_scope':scope,'sha256':digest,'acquired_at':now(),
            'unread_elements':metadata.get('unread_elements',['figures','formula_layout','supplement'] if p.suffix.lower()=='.pdf' else []),
            'original_path':original,'version':metadata.get('version'),
            'related_source_ids':metadata.get('related_source_ids',[]),'extraction_warnings':warnings,
            'origin_path':str(p),'synthetic':metadata.get('synthetic',False)}
    store.put('Source',source)
    count=0
    with store.db:
        for page,text in pages:
            paragraphs=re.split(r'\n\s*\n',text)
            for para,block in enumerate(paragraphs,1):
                for offset in range(0,len(block),1500):
                    fragment=block[offset:offset+1500].strip()
                    if not fragment: continue
                    locator=('page '+str(page)+', ' if page else '')+f'paragraph {para}, chars {offset}-{offset+len(fragment)}'
                    cid=sid+'_c'+str(count)
                    tokens=' '.join(tokenize(fragment))
                    store.db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(cid,sid,store.project_id,locator,fragment,tokens))
                    if store.fts: store.db.execute('INSERT INTO chunk_fts VALUES(?,?)',(cid,tokens))
                    count+=1
        store.event('ingest',{'source_id':sid,'chunks':count,'scope':scope})
    return {'source_id':sid,'duplicate':False,'chunks':count,'source':source}

def search(store, query, limit=10):
    require(isinstance(limit,int) and 1<=limit<=100,'limit must be 1..100')
    terms=tokenize(query)[:40]
    if not terms: return {'backend':'fts5' if store.fts else 'substring_fallback','results':[]}
    if store.fts:
        expression=' AND '.join('"'+t.replace('"','""')+'"' for t in terms)
        rows=store.db.execute('SELECT c.*,bm25(chunk_fts) AS rank FROM chunk_fts JOIN chunks c ON c.id=chunk_fts.id WHERE chunk_fts MATCH ? AND c.project_id=? ORDER BY rank LIMIT ?',(expression,store.project_id,limit)).fetchall()
    else:
        rows=store.db.execute('SELECT *,0 AS rank FROM chunks WHERE project_id=? AND '+ ' AND '.join('instr(tokens,?)>0' for _ in terms)+' LIMIT ?',(store.project_id,*terms,limit)).fetchall()
    return {'backend':'fts5_character_latin' if store.fts else 'substring_fallback',
            'results':[{'source_id':r['source_id'],'chunk_id':r['id'],'locator':r['locator'],'text':r['text'],'rank':r['rank']} for r in rows]}

def repo_map(store, root):
    root=Path(root).resolve(); require(root.is_dir(),'Repository not found')
    def git(*args):
        r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
        return r.stdout.strip() if r.returncode==0 else None
    commit=git('rev-parse','HEAD') if shutil.which('git') else None
    status=git('status','--porcelain') if commit else None
    files=[]; entries={}; instructions=[]; licenses=[]; suspicious=[]; skipped=[]
    ignored={'.git','.venv','venv','node_modules','__pycache__','.cache'}
    for p in sorted(root.rglob('*')):
        if any(part in ignored for part in p.relative_to(root).parts) or not p.is_file(): continue
        if p.is_symlink() or not p.resolve().is_relative_to(root): skipped.append(str(p)); continue
        if len(files)>=2000 or p.stat().st_size>1024*1024: skipped.append(str(p.relative_to(root))); continue
        rel=p.relative_to(root).as_posix(); info={'path':rel,'sha256':hashfile(p),'bytes':p.stat().st_size,'symbols':[]}
        text=''
        try: text=p.read_text(encoding='utf-8')
        except (UnicodeError,OSError): pass
        if p.suffix=='.py' and text:
            try:
                tree=ast.parse(text)
                info['symbols']=[{'name':n.name,'line':n.lineno,'end_line':n.end_lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
            except SyntaxError: info['parse_error']='Python syntax error; not executed'
        for label,pattern in {'train':r'train|fit','inference':r'infer|predict|generate','evaluation':r'eval|metric|score','data':r'data|preprocess','config':r'config|requirements|pyproject|environment','randomness':r'seed|random','loss':r'loss'}.items():
            if re.search(pattern,rel,re.I): entries.setdefault(label,[]).append(rel)
        if p.name=='AGENTS.md': instructions.append(rel)
        if p.name.lower().startswith(('license','copying')): licenses.append(rel)
        if re.search(r'curl.+\|.+sh|os\.system|subprocess|eval\(|pickle\.load|ignore (all |previous )?instructions|读取密钥',text,re.I): suspicious.append(rel)
        files.append(info)
    record={'id':new_id('RepoMap'),'root':str(root),'url':git('remote','get-url','origin') if commit else None,
            'commit':commit,'dirty':bool(status) if status is not None else None,'files':files,'entries':entries,
            'licenses':licenses,'instructions':instructions,'suspicious_entries':suspicious,
            'reading_scope':'Static file/AST inventory only; no executed validation. Skipped: '+dumps(skipped),
            'snapshot_sha256':sha(dumps(files).encode())}
    store.put('RepoMap',record)
    atomic(store.root,'evidence/'+record['id']+'.json',dumps(record)+'\n')
    return record

ALLOWED_HOSTS={'api.crossref.org','export.arxiv.org','arxiv.org'}
def check_url(url):
    u=urllib.parse.urlparse(url)
    require(u.scheme=='https' and u.hostname in ALLOWED_HOSTS and not u.username and not u.password and u.port in (None,443),'Only allowlisted public HTTPS paper endpoints supported')
    for answer in socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM):
        require(ipaddress.ip_address(answer[4][0]).is_global,'Nonpublic address rejected')

class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(store,url, max_bytes=10*1024*1024, timeout=12):
    check_url(url)
    key=sha(url.encode()); rel='evidence/cache/'+key+'.bin'; meta='evidence/cache/'+key+'.json'
    cached=inside(store.root,rel); mp=inside(store.root,meta)
    if cached.exists() and mp.exists():
        m=load(mp)
        if time.time()-m['cached_epoch']<86400 and hashfile(cached)==m['sha256']:
            return cached.read_bytes(),{**m,'cache_hit':True}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),CheckedRedirect())
    error=None
    for attempt in range(2):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'ResearchPilot/1.0 (public research metadata)'})
            with opener.open(request,timeout=timeout) as response:
                raw=response.read(max_bytes+1)
                require(len(raw)<=max_bytes,'Download exceeds limit')
                m={'url':url,'retrieved_at':now(),'cached_epoch':time.time(),'sha256':sha(raw),'cache_hit':False,'bytes':len(raw)}
                atomic(store.root,rel,raw); atomic(store.root,meta,dumps(m))
                return raw,m
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            error=e
            if attempt==0: time.sleep(.5)
    raise RPError('Network request failed: '+str(error))

def remote_search(store, query, purpose='literature', rows=5):
    require(1<=rows<=20,'rows must be 1..20')
    url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query':query,'rows':rows})
    log={'id':new_id('SearchLog'),'query':query,'searched_at':now(),'provider':'Crossref',
         'purpose':purpose,'criteria':{'inclusion':'review candidates manually','exclusion':'not yet decided'},
         'time_range':{'start':None,'end':None,'date_semantics':'metadata query; no time filter'},
         'candidates':[],'coverage_limits':['Crossref metadata, not fulltext; not exhaustive'], 'status':'failed'}
    try:
        raw,meta=fetch(store,url); items=json.loads(raw)['message']['items']
        for item in items:
            parts=item.get('published',{}).get('date-parts',[[]])[0]
            log['candidates'].append({'title':next(iter(item.get('title',[])),None),
                'authors':[(' '.join([a.get('given',''),a.get('family','')])).strip() for a in item.get('author',[]) ] or None,
                'year':parts[0] if parts else None,'doi':item.get('DOI'),'url':item.get('URL'),
                'reading_scope':'metadata_only','disposition':'pending','fulltext':'not_checked'})
        log.update(status='completed',request=meta)
    except (RPError,ValueError,KeyError) as e: log['error']=str(e)
    store.put('SearchLog',log)
    return log
