"""Explicit V1 contracts. Unknown metadata is null; unknown scientific detail is 'unknown'."""
import math
import re

VERSION = 2
MODES = ('read', 'survey', 'ideate', 'reproduce', 'experiment', 'analyze', 'review', 'resume', 'pipeline')
KINDS = {
    'Source': {'title': str, 'authors': (list, type(None)), 'year': (int, type(None)),
               'url': (str, type(None)), 'source_type': str, 'reading_scope': str,
               'sha256': (str, type(None)), 'acquired_at': str, 'unread_elements': list},
    'PaperCard': {'source_id': str, 'problem': str, 'closest_methods': list, 'method': dict,
                  'protocol': dict, 'results': list, 'author_limitations': list,
                  'inferred_limitations': list, 'validity': str, 'reproduction': dict,
                  'next_action': str, 'claim_ids': list},
    'Claim': {'text': str, 'category': str, 'confidence': str, 'confidence_basis': str,
              'references': list, 'run_ids': list, 'attribution': str},
    'IdeaCard': {'title': str, 'problem': str, 'motivation': str, 'closest_source_ids': list,
                 'similarities': list, 'differences': list, 'mechanism': str, 'method': dict,
                 'requirements': dict, 'minimal_test': str, 'confounders': list,
                 'fallback': str, 'contribution_type': str, 'validity_scope': str,
                 'novelty_status': str, 'countersearch_ids': list, 'ranking': dict},
    'Hypothesis': {'idea_id': str, 'statement': str, 'assumptions': list,
                   'falsification_rule': str, 'failure_reasons': list},
    'Decision': {'decision': str, 'reason': str, 'evidence_ids': list,
                 'next_action': str, 'alternatives': list, 'outcome': str},
    'ExperimentPlan': {'hypothesis_id': str, 'question': str, 'expected_evidence': str,
                       'falsification_rule': str, 'dataset': dict, 'baselines': list,
                       'ablations': list, 'model': dict, 'hyperparameters': dict,
                       'metrics': dict, 'seeds': list, 'independent_unit': str,
                       'statistics': dict, 'budget': dict, 'requested': dict,
                       'command': list, 'cwd': str, 'inputs': list, 'artifacts': list,
                       'stage': str, 'sequence': list, 'go_no_go': str,
                       'stop_conditions': list, 'authorization': dict},
    'RunRecord': {'experiment_id': str, 'stage': str, 'status': str, 'command': list,
                  'config_sha256': str, 'input_hashes': dict, 'seed': (int, type(None)),
                  'environment': dict, 'started_at': (str, type(None)),
                  'ended_at': (str, type(None)), 'exit_code': (int, type(None)),
                  'stdout': (str, type(None)), 'stderr': (str, type(None)),
                  'artifact_ids': list, 'metrics': dict, 'reason': (str, type(None)),
                  'provenance': str},
    'Artifact': {'run_id': (str, type(None)), 'path': str, 'sha256': str, 'role': str,
                 'synthetic': bool},
    'ProjectProfile': {'question': str, 'inputs': list, 'domain': str, 'deadline': (str, type(None)),
                       'compute': dict, 'budget': dict, 'existing_results': list,
                       'user_requirements': list, 'observations': list, 'assumptions': list,
                       'authorization': dict, 'preferences': dict, 'mode': str, 'depth': str},
    'OpenQuestion': {'question': str, 'evidence_ids': list, 'next_action': str},
    'SearchLog': {'query': str, 'searched_at': str, 'provider': str, 'purpose': str,
                  'criteria': dict, 'time_range': dict, 'candidates': list,
                  'coverage_limits': list, 'status': str},
    'RepoMap': {'root': str, 'url': (str, type(None)), 'commit': (str, type(None)),
                'dirty': (bool, type(None)), 'files': list, 'entries': dict,
                'licenses': list, 'instructions': list, 'suspicious_entries': list,
                'reading_scope': str, 'snapshot_sha256': str},
    'CodeMapping': {'source_id': str, 'repo_id': str, 'paper_locator': str,
                    'code_path': str, 'start_line': int, 'end_line': int,
                    'symbol': str, 'implementation_type': str, 'status': str,
                    'discrepancy': str, 'file_sha256': str},
    'Review': {'claim_ids': list, 'findings': list, 'unknowns': list,
               'review_mode': str, 'artifact_paths': list},
    'Delegation': {'role': str, 'goal': str, 'materials': list, 'output_schema': dict,
                   'write_scope': list, 'budget': dict, 'done_when': str,
                   'tool': str, 'status': str, 'result_paths': list, 'conflicts': list},
}
PREFIX = {'Source': 'src', 'PaperCard': 'paper', 'Claim': 'claim', 'IdeaCard': 'idea',
          'Hypothesis': 'hyp', 'Decision': 'dec', 'ExperimentPlan': 'exp',
          'RunRecord': 'run', 'Artifact': 'art', 'ProjectProfile': 'project',
          'OpenQuestion': 'question', 'SearchLog': 'search', 'RepoMap': 'repo',
          'CodeMapping': 'map', 'Review': 'review', 'Delegation': 'task'}

class RPError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise RPError(message)

