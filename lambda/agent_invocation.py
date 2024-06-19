import boto3
from botocore.exceptions import ClientError
import os
import logging
import json

agentId = os.environ["BEDROCK_AGENT_ID"]
agentAliasIdString = os.environ["BEDROCK_AGENT_ALIAS"]
region = os.environ["AWS_REGION"]

agentAliasId = agentAliasIdString[-10:]

agent_response = ""


def handler(event, context):
    
    body = json.loads(event['body'])
    question = body['userPrompt']
    sessionId = body["sessionId"]
    
    print(f"Session: {sessionId} asked question: {question}")

    try: 
        response = askQuestion(question, sessionId)
        return {
            "statusCode": 200,
            "body": json.dumps(response),
            "headers": {
                "Content-Type": "application/json"
            }
        }
    
    except Exception as e:
        return {
            "statusCode": 400,
            "body": {"error": str(e)},
            "headers": {
                "Content-Type": "application/json"
            }
        }


def askQuestion(question, sessionId):

    try:
        client = boto3.client('bedrock-agent-runtime', region_name=region)
        logging.info(f"Invoking agent with question: {question}")
        response = client.invoke_agent(
            agentId=agentId,
            agentAliasId=agentAliasId,
            sessionId=sessionId,
            inputText=question,
        )

        completion = ""

        for event in response.get("completion"):
            chunk = event["chunk"]
            completion = completion + chunk["bytes"].decode()

    except ClientError as e:
        logging.error(f"Couldn't invoke agent. {e}")
        raise
        
    print(completion)
        
    return completion