from aws_cdk import (
    Stack,
    aws_certificatemanager as acm,
    aws_cognito as cognito,
    aws_efs as efs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    Duration as Duration,
    Fn as Fn,
    RemovalPolicy,
    CfnOutput,
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib
import json

import jsonschema

class StreamlitStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, dict1, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        ### 1. Create the ECS service for the Streamlit application

        # Create a Cloudwatch log group for vpc flow logs
        vpc_flow_log_group = logs.LogGroup(self, "vpc-flowlog-group",
            log_group_name=("vpc-flowlog-group-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            log_group_class=logs.LogGroupClass.STANDARD,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Creating the VPC for the ECS service
        vpc = ec2.Vpc(self, "CompanionVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateway_subnets=None,
            subnet_configuration=[ec2.SubnetConfiguration(name="public",subnet_type=ec2.SubnetType.PUBLIC,cidr_mask=24)]
        )
        
        vpc.add_flow_log("FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group=vpc_flow_log_group),
            traffic_type=ec2.FlowLogTrafficType.ALL
        )

        # Was the certificate argument been added as part of the cdk deploy? If so then a certification will be created and attached to the alb
        acm_certificate_arn = self.node.try_get_context('acm_certificate_arn')

        # Use the ApplicationLoadBalancedFargateService L3 construct to create the application load balanced behind an ALB
        load_balanced_service = ecs_patterns.ApplicationLoadBalancedFargateService(self, "CompanionService",
            vpc=vpc,
            cpu=1024,
            memory_limit_mib=4096,
            desired_count=1,
            public_load_balancer=True,
            assign_public_ip=True,
            enable_execute_command=True,
            certificate=(acm.Certificate.from_certificate_arn(self, "certificate", certificate_arn=acm_certificate_arn) if acm_certificate_arn else None),
            redirect_http=(True if acm_certificate_arn else False),
            load_balancer_name=("saas-companion-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            # Builds and imports the container image directly from the local directory (requires Docker to be installed on the environment executing cdk deploy)
                image=ecs.ContainerImage.from_asset("streamlit"),
                environment={
                    "STREAMLIT_SERVER_RUN_ON_SAVE": "true",
                    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                    "STREAMLIT_THEME_BASE": "light",
                    "STREAMLIT_THEME_TEXT_COLOR": "#00617F",
                    "STREAMLIT_THEME_FONT": "sans serif",
                    "STREAMLIT_THEME_BACKGROUND_COLOR": "#C1C6C8",
                    "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR": "#ffffff",
                    "STREAMLIT_THEME_PRIMARY_COLOR": "#C1C6C8",
                    "BEDROCK_AGENT_ID": Fn.import_value("BedrockAgentID"),
                    "BEDROCK_AGENT_ALIAS": Fn.import_value("BedrockAgentAlias"),
                    "AWS_REGION": self.region,
                    "AWS_ACCOUNT_ID": self.account,
                }
            )
        )   

        # Export the ALB Name
        CfnOutput(self, "ALBName",
            value=load_balanced_service.load_balancer.load_balancer_name,
            export_name="ALBName"
        )
        
        # Adding the necessary permissions to the ECS task role to interact with the services
        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
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
                    "athena:ListTableMetadata"
                ],
                resources=["*"]
            )
        )

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(

                actions=[
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                    "glue:BatchGetPartition"
                ],
                resources=["*"]
            )
        )

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                    "bedrock:*",
                    "kms:DescribeKey",
                    "iam:ListRoles",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "iam:PassRole"
                ],
                resources=["*"]
            )
        )

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                "cloudwatch:DescribeAlarmsForMetric",
                "cloudwatch:GetMetricData",
                "ec2:CreateNetworkInterface",
                "ec2:DeleteNetworkInterface",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeNetworkInterfaceAttribute",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcAttribute",
                "ec2:DescribeVpcs",
                "ec2:ModifyNetworkInterfaceAttribute",
                "elasticfilesystem:Backup",
                "elasticfilesystem:CreateFileSystem",
                "elasticfilesystem:CreateMountTarget",
                "elasticfilesystem:CreateTags",
                "elasticfilesystem:CreateAccessPoint",
                "elasticfilesystem:CreateReplicationConfiguration",
                "elasticfilesystem:DeleteFileSystem",
                "elasticfilesystem:DeleteMountTarget",
                "elasticfilesystem:DeleteTags",
                "elasticfilesystem:DeleteAccessPoint",
                "elasticfilesystem:DeleteFileSystemPolicy",
                "elasticfilesystem:DeleteReplicationConfiguration",
                "elasticfilesystem:DescribeAccountPreferences",
                "elasticfilesystem:DescribeBackupPolicy",
                "elasticfilesystem:DescribeFileSystems",
                "elasticfilesystem:DescribeFileSystemPolicy",
                "elasticfilesystem:DescribeLifecycleConfiguration",
                "elasticfilesystem:DescribeMountTargets",
                "elasticfilesystem:DescribeMountTargetSecurityGroups",
                "elasticfilesystem:DescribeReplicationConfigurations",
                "elasticfilesystem:DescribeTags",
                "elasticfilesystem:DescribeAccessPoints",
                "elasticfilesystem:ModifyMountTargetSecurityGroups",
                "elasticfilesystem:PutAccountPreferences",
                "elasticfilesystem:PutBackupPolicy",
                "elasticfilesystem:PutLifecycleConfiguration",
                "elasticfilesystem:PutFileSystemPolicy",
                "elasticfilesystem:UpdateFileSystem",
                "elasticfilesystem:UpdateFileSystemProtection",
                "elasticfilesystem:TagResource",
                "elasticfilesystem:UntagResource",
                "elasticfilesystem:ListTagsForResource",                
                "elasticfilesystem:Restore",
                "kms:DescribeKey",
                "kms:ListAliases"
                ],
                resources=["*"]
            )
        )

        load_balanced_service.task_definition.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=[
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:ListMultipartUploadParts",
                    "s3:AbortMultipartUpload",
                    "s3:CreateBucket",
                    "s3:PutObject"
                ],
                resources=["*"]
            )
        )

        # Nag Suppressions in place to accommodate the items flagged. This must be addressed for a workload entering production.
        NagSuppressions.add_resource_suppressions(
            load_balanced_service.task_definition.task_role,
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="Role is controlled to services, and actions where limited service API calls required. Where wildcards are used, these are prefixed with resources partial or complete ARNs.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            load_balanced_service.task_definition.execution_role,
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="Role is default via the generating construct.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            load_balanced_service.load_balancer,
            [NagPackSuppression(id="AwsSolutions-ELB2", reason="Load Balancer not mission criticial, access logs not needed for POC."),NagPackSuppression(id="AwsSolutions-EC23", reason="Expected public access for this POC. Is reinforced by Cognito.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            load_balanced_service.task_definition,
            [NagPackSuppression(id="AwsSolutions-ECS2", reason="Data is non-sensitive. As this is a POC environment variables are OK.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            load_balanced_service.cluster,
            [NagPackSuppression(id="AwsSolutions-ECS4", reason="Container insights is not required for POC environment.")],
            True
        )

        ### 2. Creating optinoal resources based on user context variables 

        # OPTION: Was the "dev" variable passed in as part of the cdk deploy --context? 
        # If so then an EFS file system will be created and mounted into the task definition for easy access to the Streamlit application code.

        # Creating an EFS file system to help during the development phase. The EFS file system is then mounted into the task definition for easy access to the Streamlit application code.
        dev = self.node.try_get_context('dev')
        if dev:

            efs_file_system = efs.FileSystem(self, "FileSystem",
                                            vpc=vpc,
                                            allow_anonymous_access=True,
                                            encrypted=True,
                                            security_group=security_group,
                                            removal_policy=RemovalPolicy.DESTROY
                                            )
            
            load_balanced_service.task_definition.add_volume(
                name="my-efs-volume",
                efs_volume_configuration=ecs.EfsVolumeConfiguration(
                    file_system_id=efs_file_system.file_system_id
                )
            )
            
            # Mounting the EFS file system root volume into the container
            # As the EFS file system is empty the container wont see the app files. Use the cloud9 instace to copy the app files into it for development purposes.
            # For production, the EFS file system and the countainer mount wont be necessary as the container image will have the final app files already.  
            container_definition = load_balanced_service.task_definition.default_container
            container_definition.add_mount_points(
                ecs.MountPoint(
                    container_path="/usr/src",
                    source_volume="my-efs-volume",
                    read_only=False
                )
            )

            # Creating a cloud9 environment for the development phase
            cloud9 = ec2.Instance(self, "Cloud9",
                instance_type=ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE2,
                    ec2.InstanceSize.MICRO
                ),
                machine_image=ec2.MachineImage.latest_amazon_linux(),
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                security_group=security_group,
                key_name="bedrock",
                block_devices=[ec2.BlockDevice(device_name="/dev/xvda", volume=ec2.BlockDeviceVolume.ebs(8, encrypted=True))],
                user_data=ec2.UserData.for_linux()
            )

            # Adding an ingress rule to the security group to allow inbound NFS traffic
            security_group = load_balanced_service.service.connections.security_groups[0]
            security_group.add_ingress_rule(
                ec2.Peer.ipv4(vpc.vpc_cidr_block), 
                ec2.Port.tcp(2049), 
                description="Allow inbound NFS traffic"
                )
            security_group.add_ingress_rule(
                ec2.Peer.ipv4("0.0.0.0/0"),
                ec2.Port.tcp(2049),
                description="Allow inbound NFS traffic from anywhere"            
                )


        # OPTION: Was the "email" variable passed in as part of the cdk deploy --context? 
        # If so, then authentication will be applied to the ALB.
        email_address = self.node.try_get_context('email_address')

        if email_address:
            # Are we using a custom domain name?
            custom_domain_name = self.node.try_get_context('domain_name')

            #Declare variables here for logic that is reused
            domain_name = (custom_domain_name if custom_domain_name else load_balanced_service.load_balancer.load_balancer_dns_name)
            full_domain_name = ("https://" if acm_certificate_arn else "http://") + domain_name

            #Create a Cognito User Pool for user authentication
            user_pool = cognito.UserPool(self, "UserPool",
                self_sign_up_enabled=False,
                user_invitation=cognito.UserInvitationConfig(
                    email_subject="New Account",
                    email_body="""Hello,
                    
                    You've been granted permission to access a application:
                    """ + full_domain_name + """

                    Your username is '<b>{username}</b>' and your temporary password is <b>{####}</b>"""
                ),
                auto_verify=cognito.AutoVerifiedAttrs(email=True),
                password_policy=cognito.PasswordPolicy(min_length=8, require_digits=True, require_symbols=True, require_lowercase=True, require_uppercase=True),
                advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED
            )

            NagSuppressions.add_resource_suppressions(
                user_pool,
                [NagPackSuppression(id="AwsSolutions-COG2", reason="MFA is not required for the prototype.")],
                True
            )

            # Create a Cognito User Pool Domain for the ALB to use for authentication
            user_pool_domain = user_pool.add_domain("UserPoolDomain",
                cognito_domain=cognito.CognitoDomainOptions(
                    domain_prefix="saas-acs-genai-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]
                )
            )

            # Create a Cognito User Pool Client for the ALB to use for authentication. This is required for the ALB to use the Cognito User Pool.
            user_pool_client = user_pool.add_client("NetworkAssistantUserPoolClient",
                o_auth=cognito.OAuthSettings(
                    scopes=[
                        cognito.OAuthScope.OPENID
                    ],
                    callback_urls=[
                        full_domain_name + "/oauth2/idpresponse"
                    ],
                    flows=cognito.OAuthFlows(authorization_code_grant=True)
                ),
                auth_flows=cognito.AuthFlow(user_password=True),
                generate_secret=True
            ) 

            # Create a Cognito User Pool User based on the provided email address for the ALB to use for authentication. This is required for the ALB to use the Cognito User Pool. This user is the only user that will be able to access the ALB.
            cognito.CfnUserPoolUser(self, "UserPoolUser",
                desired_delivery_mediums=["EMAIL"],
                user_attributes=[cognito.CfnUserPoolUser.AttributeTypeProperty(
                    name="email",
                    value=email_address
                )],
                username="dashboard_user",
                user_pool_id=user_pool.user_pool_id
            )

            # Apply the Cognito User Pool to the ALB. This will cause the ALB to use the Cognito User Pool for authentication. This is required for the ALB to use the Cognito User Pool. This user is the only user that will be able to access the ALB.
            load_balanced_service.listener.node.default_child.default_actions = [
                {
                    "order": 1,
                    "type": "authenticate-cognito",
                    "authenticateCognitoConfig": {
                        "userPoolArn": user_pool.user_pool_arn,
                        "userPoolClientId": user_pool_client.user_pool_client_id,
                        "userPoolDomain": user_pool_domain.domain_name,
                    }
                },
                {
                    "order": 2,
                    "type": "forward",
                    "targetGroupArn": load_balanced_service.target_group.target_group_arn
                }
            ]

            load_balanced_service.load_balancer.connections.allow_to_any_ipv4(ec2.Port.tcp(443))
            
        ### 3. Creating an api gateway that web applications can access to invoke the agent
        
        # Create the lambda function that will be invoked by the API Gateway
        agent_invocation_lambda = _lambda.Function(
            self, 'agent-invocation-lambda',
            runtime=_lambda.Runtime.PYTHON_3_12,
            code=_lambda.Code.from_asset('lambda'),
            handler='agent_invocation.handler',
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "BEDROCK_AGENT_ID": Fn.import_value("BedrockAgentID"),
                "BEDROCK_AGENT_ALIAS": Fn.import_value("BedrockAgentAlias"),
                "REGION": dict1['region'],
            },
            current_version_options=_lambda.VersionOptions(
                removal_policy=RemovalPolicy.RETAIN,
                provisioned_concurrent_executions=2
                ),
            )

        # Define bedrock permission for the Lambda function. This function calls the Bedrock API to invoke the agent and must have the "bedrock" permissions. 
        agent_invocation_lambda.role.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                    "bedrock:InvokeAgent"
                ],
            resources=[
                "*"
                ],
            )
        )

        # Export the lambda arn
        CfnOutput(self, "LambdaAgentInvocationHandlerArn",
            value=agent_invocation_lambda.function_arn,
            export_name="LambdaAgentInvocationHandlerArn"
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/StreamlitStack/agent-invocation-lambda/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="The agent does need to invoke changing agents aliases and the wildcard is needed to avoid unreasonable toil.")],
            True
        )

        # Create an access log group for the API Gateway access logs
        apigw_access_loggroup = logs.LogGroup(self, "apigw-log-group",
            log_group_name=("apigw-access-log-group-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            log_group_class=logs.LogGroupClass.STANDARD,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        ) 

        # Create a new API Gateway, as a public endpoint. Defines an API Gateway REST API with AWS Lambda proxy integration.
        agent_apigw_endpoint = apigw.LambdaRestApi(self, "agent_apigw_endpoint",
            rest_api_name="agent_apigw_endpoint",
            handler=agent_invocation_lambda,
            description="This is the API Gateway endpoint that takes in a user prompt and retuns an agent response.",
            cloud_watch_role=True,
            proxy=False,
            deploy=True,
            endpoint_types=[apigw.EndpointType.EDGE],
            deploy_options=apigw.StageOptions(
                stage_name="question",
                logging_level=apigw.MethodLoggingLevel.INFO,
                access_log_destination=apigw.LogGroupLogDestination(apigw_access_loggroup),
                data_trace_enabled=True,
                caching_enabled=False,
                metrics_enabled=True,
            ),
            integration_options=apigw.LambdaIntegrationOptions(
                timeout=Duration.seconds(29),
            )
        )

        plan = apigw.UsagePlan(self, "BedrockUsagePlan",
            name="BedrockUsagePlan",
            description="This is the usage plan for the Bedrock API Gateway endpoint.",
            quota=apigw.QuotaSettings(
                limit=1000,
                period=apigw.Period.DAY,
                offset=0
            ),
            throttle=apigw.ThrottleSettings(
                rate_limit=100,
                burst_limit=50
            ),
            api_stages=[apigw.UsagePlanPerApiStage(
                api=agent_apigw_endpoint,
                stage=agent_apigw_endpoint.deployment_stage
            )]
        )
        
        # Create an API key for the API Gateway endpoint. Requester must add the x-api-key header with the key to gain access.
        bedrock_api_key = apigw.ApiKey(self, "BedrockAPIKey",
                api_key_name="BedrockAPIKey",
                enabled=True,
                description="This is the API key for the Bedrock API Gateway endpoint.",    
            )
        plan.add_api_key(bedrock_api_key)

        # Create request validator for the API Gateway endpoint
        request_model = agent_apigw_endpoint.add_model("BrRequestValidatorModel",
            content_type="application/json",
            model_name="BrRequestValidatorModel",
            description="This is the request validator model for the Bedrock API Gateway endpoint.",
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title="postRequestValidatorModel",
                type=apigw.JsonSchemaType.OBJECT,
                required=["sessionId", "userPrompt"],
                properties={
                    "sessionId": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, min_length=2, max_length=32),
                    "userPrompt": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, min_length=1, max_length=500),
                }
            )
        )
        
        # Add the POST method that references the request validator and sets the API key as required
        agent_apigw_endpoint.root.add_method(
            http_method='POST', 
            api_key_required=True,
            request_validator_options=apigw.RequestValidatorOptions(
                request_validator_name="PostRequestValidator",
                validate_request_body=True,
                validate_request_parameters=False,
            ),
            request_models={"application/json": request_model},
        )

        # Adding documentation to the API Gateway endpoint
        properties_json = '{"info":"This is the API Gateway endpoint that takes in a user prompt and retuns an agent response."}'

        cfn_documentation_part = apigw.CfnDocumentationPart(self, "MyCfnDocumentationPart",
            location=apigw.CfnDocumentationPart.LocationProperty(
                type="API"
            ),
            properties=properties_json,
            rest_api_id=agent_apigw_endpoint.rest_api_id
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/StreamlitStack/agent_apigw_endpoint/CloudWatchRole/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="The service role permission for cloudwatch logs are handled by the LambdaRestApi Construct.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            agent_apigw_endpoint,
            [NagPackSuppression(id="AwsSolutions-APIG2", reason="Request validation is in fact enabled."), NagPackSuppression(id="AwsSolutions-APIG4", reason="We do not need an authorizer at this point."), NagPackSuppression(id="AwsSolutions-COG4", reason="We may or not use a Cognito user pool authorizer.")],
            True
        )