def finite_tree(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite number; use null for missing data')
    elif isinstance(value, dict):
        for v in value.values(): finite_tree(v)
    elif isinstance(value, list):
        for v in value: finite_tree(v)

def validate(kind, d):
    require(kind in KINDS, 'Unknown kind: ' + kind)
    require(isinstance(d, dict), kind + ' must be an object')
    require(isinstance(d.get('id'), str) and re.fullmatch(r'[a-z][a-z0-9_-]{1,100}', d['id']), 'Invalid/missing id')
    for key, typ in KINDS[kind].items():
        require(key in d, f'{kind}.{key} required; supply null/unknown only where supported')
        require(isinstance(d[key], typ) and not (isinstance(d[key], bool) and typ == int), f'{kind}.{key} wrong type')
        if typ == str: require(bool(d[key].strip()), f'{kind}.{key} cannot be empty')
    finite_tree(d)
    if kind == 'Source':
        require(d['reading_scope'] in ('metadata_only', 'abstract_only', 'partial_text', 'full_text'), 'Invalid reading_scope')
        require(d['year'] is None or 1000 <= d['year'] <= 9999, 'Invalid year')
        require(d['authors'] is None or all(isinstance(a, str) for a in d['authors']), 'authors must be names or null')
    if kind == 'ProjectProfile':
        require(d['mode'] in MODES and d['depth'] in ('quick','standard','deep'), 'Invalid mode/depth')
    if kind == 'Claim':
        require(d['category'] in ('source_fact','inference','hypothesis','measured_result','unknown'), 'Invalid claim category')
        require(d['confidence'] in ('high','medium','low'), 'Invalid confidence')
        for ref in d['references']:
            require(isinstance(ref, dict) and ref.get('source_id') and ref.get('locator'), 'Reference requires source_id and actual locator')
        if d['category'] == 'source_fact': require(d['references'], 'source_fact needs located source evidence')
        if d['category'] == 'measured_result': require(d['run_ids'], 'measured_result needs run_ids')
    if kind == 'IdeaCard':
        require(d['novelty_status'] in ('unchecked','insufficient','differentiated','overlap','withdrawn'), 'Invalid novelty_status')
        if d['novelty_status'] == 'differentiated':
            require(d['closest_source_ids'] and d['countersearch_ids'] and d['differences'], 'Differentiated idea needs closest work, countersearch and differences')
    if kind == 'ExperimentPlan':
        require(d['stage'] in ('smoke','pilot','main','ablation','robustness'), 'Invalid experiment stage')
        require(d['command'] and all(isinstance(x,str) for x in d['command']), 'command must be argv strings')
        for k in ('time_seconds','gpu_seconds','api_usd','samples','download_mb'):
            require(isinstance(d['budget'].get(k), (int,float)) and not isinstance(d['budget'][k],bool) and d['budget'][k] >= 0, 'budget.'+k+' must be nonnegative')
            require(isinstance(d['requested'].get(k),(int,float)) and d['requested'][k] >= 0, 'requested.'+k+' required')
            require(d['requested'][k] <= d['budget'][k], 'Requested exceeds budget: '+k)
        require(d['budget']['time_seconds'] > 0, 'Positive wall time required')
        for k in ('version','source','license_status','split','preprocessing','deduplication','contamination_check'):
            require(k in d['dataset'], 'dataset.'+k+' required')
        for k in ('primary','secondary','calculation','failure_rate','resource_cost'):
            require(k in d['metrics'], 'metrics.'+k+' required')
        require(d['artifacts'], 'At least one expected artifact required')
        require(all(isinstance(p,str) for p in d['inputs'] + d['artifacts']), 'input/artifact paths must be strings')
    if kind == 'RunRecord':
        require(d['status'] in ('planned','running','completed','failed','cancelled'), 'Invalid run status')
        if d['status'] == 'completed':
            require(d['exit_code'] == 0 and d['started_at'] and d['ended_at'] and d['artifact_ids'], 'Completed needs successful execution and artifacts')
    if kind == 'Artifact': require(re.fullmatch('[a-f0-9]{64}',d['sha256']), 'Artifact needs SHA256')
    if kind == 'CodeMapping': require(1 <= d['start_line'] <= d['end_line'], 'Invalid code line range')
    return d

def references(kind, d):
    refs = []
    single = {'PaperCard': [('source_id','Source')], 'Hypothesis': [('idea_id','IdeaCard')],
              'ExperimentPlan': [('hypothesis_id','Hypothesis')], 'RunRecord': [('experiment_id','ExperimentPlan')],
              'Artifact': [('run_id','RunRecord')], 'CodeMapping': [('source_id','Source'),('repo_id','RepoMap')]}
    many = {'Claim': [('run_ids','RunRecord')], 'PaperCard': [('claim_ids','Claim')],
            'IdeaCard': [('closest_source_ids','Source'),('countersearch_ids','SearchLog')],
            'RunRecord': [('artifact_ids','Artifact')], 'Review': [('claim_ids','Claim')]}
    for field, target in single.get(kind,[]):
        if d[field] is not None: refs.append((d[field],target))
    for field, target in many.get(kind,[]): refs.extend((v,target) for v in d[field])
    if kind == 'Claim': refs.extend((v['source_id'],'Source') for v in d['references'])
    if kind in ('Decision','OpenQuestion'): refs.extend((v,None) for v in d['evidence_ids'])
    if d.get('supersedes'): refs.append((d['supersedes'],kind))
    return refs
