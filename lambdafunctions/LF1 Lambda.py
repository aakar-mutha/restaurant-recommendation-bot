import boto3
import datetime
import dateutil.parser
import json
import logging
import math
import os
import time
from botocore.vendored import requests
import re
EMAILREGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def get_slots(intent_request):
    return intent_request['interpretations'][0]['intent']['slots']


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return {"sessionState" : response}


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is False:
        return {
            "isValid": True,
            "violatedSlot": violated_slot
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {'sessionState' : {
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'ElicitSlot',
                
                'slotToElicit': slot_to_elicit,
                
                },
            'intent' : {
                'name' : intent_name,
                'slots': slots,
                },
            },
            'messages': [message]
        }
    


""" --- Functions that control the bot's behavior --- """


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def delegate(intent_name,session_attributes, slots):
    toFill = ""
    for i,j in slots.items():
        if j == None:
            toFill = i
            break
        
    if(toFill == ""):
        return {"sessionState": {
        "dialogAction": {
            "type": "ConfirmIntent"
        }, 
        "intent": {
                    "name": intent_name,
                    "slots" : slots
                },
        "messages": [{
            "contentType": "PlainText",
            "content": "Just to confirm, you want suggestions in {Location} for {Cuisine} food, for {NumberOfPeople} people, at {DiningTime}?"
                }]
            }
        }

    else:
        return {
            "sessionState": {
                "dialogAction": {
                    "slotToElicit": toFill,
                    "type": "ElicitSlot"
                },
                "intent": {
                    "name": intent_name,
                    "slots" : slots
                }
            }
        } 
    
def push_to_sqs(location, cuisine, dining_time, num_people, email, sessionId):
    # connect to SQS
    sqs_client = boto3.client('sqs')

    # SQS queue URL
    queue_url = 'https://sqs.us-east-1.amazonaws.com/905418445552/dining-suggestion-queue'

    # create message body
    message_body = {
        'sessionid': sessionId,
        'location': location,
        'cuisine': cuisine,
        'dining_time': dining_time,
        'num_people': num_people,
        'email': email
    }

    # send message to SQS queue
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body),
    )
    print(f"sent message {message_body} to SQS")

def validate_dining_suggestion(location, cuisine, num_people, time, email):
    cuisines = ['italian', 'chinese', 'indian', 'greek', 'mexican', 'spanish','american','japanese']
    locations = ['new york', 'manhattan']
    
    if(location is None):
        return build_validation_result(False,
                                       "Location",
                                       "This location is not supported.")
        
    elif (location.lower() not in locations):
        return build_validation_result(False,
                                       "Location",
                                       "This location is not supported.")
        
    if cuisine is not None and cuisine.lower() not in cuisines:
        return build_validation_result(False,
                                       'Cuisine',
                                       'Cuisine not available. Please try another.')

    if num_people is not None:
        num_people = int(num_people)
        if num_people > 20 or num_people < 0:
            return build_validation_result(False,
                                           'NumberOfPeople',
                                           'Maximum 20 people allowed. Try again')

    if time is not None:
        if len(time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', "Incorrect time entered. Please try again!")

        hour, minute = time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', 'Not a valid time')

        if hour <= 10 or hour >= 21:
            # Outside of business hours
            return build_validation_result(False, 'DiningTime',
                                           'Our business hours are from 10 am to 9 pm. Can you please specify a time during this range?')
    if email is not None:
        if(not re.fullmatch(EMAILREGEX, email)):
            build_validation_result(False, 'email', 'Can you please check your email address and try again?')
    
    return build_validation_result(True, None, None)


def get_slot_val(slot,to_get):
    if slot[to_get]:
        return slot[to_get]['value'].get('interpretedValue',None)
    return None

def dining_suggestion_intent(intent_request):
    
    slots = get_slots(intent_request)
    location = get_slot_val(slots,"Location")
    cuisine = get_slot_val(slots,"Cuisine")
    num_people = get_slot_val(slots,"NumberOfPeople")
    time = get_slot_val(slots,"DiningTime")
    email =  get_slot_val(slots,"email")
    source = intent_request['invocationSource']
    
    confirmation = intent_request['interpretations'][0]['intent']['confirmationState']
    if(confirmation == "Denied"):
        return {
                "sessionState": {
                    "dialogAction": {
                        "type": "ElicitIntent"
                    }
                },
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": "Okay! Lets try again!"
                    },
                    {
                        "contentType": "PlainText",
                        "content": "How can I help you today?"
                    }
                ]
            }
    elif(location == None or cuisine == None or num_people == None or time == None or email == None or confirmation != "Confirmed"):
        validation_result = validate_dining_suggestion(location, cuisine, num_people, time, email)   
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionState']['sessionAttributes'],
                            intent_request['interpretations'][0]['intent']['name'],
                            slots,
                            validation_result['violatedSlot'],
                            validation_result['message'])

        if intent_request['sessionState']['sessionAttributes'] is not None:
            output_session_attributes = intent_request['sessionState']['sessionAttributes']
        else:
            output_session_attributes = {}
            
        return delegate(intent_request['interpretations'][0]['intent']['name'],output_session_attributes, slots)
    
    else:
        sessionId = intent_request.get('sessionId')
        push_to_sqs(location,cuisine, time, num_people, email, sessionId)
        return {"sessionState": {
                    "dialogAction": {
                        "type": "Close"
                    },
                    "intent": {
                        "name": intent_request['interpretations'][0]['intent']['name'],
                        "state": "Fulfilled"
                    }
                },
                "messages": [{
                    "contentType": "PlainText",
                    "content": "Thank you for confirming, You will recieve the email shortly!"
                        }]
                }
        
