from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_lambda as _lambda,
    aws_iam as iam,
)

class LambdaStack(Stack):

    def __init__(self, scope: Construct, id: str, dict1, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Defines an AWS Lambda function
        my_lambda = _lambda.Function(
            self, 'bedrock-agent-txtsql-action',
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset('lambda'),
            handler='lambda.lambda_handler',
            timeout=Duration.seconds(60),
            memory_size=1024,
        )

        # Export the lambda arn
        CfnOutput(self, "LambdaAthenaForBedrockAgent",
            value=my_lambda.function_arn,
            export_name="LambdaAthenaForBedrockAgent"
        )

        self.lambda_arn = my_lambda.function_arn

        # Adding Lambda execution role permissions for the services lambda will interact with.
        add_execution_policy = my_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:*", "athena:*", "s3:*"],
            resources=["*"],
            )
        )  

        # Adding iam managed policies to the Lambda execution role
        my_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3FullAccess')
            )
        my_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonAthenaFullAccess')
            )
        my_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AWSGlueConsoleFullAccess')
            )     
        
        # Add permissions to the Lambda function resource policy. You use a resource-based policy to allow an AWS service to invoke your function.
        add_lambda_resource_policy = my_lambda.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{dict1['region']}:{dict1['account_id']}:agent/*"
        )