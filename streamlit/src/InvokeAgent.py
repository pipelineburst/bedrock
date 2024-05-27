import boto3
from botocore.exceptions import ClientError
import os
import logging

agentId = os.environ["BEDROCK_AGENT_ID"]
agentAliasIdString = os.environ["BEDROCK_AGENT_ALIAS"]
agentAliasId = agentAliasIdString[-10:]
sessionId = "MYSESSION"

theRegion = os.environ["AWS_REGION"]
region = os.environ["AWS_REGION"]
llm_response = ""

def askQuestion(question, endSession=False):

    """
    Sends a prompt for the agent to process and respond to.

    :param agent_id: The unique identifier of the agent to use.
    :param agent_alias_id: The alias of the agent to use.
    :param session_id: The unique identifier of the session. Use the same value across requests to continue the same conversation.
    :param prompt: The prompt that you want Claude to complete.
    :return: Inference response from the model.
    """

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

def agent_handler(event, context):
    
    """
    Takes in an event body containint the prompt and returns the response from the agent.

    :param event: A dict that contains the prompt and session id.
    :param context: The context of the prompt.
    """
    
    sessionId = event["sessionId"]
    question = event["question"]
    endSession = False
    
    print(f"Session: {sessionId} asked question: {question}")
    
    try:
        if (event["endSession"] == "true"):
            endSession = True
    except:
        endSession = False

    try: 
        response = askQuestion(question, endSession)
        return response
    
    except Exception as e:
        return "Oh no, an error occurred with the resonse. Please rerun the query... :sparkles:"