def dispatch(intent_request):
    intent_name = intent_request['interpretations'][0]['intent']['name']
    logger.debug('dispatch, intentName={}'.format (intent_name))
    
    if intent_name == 'DiningSuggestionsIntent':
        return dining_suggestion_intent(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


def lambda_handler(event, context=[]):
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    # logger.debug('event.bot.name={}'.format(event['bot']['name']))
    print(json.dumps(event))
    toRet = dispatch(event)
    print(json.dumps(toRet))
    return toRet


# event = {
#     "inputMode": "Text",
#     "sessionId": "X8xby",
#     "inputTranscript": "yes",
#     "interpretations": [
#         {
#             "interpretationSource": "Lex",
#             "nluConfidence": 1,
#             "intent": {
#                 "confirmationState": "Confirmed",
#                 "name": "DiningSuggestionsIntent",
#                 "slots": {
#                     "Cuisine": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "indian",
#                             "resolvedValues": [
#                                 "indian"
#                             ],
#                             "interpretedValue": "indian"
#                         }
#                     },
#                     "NumberOfPeople": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "2",
#                             "resolvedValues": [
#                                 "2"
#                             ],
#                             "interpretedValue": "4"
#                         }
#                     },
#                     "DiningTime": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "6pm",
#                             "resolvedValues": [
#                                 "18:00"
#                             ],
#                             "interpretedValue": "18:00"
#                         }
#                     },
#                     "email": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "am13480@nyu.edu",
#                             "resolvedValues": [
#                                 "am13480@nyu.edu"
#                             ],
#                             "interpretedValue": "am13480@nyu.edu"
#                         }
#                     },
#                     "Location": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "new york",
#                             "resolvedValues": [
#                                 "new york"
#                             ],
#                             "interpretedValue": "new york"
#                         }
#                     }
#                 },
#                 "state": "InProgress"
#             }
#         },
#         {
#             "interpretationSource": "Lex",
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "FallbackIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             }
#         },
#         {
#             "interpretationSource": "Lex",
#             "nluConfidence": 0.37,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "GreetingIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             }
#         },
#         {
#             "interpretationSource": "Lex",
#             "nluConfidence": 0.23,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "ThankYouIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             }
#         }
#     ],
#     "bot": {
#         "aliasId": "TSTALIASID",
#         "aliasName": "TestBotAlias",
#         "name": "restaurantBot2",
#         "version": "DRAFT",
#         "localeId": "en_US",
#         "id": "V4X2CJY560"
#     },
#     "sessionState": {
#         "originatingRequestId": "9a0ce5f6-d10b-4289-8260-0cd4dc2b2c21",
#         "sessionAttributes": {},
#         "activeContexts": [],
#         "intent": {
#             "confirmationState": "Confirmed",
#             "name": "DiningSuggestionsIntent",
#             "slots": {
#                 "Cuisine": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "indian",
#                         "resolvedValues": [
#                             "indian"
#                         ],
#                         "interpretedValue": "indian"
#                     }
#                 },
#                 "NumberOfPeople": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "2",
#                         "resolvedValues": [
#                             "2"
#                         ],
#                         "interpretedValue": "2"
#                     }
#                 },
#                 "DiningTime": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "6pm",
#                         "resolvedValues": [
#                             "18:00"
#                         ],
#                         "interpretedValue": "18:00"
#                     }
#                 },
#                 "email": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "am13480@nyu.edu",
#                         "resolvedValues": [
#                             "am13480@nyu.edu"
#                         ],
#                         "interpretedValue": "am13480@nyu.edu"
#                     }
#                 },
#                 "Location": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "new york",
#                         "resolvedValues": [
#                             "new york"
#                         ],
#                         "interpretedValue": "new york"
#                     }
#                 }
#             },
#             "state": "InProgress"
#         }
#     },
#     "messageVersion": "1.0",
#     "invocationSource": "DialogCodeHook",
#     "responseContentType": "text/plain; charset=utf-8",
#     "transcriptions": [
#         {
#             "resolvedContext": {
#                 "intent": "DiningSuggestionsIntent"
#             },
#             "resolvedSlots": {},
#             "transcriptionConfidence": 1,
#             "transcription": "yes"
#         }
#     ]
# }

# event = {
#     "sessionId": "X8xby",
#     "inputTranscript": "no",
#     "interpretations": [
#         {
#             "nluConfidence": 1,
#             "intent": {
#                 "confirmationState": "Denied",
#                 "name": "DiningSuggestionsIntent",
#                 "slots": {
#                     "Cuisine": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "indian",
#                             "resolvedValues": [
#                                 "indian"
#                             ],
#                             "interpretedValue": "indian"
#                         }
#                     },
#                     "NumberOfPeople": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "4",
#                             "resolvedValues": [
#                                 "4"
#                             ],
#                             "interpretedValue": "4"
#                         }
#                     },
#                     "DiningTime": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "18:00",
#                             "resolvedValues": [
#                                 "18:00"
#                             ],
#                             "interpretedValue": "18:00"
#                         }
#                     },
#                     "email": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "am13480@nyu.edu",
#                             "resolvedValues": [
#                                 "am13480@nyu.edu"
#                             ],
#                             "interpretedValue": "am13480@nyu.edu"
#                         }
#                     },
#                     "Location": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "new york",
#                             "resolvedValues": [
#                                 "new york"
#                             ],
#                             "interpretedValue": "new york"
#                         }
#                     }
#                 },
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "FallbackIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "nluConfidence": 0.5,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "ThankYouIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "nluConfidence": 0.48,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "GreetingIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         }
#     ],
#     "bot": {
#         "aliasId": "TSTALIASID",
#         "aliasName": "TestBotAlias",
#         "name": "restaurantBot2",
#         "version": "DRAFT",
#         "localeId": "en_US",
#         "id": "V4X2CJY560"
#     },
#     "responseContentType": "text/plain; charset=utf-8",
#     "proposedNextState": {
#         "prompt": {
#             "attempt": "Initial"
#         },
#         "intent": {
#             "confirmationState": "None",
#             "name": "DiningSuggestionsIntent",
#             "slots": {
#                 "Cuisine": None,
#                 "NumberOfPeople": None,
#                 "DiningTime": None,
#                 "email": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "am13480@nyu.edu",
#                         "resolvedValues": [
#                             "am13480@nyu.edu"
#                         ],
#                         "interpretedValue": "am13480@nyu.edu"
#                     }
#                 },
#                 "Location": None
#             },
#             "state": "InProgress"
#         },
#         "dialogAction": {
#             "slotToElicit": "Location",
#             "type": "ElicitSlot"
#         }
#     },
#     "sessionState": {
#         "sessionAttributes": {},
#         "intent": {
#             "confirmationState": "Denied",
#             "name": "DiningSuggestionsIntent",
#             "slots": {
#                 "Cuisine": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "indian",
#                         "resolvedValues": [
#                             "indian"
#                         ],
#                         "interpretedValue": "indian"
#                     }
#                 },
#                 "NumberOfPeople": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "4",
#                         "resolvedValues": [
#                             "4"
#                         ],
#                         "interpretedValue": "4"
#                     }
#                 },
#                 "DiningTime": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "18:00",
#                         "resolvedValues": [
#                             "18:00"
#                         ],
#                         "interpretedValue": "18:00"
#                     }
#                 },
#                 "email": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "am13480@nyu.edu",
#                         "resolvedValues": [
#                             "am13480@nyu.edu"
#                         ],
#                         "interpretedValue": "am13480@nyu.edu"
#                     }
#                 },
#                 "Location": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "new york",
#                         "resolvedValues": [
#                             "new york"
#                         ],
#                         "interpretedValue": "new york"
#                     }
#                 }
#             },
#             "state": "InProgress"
#         },
#         "originatingRequestId": "ddaacdf5-4b4b-4bc9-a494-12cf6a3594ce"
#     },
#     "messageVersion": "1.0",
#     "invocationSource": "DialogCodeHook",
#     "transcriptions": [
#         {
#             "resolvedContext": {
#                 "intent": "DiningSuggestionsIntent"
#             },
#             "transcriptionConfidence": 1,
#             "transcription": "no",
#             "resolvedSlots": {}
#         }
#     ],
#     "inputMode": "Text"
# }

# event = {
#     "sessionId": "NDmqk",
#     "inputTranscript": "yes",
#     "interpretations": [
#         {
#             "nluConfidence": 1,
#             "intent": {
#                 "confirmationState": "Confirmed",
#                 "name": "DiningSuggestionsIntent",
#                 "slots": {
#                     "Cuisine": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "indian",
#                             "resolvedValues": [
#                                 "indian"
#                             ],
#                             "interpretedValue": "indian"
#                         }
#                     },
#                     "NumberOfPeople": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "3",
#                             "resolvedValues": [
#                                 "3"
#                             ],
#                             "interpretedValue": "3"
#                         }
#                     },
#                     "DiningTime": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "6pm",
#                             "resolvedValues": [
#                                 "18:00"
#                             ],
#                             "interpretedValue": "18:00"
#                         }
#                     },
#                     "email": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "am13480@nyu.edu",
#                             "resolvedValues": [
#                                 "am13480@nyu.edu"
#                             ],
#                             "interpretedValue": "am13480@nyu.edu"
#                         }
#                     },
#                     "Location": {
#                         "shape": "Scalar",
#                         "value": {
#                             "originalValue": "new york",
#                             "resolvedValues": [
#                                 "new york"
#                             ],
#                             "interpretedValue": "new york"
#                         }
#                     }
#                 },
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "FallbackIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "nluConfidence": 0.37,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "GreetingIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         },
#         {
#             "nluConfidence": 0.23,
#             "intent": {
#                 "confirmationState": "None",
#                 "name": "ThankYouIntent",
#                 "slots": {},
#                 "state": "InProgress"
#             },
#             "interpretationSource": "Lex"
#         }
#     ],
#     "bot": {
#         "aliasId": "TSTALIASID",
#         "aliasName": "TestBotAlias",
#         "name": "restaurantBot2",
#         "version": "DRAFT",
#         "localeId": "en_US",
#         "id": "V4X2CJY560"
#     },
#     "responseContentType": "text/plain; charset=utf-8",
#     "sessionState": {
#         "sessionAttributes": {},
#         "activeContexts": [],
#         "intent": {
#             "confirmationState": "Confirmed",
#             "name": "DiningSuggestionsIntent",
#             "slots": {
#                 "Cuisine": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "indian",
#                         "resolvedValues": [
#                             "indian"
#                         ],
#                         "interpretedValue": "indian"
#                     }
#                 },
#                 "NumberOfPeople": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "3",
#                         "resolvedValues": [
#                             "3"
#                         ],
#                         "interpretedValue": "3"
#                     }
#                 },
#                 "DiningTime": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "6pm",
#                         "resolvedValues": [
#                             "18:00"
#                         ],
#                         "interpretedValue": "18:00"
#                     }
#                 },
#                 "email": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "am13480@nyu.edu",
#                         "resolvedValues": [
#                             "am13480@nyu.edu"
#                         ],
#                         "interpretedValue": "am13480@nyu.edu"
#                     }
#                 },
#                 "Location": {
#                     "shape": "Scalar",
#                     "value": {
#                         "originalValue": "new york",
#                         "resolvedValues": [
#                             "new york"
#                         ],
#                         "interpretedValue": "new york"
#                     }
#                 }
#             },
#             "state": "InProgress"
#         },
#         "originatingRequestId": "3b20f674-ead1-46fc-89a5-7651db0aeefd"
#     },
#     "messageVersion": "1.0",
#     "invocationSource": "DialogCodeHook",
#     "transcriptions": [
#         {
#             "resolvedContext": {
#                 "intent": "DiningSuggestionsIntent"
#             },
#             "resolvedSlots": {},
#             "transcriptionConfidence": 1,
#             "transcription": "yes"
#         }
#     ],
#     "inputMode": "Text"
# }

# lambda_handler(event)