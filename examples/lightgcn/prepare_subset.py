"""Freeze a local real LastFM subset from user-supplied official files; no network.
Source licensing must be checked separately. No test-dependent universe selection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True, help='Contains data1.txt and test1.txt')
    parser.add_argument('--output', type=Path, required=True, help='New/empty local data folder')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Output folder must be new/empty; existing data are not overwritten.')
    files = [args.source_dir / 'data1.txt', args.source_dir / 'test1.txt']
    if not all(p.is_file() for p in files):
        parser.error('Missing data1.txt or test1.txt')
    train_raw, test_raw = [np.loadtxt(p, dtype=np.int64, ndmin=2, usecols=(0, 1)) for p in files]
    train, test = np.unique(train_raw, axis=0), np.unique(test_raw, axis=0)
    items, counts = np.unique(train[:,1], return_counts=True)
    chosen_items = items[np.lexsort((items, -counts))[:180]]
    candidate = train[np.isin(train[:,1], chosen_items)]
    users, degree = np.unique(candidate[:,0], return_counts=True)
    chosen_users = users[degree >= 5][:60]
    assert len(chosen_users) == 60 and len(chosen_items) == 180
    candidate = candidate[np.isin(candidate[:,0], chosen_users)]
    umap = {int(v):i for i,v in enumerate(chosen_users)}
    imap = {int(v):i for i,v in enumerate(chosen_items)}
    original_train = sorted({(umap[int(u)], imap[int(i)]) for u,i in candidate})
    original_test = sorted({(umap[int(u)], imap[int(i)]) for u,i in test if int(u) in umap and int(i) in imap})
    assert not set(original_train) & set(original_test)
    fit, valid = [], []
    rng = np.random.default_rng(20261014)
    for u in range(60):
        choices = [i for x,i in original_train if x == u]
        held = int(rng.choice(choices))
        valid.append([u, held])
        fit.extend([u,i] for i in choices if i != held)
    assert len(fit) <= 5000 and original_test
    data = {'n_users':60, 'n_items':180, 'train':fit, 'validation':valid, 'test':[list(p) for p in original_test],
            'original_user_ids':[int(v) for v in chosen_users], 'original_item_ids':[int(v) for v in chosen_items],
            'synthetic':False, 'source_kind':'real_public_lastfm_subset',
            'selection':'180 most frequent training items; first 60 qualified numeric training users; no test-based selection',
            'validation_description':'One held-out original train interaction/user; splitseed20261014',
            'test_description':'Source original test restricted to frozen train-selected universe; no tuning on test'}
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / 'lastfm-subset.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    manifest = {'source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                'subset_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'source_commit_expected':'947ca2b3b1d2d3545b114145710cb06c4e57b3d2',
                'expected_source_hashes':{'data1.txt':'c82af3228cbbda2f55a39244de09ed93292894f1d0d9f1908ebb57e27598fded',
                                          'test1.txt':'de4417c0e6123284ce59a0934bcf5288ec1ec8774a18a1eef453c9952dfa48f9'},
                'fit_interactions':len(fit),'validation_interactions':len(valid),'test_interactions':len(original_test),
                'test_users':len({u for u,i in original_test}),
                'license_status':'Not verified by this script; input files are supplied by user, not redistributed',
                'external_validity':'Restricted subgraph, not original paper three-benchmark replication'}
    manifest['source_matches_published_case'] = manifest['source_files'] == manifest['expected_source_hashes']
    (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

