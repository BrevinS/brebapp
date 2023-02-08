import espn_scraper as espn
import json


def ppjson(data):
    print(json.dumps(data, indent=2, sort_keys=True))

def athletes(json):
    json_data = json['page']['content']['gamepackage']['bxscr']['athletes']
    
    return json_data

# function to find live game id's