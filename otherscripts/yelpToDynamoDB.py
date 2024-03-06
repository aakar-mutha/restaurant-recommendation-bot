from __future__ import print_function

import argparse
import json
from pprint import pprint
import requests
import sys
import urllib
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.parse import urlencode
from time import sleep
import boto3
from decimal import Decimal
import datetime


API_KEY= ""

# API constants, you shouldn't have to change these.
API_HOST = 'https://api.yelp.com'
SEARCH_PATH = '/v3/businesses/search'
BUSINESS_PATH = '/v3/businesses/'  # Business ID will come after slash.


# Defaults for our code
DEFAULT_TERM = 'dinner'
DEFAULT_LOCATION = 'Manhattan'
SEARCH_LIMIT = 50
TABLE_NAME = 'yelp-restaurants'

def createResource():
    return boto3.resource('dynamodb')

def createTable(dynamodb):
# Get the service resource.
    client = boto3.client('dynamodb')
    existing_tables = client.list_tables()['TableNames']
    if(TABLE_NAME not in existing_tables):

        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'cuisine',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'cuisine',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        # Wait until the table exists.
        table.wait_until_exists()
         # Print out some data about the table.
    else:
        print(f"Table {TABLE_NAME} already exists.")



def request(host, path, url_params=None):
    """Given your API_KEY, send a GET request to the API.

    Args:
        host (str): The domain host of the API.
        path (str): The path of the API after the domain.
        API_KEY (str): Your API Key.
        url_params (dict): An optional set of query parameters in the request.

    Returns:
        dict: The JSON response from the request.

    Raises:
        HTTPError: An error occurs from the HTTP request.
    """
    url_params = url_params or {}
    url = '{0}{1}'.format(host, quote(path.encode('utf8')))
    headers = {
        'Authorization': 'Bearer %s' % API_KEY,
    }

    print(u'Querying {0} ...'.format(url))

    response = requests.request('GET', url, headers=headers, params=url_params)

    return response.json()


def search(cuisine,offset):
    """Query the Search API by a search term and location.

    Args:
        term (str): The search term passed to the API.
        location (str): The search location passed to the API.

    Returns:
        dict: The JSON response from the request.
    """

    url_params = {
        'location': DEFAULT_LOCATION,
        'limit': SEARCH_LIMIT,
        'term': cuisine + "+restaurants",
        'sort_by': 'rating',
        'offset' : offset
    }
    return request(API_HOST, SEARCH_PATH, url_params=url_params)

def convertRecord(record,cuisine):
    """
    Processess the record and maps them into the required dynamoDB format.
    Args: 
        id : string
        alias : string
        cuisine : string
        phone : string
        image_url : string
        name : string
        rating : string
        review_count : string
        yelp_url : string
        insertedAtTimestamp : string
        latitude : string
        longitude : string
        address : string
        state : string
        zip_code : string
        
    Returns: 
        dict
    """
    
    rec = {}
    rec['id'] = record.get('id',None)
    rec['alias'] = record.get('alias',None)
    rec['cuisine'] = cuisine
    rec['phone'] = record.get('display_phone', None)
    rec['image_url'] = record.get('image_url', None)
    rec['name'] = record.get('name', None)
    rec['rating'] = Decimal(str(record.get('rating', None)))
    rec['review_count'] = Decimal(str(record.get('review_count', None)))
    rec['yelp_url'] = record.get('url', None)
    rec['insertedAtTimestamp'] = str(datetime.datetime.now().isoformat())
    coordinates = record.get('coordinates', None)
    if(coordinates != None):
        rec['latitude'] = Decimal(str(coordinates.get('latitude', None)))
        rec['longitude'] = Decimal(str(coordinates.get('longitude', None)))
    
    location = record.get('location', None)
    if(location != None):
        address = location.get('display_address', None)
        if(address != None):
            rec['address'] = " ".join(address)
        rec['state'] = location.get('state', None)
        rec['zip_code'] = location.get('zip_code', None)
        
    return rec

def processRecord(dynamodb,records,cuisine):
    table = dynamodb.Table('yelp-restaurants')
    try:
        with table.batch_writer() as batch:
            for record in records:
                # batch.append(convertRecord(record,cuisine))py 
                batch.put_item(Item=convertRecord(record,cuisine))
                sleep(0.001)
    except Exception as e:
        print("Error in inserting the record.")
        pprint(e)        

if __name__ == "__main__":
    dynamoDB = createResource()
    createTable(dynamoDB)
    print("Table Created Successfully")
    cuisines = ['italian', 'chinese', 'indian', 'greek', 'mexican', 'spanish','american','japanese']
    
    
    for cuisine in cuisines:
        offset = 0
        while offset < 1000:
            records = search(cuisine, offset)
            if(len(records['businesses']) > 0):
                processRecord(dynamoDB,records['businesses'],cuisine)
                offset += SEARCH_LIMIT
                print(f"{offset} records of {cuisine} inserted.")
            else:
                offset += SEARCH_LIMIT
                break
                
    print("All records inserted")