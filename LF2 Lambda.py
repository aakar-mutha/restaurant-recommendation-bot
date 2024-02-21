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
        
def lambda_handler(event,context):
    print(json.dumps(event))
    records = event.get('Records',None)
    if(len(records) > 0):
        for record in records:
            body = json.loads(record.get('body', None))
            if(body != None):
                cuisine = body.get('cuisine', None)
                email = body.get('email', None)
                hits = queryElasticSearch(cuisine)
                sendEmail(hits,email)