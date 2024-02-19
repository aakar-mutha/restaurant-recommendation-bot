import json
import boto3


def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    global USER_EMAIL_ADDRESS
    USER_EMAIL_ADDRESS = 'mj3102@nyu.edu'  # set default email to send to
    print(f"default user email address {USER_EMAIL_ADDRESS}")

    # extract intent, session attributes, and parameters from Lex
    intent = event["sessionState"]["intent"]["name"]
    print(f"intent {intent}")
    session_attributes = event["sessionState"]["sessionAttributes"]
    print(f"session attributes {session_attributes}")

    # check which intent was called, and handle it accordingly
    if intent == "GreetingIntent":
        lex_session_id = event['sessionId']
        print("intent is GreetingIntent")
        print(f"user sessionId {lex_session_id}")
        USER_EMAIL_ADDRESS = event["sessionState"]["intent"]['slots']['Email']['value']['interpretedValue']
        
        if event["sessionState"]["intent"]['slots']['Email'] is None:
            return {
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": "Please provide your email address."
                    }
                ],
                "sessionState": {
                    "intent": {
                        "name": "GreetingIntent",
                        "state": "InProgress"
                    },
                    "sessionAttributes": {
                        "USER_EMAIL_ADDRESS": USER_EMAIL_ADDRESS
                    }
                }
            }
            
        else:
            print(f"user session email is {USER_EMAIL_ADDRESS}")
    
            # Store the user's email in DynamoDB with Lex session ID
            push_user_email_to_dynamodb(USER_EMAIL_ADDRESS, lex_session_id)
            print("user email sent to DynamoDB")
    
            # Return a success response to Lex
            return {
                "messages": [
                    {
                        "contentType": "PlainText",
                        "content": "Thank you for providing your email address."
                    }
                ],
                "sessionState": {
                    "dialogAction": {
                        "type": "ConfirmIntent",
                        "intent": {
                            "name": "GreetingIntent",
                            "slots": {
                                "Email": USER_EMAIL_ADDRESS
                            }
                        }
                    },
                    "intent": {
                        "name": "GreetingIntent",
                        "state": "Fulfilled",
                    },
                    "sessionAttributes": {
                        "USER_EMAIL_ADDRESS": USER_EMAIL_ADDRESS
                    }
                }
            }


    elif intent == "ThankYouIntent":
        return handle_thank_you_intent()
    elif intent == "DiningSuggestionsIntent":
        # otherwise, it's the DiningSuggestionsIntent
        print("intent is DiningSuggestionsIntent")
        
        USER_EMAIL_ADDRESS = session_attributes.get("USER_EMAIL_ADDRESS", None)
        print(f"Getting email address from session attributes {USER_EMAIL_ADDRESS}")
        
        if USER_EMAIL_ADDRESS:
            # USER_EMAIL_ADDRESS exists, we continue with DiningSuggestionIntent
        
            # collect parameters from the user
            slots = event["proposedNextState"]["intent"]["slots"]
            location = slots['Location']
            cuisine = slots['Cuisine']
            dining_time = slots['DiningTime']
            num_people = slots['NumberOfPeople']
    
            # push information from user to SQS queue
            push_to_sqs(location, cuisine, dining_time, num_people, USER_EMAIL_ADDRESS)
    
            # Confirmation message to the user
            response_message = "We have received your request. We will send you an email shortly with our recommendation."
    
            # Return the response to Lex
            
            return {
              "messages": [
                {
                  "contentType": "PlainText",
                  "content": "We have received your request. We will send you an email shortly with our recommendation."
                }
              ],
              "sessionState": {
                "dialogAction": {
                  "type": "ConfirmIntent",
                  "intent": {
                    "name": "DiningSuggestionsIntent",
                    "state": "Fulfilled",
                    "slots": {
                      "Location": location,
                      "Cuisine": cuisine,
                      "DiningTime": dining_time,
                      "NumberOfPeople": num_people
                    }
                  }
                }
              }
            }
        else:
            # If the email is not available in session attributes, prompt the user to provide it
            return {
                "messages": [
                    {
                        "contentType": "PlainText",
                    }
                ],
                "sessionState": {
                    "intent": {
                        "name": "GreetingIntent",
                        "state": "InProgress"
                    },
                    "sessionAttributes": {
                        "USER_EMAIL_ADDRESS": USER_EMAIL_ADDRESS
                    }
                }
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


def push_user_email_to_dynamodb(email, lex_session_id):
    # store the user's email in DynamoDB
    print(f"pushing email {email} to DynamoDB")
    print(f"pushing session id {lex_session_id} to DynamoDB")

    dynamodb = boto3.resource('dynamodb')
    table_name = 'restaurant-bot-user-states'

    table = dynamodb.Table(table_name)
    print(f"connected to DynamoDB table {table}")

    response = table.put_item(
        Item={
            'email': email,
            'LexSessionId': lex_session_id
        }
    )
    
    print(f"DynamoDB response is {response}")
