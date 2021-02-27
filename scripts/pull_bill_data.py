# -*- coding: utf-8 -*-

### PULLING CONGRESSIONAL DATA
### from ProPublica Congress API
### https://projects.propublica.org/api-docs/congress-api/

#################
# LOAD PACKAGES #
#################

import requests, os, sys, json, re
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

def parse_argv():
    if len(sys.argv) > 1:
        parsed_args_list = [{"key": re.match("--([A-z0-9]+)=([A-z0-9]+)", arg)[1],
                             "value": re.match("--([A-z0-9]+)=([A-z0-9]+)", arg)[2]} for arg in sys.argv[1:]]
        parsed_args = {obj["key"]: obj["value"] for obj in parsed_args_list}
        return parsed_args
    else:
        return {}

def get_propublica_json(call_type, bill_type, session_id, bill_id):
    if call_type == "bill":
        url = 'https://api.propublica.org/congress/v1/%s/bills/%s%d.json' % (session_id, bill_type, bill_id)
    elif call_type == "cosponsor":
        url = 'https://api.propublica.org/congress/v1/%s/bills/%s%d/cosponsors.json' % (session_id, bill_type, bill_id)
    elif call_type == "recent_bills":
        url = 'https://api.propublica.org/congress/v1/%s/%s/bills/introduced.json' % (session_id, "house" if bill_type == "hr" else "senate")
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
    
# using helper and parsing funtions, get the information for a bill
def get_bill(bill_type, session_id, bill_id):
    status_message(log_file, "PARSING %s_%s%d" % (session_id, bill_type, bill_id), loud)
    
    bill_json = get_propublica_json("bill", bill_type, session_id, bill_id)
    bill_obj = parse_bill_data(bill_type, session_id, bill_id, bill_json)
    
    cosponsor_obj = []
    if bill_obj['_status'] == "PARSED":
        cosponsor_json = get_propublica_json("cosponsor", bill_type, session_id, bill_id)
        cosponsor_obj = parse_cosponsor_data(cosponsor_json)
        
    return [bill_obj, cosponsor_obj]

##################
# INIT VARIABLES #
##################

os.chdir('/Users/ben-tanen/Desktop/Projects/mvp-congress/')

api_keys = json.load(open("data/api_keys.json"))
log_file = "logs/log_%s.txt" % datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# parse arguments from command line (if present)
parsed_args = parse_argv()
try:
    bill_type = parsed_args["billtype"] if valid_key("billtype", parsed_args) else "hr"
    session_id = int(parsed_args["sessionid"]) if valid_key("sessionid", parsed_args) else 116
    loud = (True if parsed_args["loud"][0].lower() == "t" else False) if valid_key("loud", parsed_args) else True
except:
    status_message(log_file, "ERROR - issue parsing arguments V1", True)
    sys.exit()

# use recent bills to determine default range of bills to consider
recent_json = get_propublica_json("recent_bills", bill_type, session_id, None)
recent_bill_ids = [bill_obj["bill_id"] for bill_obj in recent_json["results"][0]["bills"] if bill_obj["bill_type"] == bill_type]
recent_bill_ids.sort()
most_recent_id = int(recent_bill_ids[-1].replace(bill_type, "").replace("-%d" % session_id, ""))

# assign high and low ID ranges (based on arguments [if present])
print(sys.argv)
print(parsed_args)
try:
    low_bill_id = int(parsed_args["low"]) if valid_key("low", parsed_args) else 1
    high_bill_id = int(parsed_args["high"]) if valid_key("high", parsed_args) else most_recent_id
except:
    status_message(log_file, "ERROR - issue parsing arguments V2", True)
    sys.exit()

# print out all arguments
print("ARGUMENTS - bill_type = %s; session = %d; bill range = [%d, %d]; loud = %r" % (bill_type, session_id, low_bill_id, high_bill_id, loud))

####################################
# LOOP THROUGH ALL BILLS AND PARSE #
####################################

all_bill_ids = range(low_bill_id, high_bill_id + 1)
# all_bill_ids.sort()

status_message(log_file, "STATUS - %d total bills to parse" % (len(all_bill_ids)), loud)
status_message(log_file, "STATUS - first bill is %s%d; last bill is %s%d" % (bill_type, all_bill_ids[0], bill_type, all_bill_ids[-1]), loud)

bill_info = [ ]
cosponsor_info = [ ]

# iterate over all bills
for bill_id in all_bill_ids:
    try:
        [bill_obj, cosponsor_obj] = get_bill(bill_type, session_id, bill_id)
        bill_info.append(bill_obj)
        if len(cosponsor_obj) > 0:
            cosponsor_info += cosponsor_obj
    except:
        status_message(log_file, "ERROR on %s_%s%d, unknown reason" % (session_id, bill_type, bill_id), loud)

#######################################
# CONVERT DATA ARRAYS INTO PANDAS DFS #
#######################################

status_message(log_file, "CONVERTING to pandas dfs", loud)

bill_df = pd.DataFrame(bill_info)
cosponsor_df = pd.DataFrame(cosponsor_info)

############
# SAVE DFS #
############

status_message(log_file, "SAVING datasets", loud)

bill_df.to_csv('data/%s%d_bills_%d-%d_%s.csv' % (bill_type, session_id, all_bill_ids[0], all_bill_ids[-1], datetime.now().strftime("%Y-%m-%d_%H-%M")), index = False)
cosponsor_df.to_csv('data/%s%d_cosponsors_%d-%d_%s.csv' % (bill_type, session_id, all_bill_ids[0], all_bill_ids[-1], datetime.now().strftime("%Y-%m-%d_%H-%M")), index = False)
