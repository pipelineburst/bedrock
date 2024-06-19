import boto3
from time import sleep
import os

# Initialize the Athena client
athena_client = boto3.client('athena')

def handler(event, context):
    print(event)

    def athena_query_handler(event):
        # Fetch parameters for the new fields

        # Extracting the SQL query. THe bedrock function call will pass the query in the request body
        query = event['requestBody']['content']['application/json']['properties'][0]['value']

        print("the received QUERY:",  query)
        
        # Adding the athena destination s3 bucket we need for the boto athena client call
        s3_output = 's3://' + os.environ["ATHENA_DEST_BUCKET"]
        wg_name = os.environ["ATHENA_WORKGROUP"]

        # Execute the query and wait for completion
        execution_id = execute_athena_query(query, s3_output, wg_name)
        result = get_query_results(execution_id)

        return result

    def execute_athena_query(query, s3_output, wg_name):
        response = athena_client.start_query_execution(
            QueryString=query,
            ResultConfiguration={
                'OutputLocation': s3_output,
                },
            WorkGroup=wg_name,
            ResultReuseConfiguration={
                'ResultReuseByAgeConfiguration': {
                    'Enabled': True,
                    'MaxAgeInMinutes': 60
                    }
                }
        )
        return response['QueryExecutionId']

    def check_query_status(execution_id):
        response = athena_client.get_query_execution(QueryExecutionId=execution_id)
        return response['QueryExecution']['Status']['State']

    def get_query_results(execution_id):
        while True:
            status = check_query_status(execution_id)
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            sleep(1)  # Polling interval

        if status == 'SUCCEEDED':
            return athena_client.get_query_results(QueryExecutionId=execution_id)
        else:
            raise Exception(f"Query failed with status '{status}'")

    action_group = event.get('actionGroup')
    api_path = event.get('apiPath')

    print("api_path: ", api_path)

    result = ''
    response_code = 200


    if api_path == '/athenaQuery':
        result = athena_query_handler(event)
    else:
        response_code = 404
        result = {"error": f"Unrecognized api path: {action_group}::{api_path}"}

    response_body = {
        'application/json': {
            'body': result
        }
    }

    action_response = {
        'actionGroup': action_group,
        'apiPath': api_path,
        'httpMethod': event.get('httpMethod'),
        'httpStatusCode': response_code,
        'responseBody': response_body
    }

    api_response = {'messageVersion': '1.0', 'response': action_response}
    return api_response