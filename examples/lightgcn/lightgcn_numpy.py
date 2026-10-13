"""Audited local CPU teaching implementation, NOT the author's benchmark reproduction.
No subprocess/network/deserialization. Frozen JSON data; analytic BPR gradients and Adam.
The --samples limit bounds unique fit edges (not optimization steps); steps/seeds are explicit.
"""
import argparse
import csv
import hashlib
import json
import os
import time
from pathlib import Path
for _key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_key] = '1'
import numpy as np


def normalized_graph(nu, ni, edges):
    adjacency = np.zeros((nu + ni, nu + ni), dtype=np.float64)
    for u, i in edges:
        adjacency[u, nu + i] = adjacency[nu + i, u] = 1.
    degree = adjacency.sum(axis=1)
    inv = np.zeros_like(degree)
    inv[degree > 0] = degree[degree > 0] ** -.5
    return inv[:, None] * adjacency * inv[None, :], degree


def propagation(s, degree, nu, method):
    eye = np.eye(len(s))
    if method == 'MF':
        return eye
    if method == 'LightGCN-last':
        return s @ s
    if method == 'LightGCN-average':
        return (eye + s + s @ s) / 3.
    if method == 'Degree-alpha':
        # Frozen before test: low-degree <=5 favors high hop; high-degree favors E0.
        alpha = np.tile([1/3, 1/3, 1/3], (len(s), 1))
        alpha[:nu] = np.where((degree[:nu] <= 5)[:, None], [.1, .2, .7], [.5, .3, .2])
        return alpha[:, 0, None] * eye + alpha[:, 1, None] * s + alpha[:, 2, None] * (s @ s)
    raise ValueError(method)


def objective_gradient(e0, p, nu, users, positive, negative, reg):
    final = p @ e0
    u, pos, neg = final[users], final[nu + positive], final[nu + negative]
    margin = np.sum(u * (pos - neg), axis=1)
    loss = np.logaddexp(0., -margin).mean()
    coeff = -np.exp(-np.logaddexp(0., margin)) / len(users)
    g = np.zeros_like(final)
    np.add.at(g, users, coeff[:, None] * (pos - neg))
    np.add.at(g, nu + positive, coeff[:, None] * u)
    np.add.at(g, nu + negative, -coeff[:, None] * u)
    grad = p.T @ g
    idx = np.concatenate([users, nu + positive, nu + negative])
    loss += reg * np.square(e0[idx]).sum() / (2 * len(users))
    np.add.at(grad, idx, reg * e0[idx] / len(users))
    return float(loss), grad


def ranking(scores, truth, blocked, k=20):
    scores = scores.copy()
    for u, i in blocked:
        scores[u, i] = -np.inf
    per_user = []
    for u in range(len(scores)):
        relevant = {i for x, i in truth if x == u}
        if not relevant:
            continue  # Explicit evaluated-user denominator, including 0-hit users.
        order = np.argsort(-scores[u], kind='stable')[:k]
        hits = np.array([i in relevant for i in order], dtype=float)
        discount = 1 / np.log2(np.arange(2, len(order) + 2))
        ideal = discount[:min(k, len(relevant))].sum()
        per_user.append({'user': u, 'recall20': float(hits.sum()/len(relevant)),
                         'ndcg20': float((hits * discount).sum()/ideal)})
    assert per_user
    return {'recall20': float(np.mean([r['recall20'] for r in per_user])),
            'ndcg20': float(np.mean([r['ndcg20'] for r in per_user])),
            'test_users': len(per_user)}, per_user


def self_checks():
    s, deg = normalized_graph(2, 2, [[0, 0], [0, 1], [1, 1]])
    assert np.allclose(s, s.T)
    assert np.isclose(s[0, 2], 1/np.sqrt(2)) and np.isclose(s[0, 3], .5)
    assert np.all(np.diag(s) == 0)
    rng = np.random.default_rng(43)
    e = rng.normal(size=(4, 3))
    poly = propagation(s, deg, 2, 'LightGCN-average')
    assert np.allclose(poly @ e, (e + s @ e + s @ (s @ e))/3)
    errors = {}
    for method in ('MF', 'LightGCN-last', 'LightGCN-average', 'Degree-alpha'):
        p = propagation(s, deg, 2, method)
        loss, grad = objective_gradient(e, p, 2, np.array([0,1]), np.array([0,1]), np.array([1,0]), .01)
        maximum = 0.
        for idx in np.ndindex(e.shape):
            ep, em = e.copy(), e.copy()
            ep[idx] += 1e-6
            em[idx] -= 1e-6
            lp = objective_gradient(ep,p,2,np.array([0,1]),np.array([0,1]),np.array([1,0]),.01)[0]
            lm = objective_gradient(em,p,2,np.array([0,1]),np.array([0,1]),np.array([1,0]),.01)[0]
            maximum = max(maximum, abs((lp-lm)/2e-6 - grad[idx]))
        assert maximum < 1e-7, (method, maximum)
        errors[method] = maximum
    score, _ = ranking(np.array([[4.,3.,2.,1.]]), [[0,2]], [[0,0]], k=2)
    assert score['recall20'] == 1. and np.isclose(score['ndcg20'], 1/np.log2(3))
    return {'normalized_toy_graph': 'passed', 'no_self_loop': 'passed',
            'iterative_vs_matrix': 'passed', 'finite_difference_gradient_errors': errors,
            'ranking_and_known_positive_mask': 'passed'}


