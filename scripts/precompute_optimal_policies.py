#!/usr/bin/env python

''' Script for precomputing the optimal (shortest path) policy at each viewpoint. '''

from env import R2RBatch
import json
import os

r2r = R2RBatch(None, batch_size=1)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if os.path.isdir(path):
            pass
        else: raise

for scan in r2r.paths:
    for goal in r2r.paths[scan]:
        mkdir_p('./data/v1/scans/{}/policies'.format(scan))
        with open('./data/v1/scans/{}/policies/{}.json'.format(scan, goal), 'w') as f:
            f.write(json.dumps(r2r.paths[scan][goal]))

