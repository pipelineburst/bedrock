from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_lambda as _lambda,
    aws_iam as iam,
    Fn as Fn,
)
from constructs import Construct
import os

class LambdaStack(Stack):

    def __init__(self, scope: Construct, id: str, dict1, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ### Define a Lambda function for the agent to interact with Athena

        # Defines an AWS Lambda function
        athena_lambda = _lambda.Function(
            self, 'athena-lambda-action',
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset('lambda'),
            handler='lambda_athena.handler',
            timeout=Duration.seconds(60),
            memory_size=4048,
        )

        # Export the lambda arn
        CfnOutput(self, "LambdaAthenaForBedrockAgent",
            value=athena_lambda.function_arn,
            export_name="LambdaAthenaForBedrockAgent"
        )

        self.athena_lambda_arn = athena_lambda.function_arn

        # Adding Lambda execution role permissions for the services lambda will interact with.
        add_execution_policy = athena_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:*", "athena:*", "s3:*"],
            resources=["*"],
            )
        )  

        # Adding iam managed policies to the Lambda execution role
        athena_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3FullAccess')
            )
        athena_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonAthenaFullAccess')
            )
        athena_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AWSGlueConsoleFullAccess')
            )     
        
        # Add permissions to the Lambda function resource policy. You use a resource-based policy to allow an AWS service to invoke your function.
        add_lambda_resource_policy = athena_lambda.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{dict1['region']}:{dict1['account_id']}:agent/*"
        )
        
        ### Define a Lambda function for the agent to seatch the web

        # Create a Lambda layer
        layer = _lambda.LayerVersion(
            self, 'py-lib-layer',
            code=_lambda.Code.from_asset('assets/lambda_layer_with_py_deps.zip'),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
        )

        # Defines an AWS Lambda function
        search_lambda = _lambda.Function(
            self, 'search-lambda-action',
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset("lambda"),
            handler='lambda_search.handler',
            timeout=Duration.seconds(60),
            memory_size=4048,
        )
        
        # Add the layer to the search lambda function
        search_lambda.add_layers(layer)

        # Export the lambda arn
        CfnOutput(self, "LambdaSearchForBedrockAgent",
            value=search_lambda.function_arn,
            export_name="LambdaSearchForBedrockAgent"
        )

        self.search_lambda_arn = search_lambda.function_arn

        # Adding Lambda execution role permissions for the services lambda will interact with.
        add_execution_policy = search_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:*", "athena:*", "s3:*"],
            resources=["*"],
            )
        )  

        # Adding iam managed policies to the Lambda execution role
        search_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3FullAccess')
            )
        search_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonAthenaFullAccess')
            )
        search_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AWSGlueConsoleFullAccess')
            )     
        
        # Add permissions to the Lambda function resource policy. You use a resource-based policy to allow an AWS service to invoke your function.
        add_lambda_resource_policy = search_lambda.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{dict1['region']}:{dict1['account_id']}:agent/*"
        )
        
        # Create add athena destination bucket name as environment variables to the athena lambda function
        athena_dest_bucket = Fn.import_value("AthenaDestinationBucketName")
        athena_lambda.add_environment("ATHENA_DEST_BUCKET", athena_dest_bucket)