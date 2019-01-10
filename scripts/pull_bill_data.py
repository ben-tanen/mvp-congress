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

def status_message(message, loud):
    if loud:
        print(message)

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
        '_district': bill_json['sponsor']['district'] if bill_json['sponsor']['district'] != None else 0,
        '_joined_at': bill_json['actions'][0]['acted_at']
    })
        
    # add all cosponsors
    for cosponsor in bill_json['cosponsors']:
        sponsors.append({
            '_type': 'original cosponsor' if valid_key('original_cosponsor', cosponsor) \
                                          and cosponsor['original_cosponsor'] == True else 'cosponsor',
            '_bill': bill_json['bill_type'] + bill_json['number'],
            '_name': cosponsor['name'],
            '_title': cosponsor['title'],
            '_state': cosponsor['state'],
            '_district': cosponsor['district'] if cosponsor['district'] != None else 0,
            '_joined_at': cosponsor['sponsored_at']
        })
    
    return sponsors

##################
# INIT VARIABLES #
##################

loud = True

bill_type = "hr"
session_id = 111

####################################
# LOOP THROUGH ALL BILLS AND PARSE #
####################################

general_info = [ ]
actions  = [ ]
sponsors = [ ]

# get list of bills
all_bills_url  = "https://www.govtrack.us/data/congress/%d/bills/%s/" % (session_id, bill_type)
all_bills_soup = BeautifulSoup(requests.get(all_bills_url).text, 'html.parser')
all_bills = [a.decode_contents()[:-1] for a in all_bills_soup.find_all('a')]
all_bill_ids = [int(bill[len(bill_type):]) for bill in all_bills if bill != ".."]
all_bill_ids.sort()

status_message("%d total bills; last bill is %s%d" % (len(all_bill_ids), bill_type, all_bill_ids[-1]), loud)

# iterate over all bills
for bill_id in all_bill_ids:

    status_message("--> parsing %s%d" % (bill_type, bill_id), loud)
    
    bill_json = get_bill_json(bill_type, session_id, bill_id)
    
    if bill_json == None:
        continue

    general_info.append(parse_general_bill_data(bill_json))
    actions  += parse_actions_bill_data(bill_json)
    sponsors += parse_sponsor_bill_data(bill_json)

#######################################
# CONVERT DATA ARRAYS INTO PANDAS DFS #
#######################################

status_message("--> converting to pandas dfs", loud)

general_df = pd.DataFrame(general_info)
actions_df = pd.DataFrame(actions)
sponsor_df = pd.DataFrame(sponsors)

###########################################################
# BUILD DATASET OF CONGRESS MEMBERS FROM SPONSORSHIP DATA #
###########################################################

# get unique reps from sponsor_df
members_df = sponsor_df[['_name', '_state', '_district', '_title']].drop_duplicates()

# add full district column
members_df['_full_district'] = members_df['_state'].str.cat(members_df['_district'].values.astype('str'))

# clean name and normalize between sources
def clean_member_name(name):    
    # remove jr. and sr.
    clean_name = re.sub("(,)? (Jr|Sr)\.", "", name).strip()
    
    # remove nicknames
    clean_name = re.sub('"(.*)?"', "", clean_name).strip()
    
    # remove middle initial
    clean_name = re.sub(" [A-Z]\.$", "", clean_name).strip()
    
    # standardize certain characters
    clean_name = re.sub("á", "a", clean_name)
    clean_name = re.sub("é", "e", clean_name)
    clean_name = re.sub("í", "i", clean_name)
    clean_name = re.sub("ó", "o", clean_name)
    clean_name = re.sub("(ú|ü)", "u", clean_name)
    clean_name = re.sub("’", "'", clean_name)
    
    return clean_name
    
members_df['_clean_name'] = np.vectorize(clean_member_name)(members_df['_name'])
members_df['_last_name'] = np.vectorize(lambda n: n.split(',')[0])(members_df['_clean_name'])
members_df['_merge_flag'] = members_df['_last_name'].str.cat(members_df['_full_district'], sep='-')

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

status_message("--> pulling member data from EveryPolitician", loud)

for member in ep_house_session.csv():
    members_data.append({
        '_name': member['name'],
        '_sort_name': member['sort_name'],
        '_party': member['group'],
        '_district': int(re.search('cd:([0-9]+)',member['area_id'])[1]) if len(member['area_id']) > 32 else 0,
        '_state': re.search('state:([a-z]+)',member['area_id'])[1].upper(),
        '_facebook': member['facebook'],
        '_twitter': member['twitter']
    })
    
# add a merge flag to merge onto existing member df
for member in members_data:
    member.update({'_merge_flag': "%s-%s%d" % (clean_member_name(member['_sort_name']).split(',')[0], \
                                               member['_state'], member['_district']) })
        
    # minor manual tweaks to merge flag
    if 'Radewagen' in member['_name']:
        member['_merge_flag'] = 'Radewagen-AS0'

# merge member data onto members_df
members_df = pd.merge(members_df, pd.DataFrame(members_data), how='left', \
                      left_on='_merge_flag', right_on='_merge_flag')

members_df = members_df.drop(['_sort_name', '_clean_name', '_district_y', '_state_y', '_merge_flag'], axis=1)
members_df = members_df.rename(columns = {'_name_x': '_sort_name', '_state_x': '_state', 
                                '_district_x': '_district', '_name_y': '_clean_name'})
members_df = members_df.fillna('')

####################################
# PULL NUMBER OF TWITTER FOLLOWERS #
####################################

import tweepy
# see tweepy docs for more
# http://tweepy.readthedocs.io/

# pull in api key and secret
api_keys = json.load(open("../data/api_keys.json"))

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

status_message("--> pulling twitter follower counts for members", loud)

members_df['_twitter_followers'] = np.vectorize(get_twitter_follower_count)(members_df['_twitter'])

############
# SAVE DFS #
############

status_message("--> saving datasets", loud)

general_df.to_csv('../data/general-%s%d.csv' % (bill_type, session_id), index = False)
actions_df.to_csv('../data/actions-%s%d.csv' % (bill_type, session_id), index = False)
sponsor_df.to_csv('../data/sponsor-%s%d.csv' % (bill_type, session_id), index = False)
members_df.to_csv('../data/members-%s%d.csv' % (bill_type, session_id), index = False)
    