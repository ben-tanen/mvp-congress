# -*- coding: utf-8 -*-

### PULLING CONGRESSIONAL DATA
### from GovTrack.us
### https://www.govtrack.us/data/

#################
# LOAD PACKAGES #
#################

import requests, re, json
import pandas as pd
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup

###########################
# DEFINE HELPER FUNCTIONS #
###########################

def valid_key(key, obj):
    return key in obj.keys()

def get_bill_json(bill_type, session_id, bill_id):
    url = 'https://www.govtrack.us/data/congress/%s/bills/%s/%s%d/data.json' % (session_id, bill_type, bill_type, bill_id)
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()

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
        '_status': bill_json['status'],
        '_passed_house': valid_key('house_passage_result', bill_json['history']) \
                         and bill_json['history']['house_passage_result'] == 'pass',
        '_passed_senate': valid_key('senate_passage_result', bill_json['history']) \
                          and bill_json['history']['senate_passage_result'] == 'pass',
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

bill_type = "hr"
session_id = 114

general_info = [ ]
actions  = [ ]
sponsors = [ ]

# get list of bills
all_bills_url  = "https://www.govtrack.us/data/congress/%d/bills/%s/" % (session_id, bill_type)
all_bills_soup = BeautifulSoup(requests.get(all_bills_url).text, 'html.parser')
all_bills = [a.decode_contents()[:-1] for a in all_bills_soup.find_all('a')]
all_bill_ids = [int(bill[len(bill_type):]) for bill in all_bills if bill != ".."]
all_bill_ids.sort()

# iterate over all bills
for bill_id in all_bill_ids[:100]:

    if loud and bill_id % loud_count == 0:
        print("--> parsing %s%d" % (bill_type, bill_id))
    
    bill_json = get_bill_json(bill_type, session_id, bill_id)
    
    if bill_json == None:
        continue

    general_info.append(parse_general_bill_data(bill_json))
    actions  += parse_actions_bill_data(bill_json)
    sponsors += parse_sponsor_bill_data(bill_json)

#######################################
# CONVERT DATA ARRAYS INTO PANDAS DFS #
#######################################

general_df = pd.DataFrame(general_info)
actions_df = pd.DataFrame(actions)
sponsor_df = pd.DataFrame(sponsors)

###########################################################
# BUILD DATASET OF CONGRESS MEMBERS FROM SPONSORSHIP DATA #
###########################################################

# get unique reps from sponsor_data
members_df = sponsor_df[['_id', '_name', '_state', '_district', '_title']].drop_duplicates()

# add clean name column
def clean_member_name(name):
    # remove middle initial
    clean_name = re.sub(" [A-Z]\.", "", name).strip()
    
    # remove jr. and sr.
    clean_name = re.sub("(,)? (Jr|Sr)\.", "", clean_name).strip()
    
    # remove nicknames
    clean_name = re.sub('"(.*)?"', "", clean_name).strip()
    
    return clean_name
    
members_df['_clean_name'] = np.vectorize(clean_member_name)(members_df['_name'])

##################################################################
# PULL PARTY AFFILIATION AND TWITTER HANDLE FROM EVERYPOLITICIAN #
##################################################################

from everypolitician import EveryPolitician
# see EveryPolitician and ruby documentation for more:
# http://everypolitician.org/united-states-of-america/
# https://github.com/everypolitician/everypolitician-ruby

# get relevant house and senate sessions
ep = EveryPolitician().country('United-States-of-America')
ep_house  = ep.lower_house()
ep_senate = ep.upper_house()
ep_house_session  = [lp for lp in ep_house.legislative_periods() if lp.id == "term/%d" % session_id][0]
ep_senate_session = [lp for lp in ep_senate.legislative_periods() if lp.id == "term/%d" % session_id][0]

# pull party affiliation, facebook name, and twitter handle from ep
members_data = [ ]

for member in ep_house_session.csv():
    members_data.append({
        '_name': member['name'],
        '_sort_name': member['sort_name'],
        '_party': member['group'],
        '_facebook': member['facebook'],
        '_twitter': member['twitter']
    })

# merge data onto members_df
members_df = pd.merge(members_df, pd.DataFrame(members_data), how='left', \
                      left_on='_clean_name', right_on='_sort_name')

members_df = members_df.fillna('')

np.isnan(members_df['_facebook'][392])

####################################
# PULL NUMBER OF TWITTER FOLLOWERS #
####################################

import tweepy
# see tweepy docs for more
# http://tweepy.readthedocs.io/

# pull in api key and secret
api_keys = json.load(open("api_keys.json"))

tweepy_auth = tweepy.OAuthHandler(api_keys['tweepy_consumer_key'], api_keys['tweepy_consumer_secret'])
tweepy_api  = tweepy.API(tweepy_auth)

def get_twitter_follower_count(handle):
    if isinstance(handle, str) and len(handle) > 0:
        try: 
            return tweepy_api.get_user(handle).followers_count
        except:
            return -1
    else:
        return -1

members_df['_twitter_followers'] = np.vectorize(get_twitter_follower_count)(members_df['_twitter'])






    