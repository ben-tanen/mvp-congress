# -*- coding: utf-8 -*-

### PULLING CONGRESSIONAL DATA
### from ProPublica Congress API
### https://projects.propublica.org/api-docs/congress-api/

#################
# LOAD PACKAGES #
#################

import requests, os, json
import pandas as pd
from datetime import datetime

###########################
# DEFINE HELPER FUNCTIONS #
###########################

def status_message(log_file, message, loud):
    with open(log_file, 'a') as file:
        file.write("%s\n" % message)
    if loud:
        print(message)

def valid_key(key, obj):
    return key in obj.keys()

def get_propublica_json(call_type, bill_type, session_id, bill_id):
    if call_type == "bill":
        url = 'https://api.propublica.org/congress/v1/%s/bills/%s%d.json' % (session_id, bill_type, bill_id)
    elif call_type == "cosponsor":
        url = 'https://api.propublica.org/congress/v1/%s/bills/%s%d/cosponsors.json' % (session_id, bill_type, bill_id)
    response = requests.get(url, headers = {'X-API-KEY': api_keys["propublica_congress_key"]})

    if response.status_code == 200:
        return response.json()

############################
# DEFINE PARSING FUNCTIONS #
############################

# function to parse bill json and return general bill information
def parse_bill_data(bill_type, session_id, bill_id, bill_json):
    
    # init bill object
    bill_obj = {
        '_query_time': datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        '_type': bill_type,
        '_id': bill_id,
        '_session': session_id,
    }
    
    # check for errors: (1) if no results, (2) get more than one bill back
    if bill_json['status'] != "OK":
        status_message(log_file, "ERROR on %s_%s%d, got status: %s" % (session_id, bill_type, bill_id, bill_json['status']), loud)
        bill_obj.update({"_status": "QUERY ERROR"})
        return bill_obj
    elif len(bill_json['results']) != 1:
        status_message(log_file, "ERROR on %s_%s%d, expecting 1 result, got %d" % (session_id, bill_type, bill_id, len(bill_json['results'])), loud)
        bill_obj.update({"_status": "UNEXPECTED MULTIPLE RESULTS"})
        return bill_obj
    
    # if no errors, return parsed data
    bill_json = bill_json["results"][0]
    bill_obj.update({
        '_status': "PARSED",
        '_short_title': bill_json['short_title'],
        '_official_title': bill_json['title'],
        '_passed_house': bill_json['house_passage'] != None,
        '_passed_senate': bill_json['senate_passage'] != None,
        '_introduced': bill_json['introduced_date'],
        '_top_subject': bill_json['primary_subject'],
        '_sponsor_id': bill_json['sponsor_id'],
        '_sponsor_name': bill_json['sponsor'],
        '_sponsor_party': bill_json['sponsor_party'],
        '_n_cosponsors': bill_json['cosponsors'],
        '_n_dem_cosponsors': bill_json['cosponsors_by_party']['D'] if valid_key("D", bill_json['cosponsors_by_party']) else 0,
        '_n_rep_cosponsors': bill_json['cosponsors_by_party']['R'] if valid_key("R", bill_json['cosponsors_by_party']) else 0,
        '_n_withdrawn_cosponsors': bill_json['withdrawn_cosponsors']
    })
    return bill_obj

# function to parse cosponsor json and return a list of cosponsors
def parse_cosponsor_data(cosponsor_json):
    
    # init cosponsor list
    query_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    cosponsor_json = cosponsor_json["results"][0]
    cosponsors = [{
        '_query_time': query_time,
        '_bill_type': cosponsor_json["bill_type"],
        '_bill_id': cosponsor_json["bill_id"],
        '_session_id': cosponsor_json["congress"],
        '_cosponsor_type': 'sponsor',
        '_cosponsor_name': cosponsor_json['sponsor_name'],
        '_cosponsor_id': cosponsor_json['sponsor_id'],
        '_cosponsor_state': cosponsor_json['sponsor_state'],
        '_cosponsor_title': cosponsor_json['sponsor_title'],
        '_cosponsor_party': cosponsor_json['sponsor_party'],
        '_cosponsor_date': cosponsor_json['introduced_date']
    }]
    
    # loop through all other cosponsors
    for cosponsor in cosponsor_json["cosponsors"]:
        cosponsors.append({
            '_query_time': query_time,
            '_bill_type': cosponsor_json["bill_type"],
            '_bill_id': cosponsor_json["bill_id"],
            '_session_id': cosponsor_json["congress"],
            '_cosponsor_type': 'cosponsor',
            '_cosponsor_name': cosponsor['name'],
            '_cosponsor_id': cosponsor['cosponsor_id'],
            '_cosponsor_state': cosponsor['cosponsor_state'],
            '_cosponsor_title': cosponsor['cosponsor_title'],
            '_cosponsor_party': cosponsor['cosponsor_party'],
            '_cosponsor_date': cosponsor['date']
        })
        
    return cosponsors
    

##################
# INIT VARIABLES #
##################

os.chdir('/Users/ben-tanen/Desktop/Projects/mvp-congress/')

api_keys = json.load(open("data/api_keys.json"))

loud = True

bill_type = "hr"
session_id = 116

log_file = "logs/log_%s.txt" % datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

####################################
# LOOP THROUGH ALL BILLS AND PARSE #
####################################

bill_info = [ ]
cosponsor_info = [ ]

all_bill_ids = [1, 2, 3, 4, 5, 15, 20, 23, 3088, 502]

all_bill_ids.sort()

status_message(log_file, "%d total bills; last bill is %s%d" % (len(all_bill_ids), bill_type, all_bill_ids[-1]), loud)

# iterate over all bills
for bill_id in all_bill_ids:

    status_message(log_file, "PARSED %s_%s%d" % (session_id, bill_type, bill_id), loud)
    
    bill_json = get_propublica_json("bill", bill_type, session_id, bill_id)
    bill_obj = parse_bill_data(bill_type, session_id, bill_id, bill_json)

    bill_info.append(bill_obj)
    
    if bill_obj['_status'] == "PARSED":
        cosponsor_json = get_propublica_json("cosponsor", bill_type, session_id, bill_id)
        cosponsor_info.append(parse_cosponsor_data(cosponsor_json))

#######################################
# CONVERT DATA ARRAYS INTO PANDAS DFS #
#######################################

status_message(log_file, "--> converting to pandas dfs", loud)

general_df = pd.DataFrame(general_info)
actions_df = pd.DataFrame(actions)

############
# SAVE DFS #
############

status_message(log_file, "--> saving datasets", loud)

general_df.to_csv('data/2019-10-09_%s%d_general_%d-%d.csv' % (bill_type, session_id, all_bill_ids[0], all_bill_ids[-1]), index = False)
actions_df.to_csv('data/2019-10-09_%s%d_actions_%d-%d.csv' % (bill_type, session_id, all_bill_ids[0], all_bill_ids[-1]), index = False)
    