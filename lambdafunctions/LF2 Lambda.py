import boto3
from botocore.exceptions import ClientError
import requests
from opensearchpy import OpenSearch
import json

SENDER = "aakar.mutha@nyu.edu"
AWS_REGION = "us-east-1"

# The subject line for the email.
SUBJECT = "Delicious Food awaits you."

host = 'search-cloud-hw-1-43gl3ui4fy5t6aqdiv2ddgoo7a.aos.us-east-1.on.aws' # cluster endpoint, for example: my-test-domain.us-east-1.es.amazonaws.com
region = 'us-east-1'
service = 'aos'
auth = ('cloud', 'Cloud-hw1') 
client = OpenSearch(
        hosts = [{'host': host, 'port': 443}],
        http_compress = True, # enables gzip compression for request bodies
        http_auth = auth,
        use_ssl = True,
        verify_certs = True,
        ssl_assert_hostname = False,
        ssl_show_warn = False
    )

def queryElasticSearch(cuisine):
    query = {
        'size': 5,
        'query': {
            'multi_match': {
            'query': cuisine,
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
    
    return response['hits']['hits']

def sendEmail(hits,email):
    message = "Hi, following are the restaurants we recommend according to your recent interaction:\n"

    counter = 1
    for i in hits:
        data = i['_source']
        message += f"{counter}. " + data['name'] + " located at " + data['address'] + "\n"
        counter+=1

        message += "Thank you for using RestaurantBot!\nSee you again (:"
        print(message)
        
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses',region_name=AWS_REGION)

    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    email,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': CHARSET,
                        'Data': message,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])


def saveUserState(body):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('user-data')
    response = table.put_item(
        Item=body
    )
    print(response)

def lambda_handler(event,context):
    sqs_client = boto3.client('sqs')

    # SQS queue URL
    queue_url = 'https://sqs.us-east-1.amazonaws.com/905418445552/dining-suggestion-queue'

    # Receive messages from the queue
    response = sqs_client.receive_message(
        QueueUrl=queue_url,
        AttributeNames=['All'],
    )
    print(json.dumps(response))
    messages = response.get('Messages',None)
    
    if(messages != None):
        for message in messages:
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
            body = json.loads(message.get('Body',None))
            if(body != None):
                saveUserState(body)
                cuisine = body.get('cuisine', None)
                email = body.get('email', None)
                hits = queryElasticSearch(cuisine)
                sendEmail(hits,email)