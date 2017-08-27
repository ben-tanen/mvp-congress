import requests
import numpy as np
import pandas as pd

# import data from excel sheet
df = pd.read_excel('data/bills.xlsx')

# getting a list of legislators
reps    = [ ]
reps_v2 = [ ] 
for bill_id in range(500,1000):
    if bill_id % 25 == 0:
        print('--> HR%s' % bill_id)
    
    url = 'https://www.govtrack.us/data/congress/114/bills/hr/hr%d/data.json' % bill_id
    res = requests.get(url)
    
    if res.status_code == 200:
        data = res.json()
        
        s_dist = "%s%s" % (data['sponsor']['state'], data['sponsor']['district'])
        if s_dist not in reps_v2:
            reps.append(data['sponsor'])
            reps_v2.append(s_dist)
            
        for c in data['cosponsors']:
            c_dist = "%s%s" % (c['state'], c['district'])
            if c_dist not in reps_v2:
                reps.append(c)
                reps_v2.append(c_dist)

reps_df = pd.DataFrame([{'district': r['district'], 'name': r['name'], 'state': r['state']} for r in reps])
     
# read-in HR bills
congress_session = 113
bills = [ ]
for bill_id in range(1,6000):
    if bill_id % 25 == 0:
        print('--> HR%s' % bill_id)
    
    url = 'https://www.govtrack.us/data/congress/%s/bills/hr/hr%d/data.json' % (congress_session, bill_id)
    res = requests.get(url)
    
    if res.status_code == 200:
        data = res.json()
        bill = {
            '_type': 'hr',
            '_id': bill_id,
            '_status': data['status'],
            '_sponsor': data['sponsor']['name'],
            '_subject': data['subjects_top_term']
        }
        
        bill[data['sponsor']['name']] = 0
        
        for cosponsor in data['cosponsors']:
            print(cosponsor)
            bill[cosponsor['name']] = 1 if cosponsor['original_cosponsor'] else 2
        
        bills.append(bill)
        
# convert data to pandas DF
print('--> building df...')
df113 = pd.DataFrame(bills)
df113['_subject'].fillna('None', inplace=True)
df113.fillna('-', inplace=True)

# export data to excel sheet
print('--> exporting to excel sheet...')
writer = pd.ExcelWriter('data/bills-%s.xlsx', congress_session)
df113.to_excel(writer,'Sheet1')
writer.save()
