"""Run a bounded offline SYNTHETIC ResearchPilot case, never real research evidence."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CLI = BASE / 'researchpilot/scripts/researchpilot.py'
sys.path.insert(0, str(BASE / 'tests'))
from fixtures import setup, idea, hypothesis, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path, help='New or empty directory; existing projects are never deleted')
    args = parser.parse_args()
    root = args.project.resolve()
    if root.exists() and any(root.iterdir()):
        parser.error('Project directory is not empty; use resume or choose a new directory.')
    logs = []

    def call(*argv):
        cmd = [sys.executable, '-B', str(CLI), *map(str, argv), '--json']
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONUTF8': '1'}, timeout=45)
        logs.append({'argv': cmd, 'exit_code': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
        if proc.returncode:
            raise RuntimeError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)

    def put(kind, record):
        path = root / 'evidence' / (record['id'] + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        return call('memory', '--project', root, 'put', '--kind', kind, '--file', path)

    try:
        call('init', '--project', root, '--question', 'SYNTHETIC offline workflow demonstration, not scientific validation')
        setup(root)
        source = call('ingest', '--project', root, root / 'paper.json')
        search = call('search', '--project', root, 'sequential gate')
        assert search['results'], 'Expected fixture evidence not found'
        put('IdeaCard', idea(closest=[source['source_id']], status='overlap'))
        put('Hypothesis', hypothesis())
        authored_plan = plan()
        path = root / 'evidence/exp_demo.json'
        path.write_text(json.dumps(authored_plan, ensure_ascii=False, indent=2), encoding='utf-8')
        call('plan', '--project', root, path)
        preview = call('run', '--project', root, authored_plan['id'])
        assert preview['executed'] is False
        completed = call('run', '--project', root, authored_plan['id'], '--execute')['run']
        assert completed['status'] == 'completed'
        rid = completed['id']
        analysis = call('analyze', '--project', root, root / 'runs' / rid / 'rows.csv',
                        '--metric', 'score', '--unit', 'seed', '--synthetic', '--run-id', rid)
        decision = {'id': 'dec_synthetic_negative',
                    'decision': 'Keep synthetic negative outcome; no real scientific improvement claimed',
                    'reason': 'Gate deliberately flips every fourth label; oracle reads labels and is not a fair research baseline.',
                    'evidence_ids': [rid, 'hyp_demo', analysis['artifact_id']],
                    'next_action': 'Use workflow on a real paper with located evidence, protected split and appropriate independent repeats.',
                    'alternatives': ['Treat toy run as software smoke only'], 'outcome': 'synthetic_software_chain_verified'}
        put('Decision', decision)
        integrity = call('validate', '--project', root)
        exported = call('export', '--project', root)
        resumed = call('resume', '--project', root)
        again = call('run', '--project', root, authored_plan['id'], '--execute', '--run-id', rid)
        assert again['executed'] is False
        assert any(d['id'] == decision['id'] for d in resumed['recent_decisions'])
        summary = {'synthetic': True, 'research_claim': False, 'status': completed['status'],
                   'run_id': rid, 'project': str(root), 'integrity_valid': integrity['valid'],
                   'resume_negative_decision': True, 'completed_run_not_reexecuted': True,
                   'one_seed_no_significance_claim': True, 'metrics': completed['metrics'],
                   'export_paths': exported['paths']}
        (root / 'reports/demo-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        if root.exists():
            folder = root / 'reports'
            folder.mkdir(exist_ok=True)
            (folder / 'demo-commands.json').write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

