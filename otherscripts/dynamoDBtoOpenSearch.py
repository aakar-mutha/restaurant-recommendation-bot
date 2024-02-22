import OpenSearch
from pprint import pprint

HOST = 'search-cloud-hw-1-43gl3ui4fy5t6aqdiv2ddgoo7a.aos.us-east-1.on.aws' # cluster endpoint, for example: my-test-domain.us-east-1.es.amazonaws.com
REGION = 'us-east-1'
SERVICE = 'aos'
# credentials = boto3.Session().get_credentials()
# auth = AWSV4SignerAuth(credentials, region, service)
AUTH = ('cloud', 'Cloud-hw1') 
INDEX = 'restaurant-index'

def createClient():
    client = OpenSearch(
        hosts = [{'host': HOST, 'port': 443}],
        http_compress = True, # enables gzip compression for request bodies
        http_auth = AUTH,
        use_ssl = True,
        verify_certs = True,
        ssl_assert_hostname = False,
        ssl_show_warn = False
    )
    return client

def createIndex(client):
    
    index_name = INDEX
    index_body = {
        'settings': {
            'index': {
            'number_of_shards': 4
            }
        }
    }
    try:
        response = client.indices.create(index_name, body=index_body)
        print("Index Creation Failed")

    except Exception as e:
        print(f"An exception occured : {e}")
    