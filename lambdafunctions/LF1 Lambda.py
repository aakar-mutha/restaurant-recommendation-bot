import boto3
import datetime
import dateutil.parser
import json
import logging
import math
import os
import time
from botocore.vendored import requests

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
    
def push_to_sqs(location, cuisine, dining_time, num_people, email):
    # connect to SQS
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='dining-suggestion-queue')

    # create message body
    message_body = {
        'location': location,
        'cuisine': cuisine,
        'dining_time': dining_time,
        'num_people': num_people,
        'email': email
    }

    # send message to SQS queue
    queue.send_message(MessageBody=json.dumps(message_body))
    print(f"sent message {message_body} to SQS")




def greeting_intent(intent_request):
    return {
        'dialogAction': {
            "type": "ElicitIntent",
            'message': {
                'contentType': 'PlainText',
                'content': 'Hi there, how can I help?'}
        }
    }


def thank_you_intent(intent_request):
    return {
        'dialogAction': {
            "type": "ElicitIntent",
            'message': {
                'contentType': 'PlainText',
                'content': 'You are welcome!'}
        }
    }


def validate_dining_suggestion(location, cuisine, num_people, time):
    cuisines = ['italian', 'chinese', 'indian', 'american', 'mexican', 'spanish', 'greek', 'latin', 'Persian']
    locations = ['new york', 'manhattan','ny']
    if location is not None and location.lower() not in locations:
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

        if hour < 10 or hour > 16:
            # Outside of business hours
            return build_validation_result(False, 'DiningTime',
                                           'Our business hours are from ten a m. to five p m. Can you specify a time during this range?')

    return build_validation_result(True, None, None)


def get_slot_val(slot,to_get):
    if slot[to_get]:
        return slot[to_get]['value']['interpretedValue']
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
    if(location == None or cuisine == None or num_people == None or time == None or email == None or confirmation == "None"):
        validation_result = validate_dining_suggestion(location, cuisine, num_people, time)

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
        push_to_sqs(location,cuisine, time, num_people, email)
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
    if intent_name == 'GreetingIntent':
        return greeting_intent(intent_request)
    elif intent_name == 'DiningSuggestionsIntent':
        return dining_suggestion_intent(intent_request)
    elif intent_name == 'ThankYouIntent':
        return thank_you_intent(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


def lambda_handler(event, context=[]):
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    print(json.dumps(event))
    toRet = dispatch(event)
    print(json.dumps(toRet))
    return toRet


event = {
    "sessionId": "905418445552116",
    "inputTranscript": "aakar.mutha@nyu.edu",
    "interpretations": [
        {
            "interpretationSource": "Lex",
            "nluConfidence": 1,
            "intent": {
                "confirmationState": "None",
                "name": "DiningSuggestionsIntent",
                "slots": {
                    "Cuisine": {
                        "shape": "Scalar",
                        "value": {
                            "originalValue": "indian",
                            "resolvedValues": [
                                "indian"
                            ],
                            "interpretedValue": "indian"
                        }
                    },
                    "NumberOfPeople": {
                        "shape": "Scalar",
                        "value": {
                            "originalValue": "3",
                            "resolvedValues": [
                                "3"
                            ],
                            "interpretedValue": "3"
                        }
                    },
                    "DiningTime": {
                        "shape": "Scalar",
                        "value": {
                            "originalValue": "3pm",
                            "resolvedValues": [
                                "15:00"
                            ],
                            "interpretedValue": "15:00"
                        }
                    },
                    "email": {
                        "shape": "Scalar",
                        "value": {
                            "originalValue": "aakar.mutha@nyu.edu",
                            "resolvedValues": [
                                "aakar.mutha@nyu.edu"
                            ],
                            "interpretedValue": "aakar.mutha@nyu.edu"
                        }
                    },
                    "Location": {
                        "shape": "Scalar",
                        "value": {
                            "originalValue": "new york",
                            "resolvedValues": [
                                "new york"
                            ],
                            "interpretedValue": "new york"
                        }
                    }
                },
                "state": "InProgress"
            }
        },
        {
            "interpretationSource": "Lex",
            "intent": {
                "confirmationState": "None",
                "name": "FallbackIntent",
                "slots": {},
                "state": "InProgress"
            }
        },
        {
            "interpretationSource": "Lex",
            "nluConfidence": 0.44,
            "intent": {
                "confirmationState": "None",
                "name": "ThankYouIntent",
                "slots": {},
                "state": "InProgress"
            }
        },
        {
            "interpretationSource": "Lex",
            "nluConfidence": 0.24,
            "intent": {
                "confirmationState": "None",
                "name": "GreetingIntent",
                "slots": {},
                "state": "InProgress"
            }
        }
    ],
    "bot": {
        "aliasId": "TSTALIASID",
        "aliasName": "TestBotAlias",
        "name": "restaurantBot2",
        "version": "DRAFT",
        "localeId": "en_US",
        "id": "V4X2CJY560"
    },
    "responseContentType": "text/plain; charset=utf-8",
    "sessionState": {
        "originatingRequestId": "8621aeb1-5a00-4f05-8242-1f94345f5d0d",
        "sessionAttributes": {},
        "activeContexts": [],
        "intent": {
            "confirmationState": "None",
            "name": "DiningSuggestionsIntent",
            "slots": {
                "Cuisine": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "indian",
                        "resolvedValues": [
                            "indian"
                        ],
                        "interpretedValue": "indian"
                    }
                },
                "NumberOfPeople": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "3",
                        "resolvedValues": [
                            "3"
                        ],
                        "interpretedValue": "3"
                    }
                },
                "DiningTime": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "3pm",
                        "resolvedValues": [
                            "15:00"
                        ],
                        "interpretedValue": "15:00"
                    }
                },
                "email": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "aakar.mutha@nyu.edu",
                        "resolvedValues": [
                            "aakar.mutha@nyu.edu"
                        ],
                        "interpretedValue": "aakar.mutha@nyu.edu"
                    }
                },
                "Location": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "new york",
                        "resolvedValues": [
                            "new york"
                        ],
                        "interpretedValue": "new york"
                    }
                }
            },
            "state": "InProgress"
        }
    },
    "messageVersion": "1.0",
    "invocationSource": "DialogCodeHook",
    "transcriptions": [
        {
            "resolvedContext": {
                "intent": "DiningSuggestionsIntent"
            },
            "resolvedSlots": {
                "email": {
                    "shape": "Scalar",
                    "value": {
                        "originalValue": "aakar.mutha@nyu.edu",
                        "resolvedValues": [
                            "aakar.mutha@nyu.edu"
                        ]
                    }
                }
            },
            "transcriptionConfidence": 1,
            "transcription": "aakar.mutha@nyu.edu"
        }
    ],
    "inputMode": "Text"
}

print(lambda_handler(event))