import boto3
from boto3.dynamodb.conditions import Key

from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from pprint import pprint

import json
from decimal import Decimal



host = 'localhost'
port = 9200
auth = ('admin','admin')
# Create the client with SSL/TLS and hostname verification disabled.
client = OpenSearch(
    hosts = [{'host': host, 'port': port}],
    http_auth = auth,
    http_compress = True, # enables gzip compression for request bodies
    use_ssl = True,
    verify_certs = False,
    ssl_assert_hostname = False,
    ssl_show_warn = False
)


q = 'Japanese'
query = {
  'size': 5,
  'query': {
    'multi_match': {
      'query': q,
      'fields': ['address', 'name']
    }
  },
  'sort' : {
      'rating' :{
          'order' : 'desc'
      }
  }
  
}


response = client.search(
    body = query,
    index = 'restaurant-index'
)

pprint(response)