import json
from pprint import pprint
import boto3


def lambda_handler(event, context=[]):
    lexClient = boto3.client("lexv2-runtime")
    messages = event.get("messages", None)

    if messages is not None:
        for i in messages:
            response = lexClient.recognize_text(
                botId="WMPBTRYOED",
                botAliasId="TSEQEDBCNE",
                localeId="en_US",
                sessionId="test1",
                text=i["unstructured"]["text"],
            )
            pprint(response)
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
#             "unstructured": {"text": "can i get some suggestions on restaurants?"},
#         }
#     ]
# }

# pprint(lambda_handler(event=event))
