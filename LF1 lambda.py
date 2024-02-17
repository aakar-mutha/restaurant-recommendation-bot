import json
import boto3


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def lambda_handler(event, context):
    # extract intent and parameters from Lex
    intent = event["currentIntent"]["name"]
    slots = event["currentIntent"]["slots"]

    # check which intent was called, and handle it accordingly
    if intent == "GreetingIntent":
        return handle_greeting_intent()
    elif intent == "ThankYouIntent":
        return handle_thank_you_intent()
    else:
        # otherwise, it's the DiningSuggestionsIntent

        # collect parameters from the user
        location = slots['Location']
        cuisine = slots['Cuisine']
        dining_time = slots['DiningTime']
        num_people = slots['NumberOfPeople']
        user_email = slots['Email']

        # push information from user to SQS queue
        push_to_sqs(location, cuisine, dining_time, num_people, user_email)

        # Confirmation message to the user
        response_message = "Thank you for providing the information. We will notify you over email once we have restaurant suggestions."

        # Return the response to Lex
        
        return {
            'dialogAction': {
                'type': 'Close',
                'fulfillmentState': 'Fulfilled',
                'message': {
                    'contentType': 'PlainText',
                    'content': response_message
                }
            }
        }


def handle_greeting_intent():
    # receives request for GreetingIntent and composes a response
    return {
        "statusCode": 200,
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "text": "Hi there, how can I help?"
                },
            }
        ],
    }


def handle_thank_you_intent():
    # receives request for ThankYouIntent and composes a response
    return {
        "statusCode": 200,
        "messages": [
            {
                "type": "unstructured",
                "unstructured": {
                    "text": "You're welcome! If you need any more assistance, feel free to ask."
                },
            }
        ],
    }


def push_to_sqs(location, cuisine, dining_time, num_people, user_email):
    # connect to SQS
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='dining-suggestion-queue')

    # create message body
    message_body = {
        'location': location,
        'cuisine': cuisine,
        'dining_time': dining_time,
        'num_people': num_people,
        'user_email': user_email
    }

    # send message to SQS queue
    response = queue.send_message(MessageBody=json.dumps(message_body))

    # return response
    return response
