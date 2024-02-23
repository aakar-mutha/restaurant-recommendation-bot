import json
from pprint import pprint
import boto3
import json
from boto3.dynamodb.conditions import Key

def createSlot(name,value):
    return {
        name : {
            "shape": "Scalar",
            "value": {
                        "originalValue": value,
                        "resolvedValues": [
                            value
                        ],
                        "interpretedValue": value
                    }
                }
        }

def createResponse(lexClient,record):
    slots = {}
    slots.update(createSlot('Cuisine',record['cuisine']))
    slots.update(createSlot('NumberOfPeople',record['num_people']))
    slots.update(createSlot('DiningTime',record['dining_time']))
    slots.update(createSlot('email',record['email']))
    slots.update(createSlot('Location',record['location']))
    resp = lexClient.put_session ( 
            botId= 'V4X2CJY560',
            botAliasId= 'TSTALIASID',
            localeId= 'en_US',
            sessionId= record['sessionid'],
            messages= [
                {
                    'content': 'Just to confirm, you want suggestions in {Location} for {Cuisine} food, for {NumberOfPeople} people, at {DiningTime}?' ,
                    'contentType': 'PlainText'
                },
            ],
            sessionState = {
                'dialogAction' : {
                    'type':'ConfirmIntent',
                },
                'intent' : {
                    'name' : 'DiningSuggestionsIntent',
                    'slots' : slots,
                }
            }
        )
    return {
        "statusCode": 200, "messages": [
        {
            "type": "unstructured",
            "unstructured": {
                "text": f'Do you want to dine in {record['location']} at {record['dining_time']} as a party of {record['num_people']} and try the cuisine {record['cuisine']}?'
            },
        }]
    }

def lambda_handler(event, context=[]):
    print(json.dumps(event))
    lexClient = boto3.client("lexv2-runtime")
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('user-data')
    SID = event.get('sessionId')
    messages = event.get("messages", None)
    records = table.query(
      KeyConditionExpression=Key('sessionid').eq(SID),
    )
    
    if(records['Count'] > 0) :
        table.delete_item(
            Key={
                'sessionid': SID
            }
        )
        a = createResponse(lexClient,records['Items'][0])
        print(json.dumps(a))
        return a
    if messages is not None:
        for i in messages:
            response = lexClient.recognize_text(
                botId = "V4X2CJY560",
                botAliasId = "TSTALIASID",
                localeId = "en_US",
                sessionId = SID,
                text = i["unstructured"]["text"],
            )
            print(json.dumps(response))
            responseMsgs = response.get("messages", None)
            retObj = {"statusCode": 200, "messages": []}
            if responseMsgs:
                for i in responseMsgs:
                    retObj["messages"].append(
                        {"type": "unstructured", "unstructured": {"text": i["content"]}}
                    )
                return retObj

    return {
        "statusCode": 200,
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "text": "Something went wrong, please try again!"
                },
            }
        ],
    }

# event = {
#     "messages": [
#         {
#             "type": "unstructured",
#             "unstructured": {
#                 "text": "yes"
#             }
#         }
#     ],
#     "sessionId": "d0XNf"
# }

# event = {"messages": [{"type": "unstructured", "unstructured": {"text": "hi"}}], "sessionId": "L3gdO"}



# pprint(lambda_handler(event=event))
