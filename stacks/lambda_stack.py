from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_lambda as _lambda,
    aws_iam as iam,
    Fn as Fn,
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct

class LambdaStack(Stack):

    def __init__(self, scope: Construct, id: str, dict1, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ### 1. Define a Lambda function for the agent to interact with Athena

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
        athena_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                    "athena:BatchGetQueryExecution",
                    "athena:CancelQueryExecution",
                    "athena:GetCatalogs",
                    "athena:GetExecutionEngine",
                    "athena:GetExecutionEngines",
                    "athena:GetNamespace",
                    "athena:GetNamespaces",
                    "athena:GetQueryExecution",
                    "athena:GetQueryExecutions",
                    "athena:GetQueryResults",
                    "athena:GetQueryResultsStream",
                    "athena:GetTable",
                    "athena:GetTables",
                    "athena:ListQueryExecutions",
                    "athena:RunQuery",
                    "athena:StartQueryExecution",
                    "athena:StopQueryExecution",
                    "athena:ListWorkGroups",
                    "athena:ListEngineVersions",
                    "athena:GetWorkGroup",
                    "athena:GetDataCatalog",
                    "athena:GetDatabase",
                    "athena:GetTableMetadata",
                    "athena:ListDataCatalogs",
                    "athena:ListDatabases",
                    "athena:ListTableMetadata",
                ],
            resources=["*"],
            )
        )  

        athena_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:ListMultipartUploadParts",
                    "s3:AbortMultipartUpload",
                    "s3:CreateBucket",
                    "s3:PutObject",
                    "s3:PutBucketLogging",
                    "s3:PutBucketVersioning",
                    "s3:PutBucketNotification",
                ],
            resources=[
                    f"arn:aws:s3:::{Fn.import_value('AthenaDestinationBucketName')}",
                    f"arn:aws:s3:::{Fn.import_value('AthenaDestinationBucketName')}/*",
                    Fn.import_value('DataSetBucketArn'),
                    f"{Fn.import_value('DataSetBucketArn')}/*",
                    ],
            )
        )  

        athena_lambda.add_to_role_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                    "glue:BatchGetPartition"
                ],
            resources=[
                    f"arn:aws:glue:{dict1['region']}:{dict1['account_id']}:catalog",
                    f"arn:aws:glue:{dict1['region']}:{dict1['account_id']}:database/{Fn.import_value('GlueDatabaseName')}",
                    f"arn:aws:glue:{dict1['region']}:{dict1['account_id']}:table/{Fn.import_value('GlueDatabaseName')}/*"
                    ],
            )
        )  
        
        # Add permissions to the Lambda function resource policy. You use a resource-based policy to allow an AWS service to invoke your function.
        athena_lambda.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{dict1['region']}:{dict1['account_id']}:agent/*"
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/LambdaStack/athena-lambda-action/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by the Construct.")],
            True
        )
        
        # Create athena environment variables for the athena lambda function
        athena_dest_bucket = Fn.import_value("AthenaDestinationBucketName")
        athena_lambda.add_environment("ATHENA_DEST_BUCKET", athena_dest_bucket)       
        
        athena_workgroup = Fn.import_value("AthenaWorkGroupName")
        athena_lambda.add_environment("ATHENA_WORKGROUP", athena_workgroup) 
        
        ### 2. Define a Lambda function for the agent to search the web

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

        # Add permissions to the Lambda function resource policy. You use a resource-based policy to allow an AWS service to invoke your function.
        add_lambda_resource_policy = search_lambda.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{dict1['region']}:{dict1['account_id']}:agent/*"
        )
    
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/LambdaStack/search-lambda-action/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by the Construct.")],
            True
        )