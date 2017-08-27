import os
import json

import numpy as np
import pandas as pd

# need to figure out new root_dir mapping
root_dir = "~/Desktop/Projects/Project Data/congress113"
dirs     = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

print dirs

bills = pd.DataFrame(columns = ['id', 'sponsor', 'status', 'status_at', '# cosponsors', 'cosponsors'])
reps  = [ ]

for dir in dirs:
    f = "%s\%s\data.json" % (root_dir, dir)
    with open(f) as data_file:
        data = json.load(data_file)

    # add all involved names to lsit    
    cosponsors = [cosponsor['name'] for cosponsor in data['cosponsors']]
    reps = reps + cosponsors + [data['sponsor']['name']]


    bills.loc[bills.shape[0]] = [data['bill_id'],
                                 data['sponsor']['name'],
                                 data['status'],
                                 data['status_at'],
                                 len(data['cosponsors']),
                                 '|'.join(cosponsors)
                                ]

print bills
print len(list(set(reps)))

bills.to_csv('output.csv')

pd.DataFrame(list(set(reps))).to_csv('output2.csv')