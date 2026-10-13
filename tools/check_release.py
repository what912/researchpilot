"""Check distributable resource reachability/format and accidental private payloads, offline."""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
files = [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts
         and '__pycache__' not in p.parts and '.venv' not in p.parts]
local_links = 0
for p in files:
    relative = p.relative_to(ROOT)
    if p.suffix.lower() in {'.pdf', '.sqlite3', '.db', '.pem', '.key', '.pyc'} or p.name.startswith('.env'):
        errors.append('Unexpected private/runtime file: '+str(relative))
    if p.suffix == '.json':
        try: json.loads(p.read_text(encoding='utf-8-sig'))
        except Exception as exc: errors.append(str(relative)+': invalidJSON '+str(exc))
    if p.suffix == '.py':
        try: ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(relative))
        except SyntaxError as exc: errors.append(str(relative)+': '+str(exc))
    if p.suffix.lower() not in {'.md', '.py', '.json', '.yaml', '.txt'}:
        continue
    text = p.read_text(encoding='utf-8-sig')
    if re.search(r'(?:C:[\\/]+Users[\\/]+|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)', text):
        errors.append('Unexpected personalpath/token/privatekey in '+str(relative))
    if p.suffix == '.md':
        # Only normal Markdown local links; code/path examples are not executable shell.
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-z]+://', target):
                continue
            local_links += 1
            destination = (p.parent / target).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                errors.append('Broken/outside local link in '+str(relative)+': '+target)
skill = ROOT / 'researchpilot'
skillfiles = [p for p in files if p.is_relative_to(skill)]
if len(skillfiles) != 30:
    errors.append('Expected30 frozenSkillresources, found'+str(len(skillfiles)))
front = (skill/'SKILL.md').read_text(encoding='utf-8')
if not front.startswith('---\n') or 'name: researchpilot' not in front.split('---',2)[1]:
    errors.append('Skill frontmatter/name mismatch')
result = {'valid': not errors, 'files': len(files), 'skill_resources':len(skillfiles),
          'local_links':local_links, 'errors':errors,
          'skill_resource_sha256':{str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest() for p in skillfiles}}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if not errors else 1)