def train(data, p, method, seed, steps, batch, dim, lr, reg):
    nu, ni = data['n_users'], data['n_items']
    edges = np.array(data['train'], dtype=np.int64)
    positives = [np.array([i for u,i in edges if u == x], dtype=np.int64) for x in range(nu)]
    negative_pools = [np.array(sorted(set(range(ni))-set(v.tolist())), dtype=np.int64) for v in positives]
    assert all(len(v) and len(n) for v,n in zip(positives,negative_pools))
    rng = np.random.default_rng(seed)
    e = rng.normal(0., .1, size=(nu+ni, dim))
    m, v = np.zeros_like(e), np.zeros_like(e)
    curves = []
    for step in range(1,steps+1):
        users = rng.integers(0,nu,batch)
        pos = np.array([rng.choice(positives[u]) for u in users])
        neg = np.array([rng.choice(negative_pools[u]) for u in users])
        loss, grad = objective_gradient(e,p,nu,users,pos,neg,reg)
        assert np.isfinite(loss) and np.isfinite(grad).all()
        m = .9*m + .1*grad
        v = .999*v + .001*grad**2
        e -= lr * (m/(1-.9**step)) / (np.sqrt(v/(1-.999**step))+1e-8)
        if step == 1 or step % 20 == 0 or step == steps:
            curves.append({'group':method, 'seed':seed, 'step':step, 'bpr_loss':loss})
    final = p @ e
    scores = final[:nu] @ final[nu:].T
    valid, _ = ranking(scores, data['validation'], data['train'])
    test, user_rows = ranking(scores, data['test'], data['train']+data['validation'])
    return {**test, 'validation_recall20':valid['recall20'], 'validation_ndcg20':valid['ndcg20'],
            'final_loss':curves[-1]['bpr_loss']}, user_rows, curves


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--samples', type=int, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--steps', type=int, default=180)
    ap.add_argument('--seeds', default='0,1,2,3,4')
    ap.add_argument('--stage', choices=['smoke','pilot'], default='pilot')
    args = ap.parse_args()
    started = time.perf_counter()
    data = json.loads(args.data.read_text(encoding='utf-8'))
    assert all(isinstance(data[key], list) and all(isinstance(pair, list) and len(pair) == 2 for pair in data[key])
               for key in ('train', 'validation', 'test')), 'Split schema must be actual pair arrays'
    assert len(data['train']) <= args.samples and args.samples <= 5000
    assert 1 <= args.steps <= 180
    seeds = [int(v) for v in args.seeds.split(',')]
    assert len(seeds) <= 5
    tr, va, te = [set(map(tuple,data[x])) for x in ('train','validation','test')]
    assert not (tr & va or tr & te or va & te)
    checks = self_checks()
    checks['split_overlap'] = {'train_validation':0,'train_test':0,'validation_test':0}
    s, degree = normalized_graph(data['n_users'],data['n_items'],data['train'])
    rows, users, curves = [], [], []
    methods = ('MF','LightGCN-average','LightGCN-last','Degree-alpha')
    # Popularity is a deterministic baseline, measured ONCE rather than fake seed replicates.
    popularity = np.tile(degree[data['n_users']:], (data['n_users'],1))
    pop, popusers = ranking(popularity,data['test'],data['train']+data['validation'])
    for seed in seeds:
        for method in methods:
            p = propagation(s,degree,data['n_users'],method)
            metrics, ur, cr = train(data,p,method,seed,args.steps,256,16,.02,1e-4)
            rows.append({'group':method,'seed':seed,'status':'completed',**metrics})
            users.extend({'group':method,'seed':seed,'degree':int(degree[r['user']]),**r} for r in ur)
            curves.extend(cr)
    means = {method:{key:float(np.mean([r[key] for r in rows if r['group']==method]))
                     for key in ('recall20','ndcg20')} for method in methods}
    result = {'synthetic':False, 'stage':args.stage,'samples':len(data['train']),
              'seeds':seeds,'steps':args.steps,'dimension':16,'learning_rate':.02,'lambda':1e-4,
              'means':means,'popularity_single_measurement':pop,'elapsed_seconds':time.perf_counter()-started,
              'data_sha256':hashlib.sha256(args.data.read_bytes()).hexdigest(),
              'scope':'Frozen LastFM 60-user/180-item subgraph; 50 test users; not original paper benchmark reproduction',
              'test_protection':'No selection/tuning on test; fixed steps; all test evaluation occurs after training',
              'gradient_check_max_error':max(checks['finite_difference_gradient_errors'].values())}
    args.output.mkdir(parents=True,exist_ok=True)
    for name,obj in [('metrics.json',result),('checks.json',checks),('config.json',vars(args))]:
        (args.output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    write_csv(args.output/'rows.csv',rows)
    write_csv(args.output/'users.csv',users)
    write_csv(args.output/'curves.csv',curves)
    # Prespecified contrasts, created as original run artifacts for verifiable analysis lineage.
    write_csv(args.output/'pair-mf-average.csv',[r for r in rows if r['group'] in ('MF','LightGCN-average')])
    write_csv(args.output/'pair-alpha-average.csv',[r for r in rows if r['group'] in ('Degree-alpha','LightGCN-average')])
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
