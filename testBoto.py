# import boto3
# from pprint import pprint

# client = boto3.client('lexv2-models')
# # response = client.list_bot_aliases(
# #     botId='WMPBTRYOED')
# # pprint.pprint(response)

# response = client.list_bots(
#     sortBy={
#         'attribute': 'BotName',
#         'order': 'Ascending'
#     },
# )
# pprint(response)

import botocore.awsrequest
import requests
from requests_aws4auth import AWS4Auth

# url = curl -XGET "http://localhost:9200/restaurant-index" -H 'Content-Type: application/json' -d'
# {
#         "size": 5,
#         "query": {
#             "multi_match": {
#             "query": "indian",
#             "fields": ["address", "name"]
#             }
#         },
#         "sort" : {
#             "rating" :{
#                 "order" : "desc"
#             }
#         }
#     }'