# -*- coding: utf-8 -*-

### PULLING CONGRESSIONAL DATA
### from GovTrack.us
### https://www.govtrack.us/data/

#################
# LOAD PACKAGES #
#################

import requests
import numpy as np
import pandas as pd
from datetime import datetime

###########################
# DEFINE HELPER FUNCTIONS #
###########################

def valid_key(key, obj):
    return key in obj.keys()

############################
# DEFINE PARSING FUNCTIONS #
############################

# function to parse bill json and return general bill information
def parse_general_bill_data(bill_json):
    return {
        '_type': bill_json['bill_type'],
        '_id': bill_json['number'],
        '_session': bill_json['congress'],
        '_short_title': bill_json['short_title'],
        '_official_title': bill_json['official_title'],
        '_enacted': 'enacted_as' in bill_json.keys(),
        '_introduced': datetime.strptime(bill_json['introduced_at'], '%Y-%M-%d'),
        '_top_subject': bill_json['subjects_top_term']
    }
    
# function to parse bill json and 
# return list of actions taken for a particular bill
def parse_actions_bill_data(bill_json):
    actions = [ ]
    
    # pull raw action data from json
    for action in bill_json['actions']:
        actions.append({
            '_bill': bill_json['bill_type'] + bill_json['number'],
            '_date': datetime.strptime(action['acted_at'][:10], '%Y-%M-%d').date(),
            '_time': datetime.strptime(action['acted_at'][11:19], '%H:%M:%S').time() if len(action['acted_at']) > 10 else None,
            '_status':  action['status'] if valid_key('status', action) else None,
            '_type': action['type'],
            '_committees': '|'.join(action['committees']) if valid_key('committees', action) else None,
            '_action_text': action['text']
        })

    # set first status as introduction      
    actions[0]['_status'] = 'INTRODUCED'
        
    # set status of all other actions
    for action in actions:
        # figure out something for this
        action['_status']
          
    return actions

# function to parse bill json and
# return a list of sponsors and cosponsors for a particular bill
def parse_sponsor_bill_data(bill_json):
    sponsors = [ ]
    
    # add sponsor
    sponsors.append({
        '_type': 'sponsor',
        '_bill': bill_json['bill_type'] + bill_json['number'],
        '_name': bill_json['sponsor']['name'],
        '_title': bill_json['sponsor']['title'],
        '_state': bill_json['sponsor']['state'],
        '_district': bill_json['sponsor']['district'],
        '_id': bill_json['sponsor']['bioguide_id'],
        '_joined_at': bill_json['actions'][0]['acted_at']
    })
        
    # add all cosponsors
    for cosponsor in bill_json['cosponsors']:
        sponsors.append({
            '_type': 'original cosponsor' if cosponsor['original_cosponsor'] == True else 'cosponsor',
            '_bill': bill_json['bill_type'] + bill_json['number'],
            '_name': cosponsor['name'],
            '_title': cosponsor['title'],
            '_state': cosponsor['state'],
            '_district': cosponsor['district'],
            '_id': cosponsor['bioguide_id'],
            '_joined_at': cosponsor['sponsored_at']
        })
    
    return sponsors

####################################
# LOOP THROUGH ALL BILLS AND PARSE #
####################################

loud = True
loud_count = 25

session_id = 114

general_data = [ ]
actions_data = [ ]
sponsor_data = [ ]

for bill_id in range(1,100):

    if loud and bill_id % loud_count == 0:
        print("--> parsing bill #%d" % bill_id)
    
    bill_url = 'https://www.govtrack.us/data/congress/%s/bills/hr/hr%d/data.json' % (session_id, bill_id)

    response = requests.get(bill_url)

    if response.status_code != 200:
        continue

    bill_json = response.json()

    general_data.append(parse_general_bill_data(bill_json))
    actions_data += parse_actions_bill_data(bill_json)
    sponsor_data += parse_sponsor_bill_data(bill_json)

###########################################################
# BUILD DATASET OF CONGRESS MEMBERS FROM SPONSORSHIP DATA #
###########################################################

reps_data = [ ]

# get unique reps from sponsor_data

# pull twitter, google, etc. data

#######################################
# CONVERT DATA ARRAYS INTO PANDAS DFS #
#######################################

general_df = pd.DataFrame(general_data)
actions_df = pd.DataFrame(actions_data)
sponsor_df = pd.DataFrame(sponsor_data)




    