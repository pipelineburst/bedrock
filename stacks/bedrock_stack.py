from distutils.log import Log
from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_s3_deployment as s3d,
    aws_s3 as s3,
    aws_logs as logs,
    Fn as Fn,
    custom_resources as cr,
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib

class BedrockStack(Stack):

    def __init__(self, scope: Construct, id: str, dict1, athena_lambda_arn, search_lambda_arn, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        ### 1. Create S3 bucket for the Agent schema assets

        # Imporing and instantiating the access logs bucket so we can write the logs into it
        access_logs_bucket = s3.Bucket.from_bucket_name(self, "AccessLogsBucketName", Fn.import_value("AccessLogsBucketName"))
        # access_logs_bucket.add_to_resource_policy(
        #     iam.PolicyStatement(
        #         effect=iam.Effect.ALLOW,
        #         actions=[
        #             "logs:CreateLogStream", 
        #             "logs:PutLogEvents"
        #             ],
        #         resources=[
        #             Fn.import_value("AccessLogsBucketArn"),
        #             Fn.import_value("AccessLogsBucketArn") + ":*"
        #             ],
        #     )
        # )
        
        # Create S3 bucket for the OpenAPI action group schemas 
        schema_bucket = s3.Bucket(self, "schema-bucket",
            bucket_name=("schema-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="schema-bucket-access-logs/",
            intelligent_tiering_configurations=[
                s3.IntelligentTieringConfiguration(
                name="my_s3_tiering",
                archive_access_tier_time=Duration.days(90),
                deep_archive_access_tier_time=Duration.days(180),
                prefix="prefix",
                tags=[s3.Tag(
                    key="key",
                    value="value"
                )]
             )],      
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=Duration.days(7)
                )
            ],
        )

        # Create S3 bucket policy for bedrock permissions
        add_s3_policy = schema_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:*"],
                resources=[schema_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                )
            )
    
        # Upload schema from asset to S3 bucket
        s3d.BucketDeployment(self, "DataDeployment",
            sources=[s3d.Source.asset("assets/schema/")],
            destination_bucket=schema_bucket,
            destination_key_prefix="schema/"
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by the Construct.")],
            True
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/Resource',
            [NagPackSuppression(id="AwsSolutions-L1", reason="Lambda is owned by AWS construct")],
            True
        )
        
        # Export the schema bucket name
        CfnOutput(self, "APISchemaBucket",
            value=schema_bucket.bucket_name,
            export_name="APISchemaBucket"
        )

        # Create a bedrock agent execution role (aka agent resource role) with permissions to interact with the services. The role name must follow a specific format.
        bedrock_agent_role = iam.Role(self, 'bedrock-agent-role',
            role_name=f'AmazonBedrockExecutionRoleForAgents_' + str(hashlib.sha384(hash_base_string).hexdigest())[:15],
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'),
        )
        
        CfnOutput(self, "BedrockAgentRoleArn",
            value=bedrock_agent_role.role_arn,
            export_name="BedrockAgentRoleArn"
        )

        # Add model invocation inline permissions to the bedrock agent execution role
        bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel", 
                    "bedrock:InvokeModelEndpoint", 
                    "bedrock:InvokeModelEndpointAsync"
                ],
                resources=[
                    "arn:aws:bedrock:{}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0".format(self.region)
                ]
                ,
            )
        )
        
        # Add S3 access inline permissions to the bedrock agent execution role to write logs and access the data buckets
        bedrock_agent_role.add_to_policy(
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
                    schema_bucket.bucket_arn,
                    f"{schema_bucket.bucket_arn}/*",
                    f"arn:aws:s3:::{Fn.import_value('DataSetBucketName')}",
                    f"arn:aws:s3:::{Fn.import_value('DataSetBucketName')}/*",
                    Fn.import_value('DataSetBucketArn'),
                    f"{Fn.import_value('DataSetBucketArn')}/*",
                    ],
            )
        ) 
        
        # Add knowledgebase opensearch serverless inline permissions to the bedrock agent execution role      
        bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["aoss:APIAccessAll"],
                resources=["*"],
            )
        )
        
        # Add lambda inline permissions to the bedrock agent execution role      
        bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                    "lambda:GetFunction"
                    ],
                resources=[
                    Fn.import_value('LambdaAthenaForBedrockAgent'),
                    Fn.import_value('LambdaSearchForBedrockAgent')
                    ],
            )
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/bedrock-agent-role/DefaultPolicy/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="Role is controlled to services, and actions where limited service API calls required. Where wildcards are used, these are prefixed with resources partial or complete ARNs.")],
            True
        )

        ### 2. Creating the agent for bedrock

        # Add instructions for the bedrock agent
        with open('assets/agent_instructions.txt', 'r') as file:
            agent_instruction = file.read()

        # Add schema for the bedrock agent
        with open('assets/schema/athena_ag_schema.json', 'r') as file:
            athena_schema_def = file.read()
            
        with open('assets/schema/search_ag_schema.json', 'r') as file:
            search_schema_def = file.read()

        # Define advanced prompt - pre-processing template - override pre-processing template defaults
        with open('assets/agent_preprocessing_template.json', 'r') as file:
            pre_temp_def = file.read()

        # Define advanced prompt - orchestation template - override orchestration template defaults
        with open('assets/agent_orchenstation_template.json', 'r') as file:
            orc_temp_def = file.read()

        # Define advanced prompt - knowledgebase template - override knowledgebase template defaults
        with open('assets/agent_kb_template.txt', 'r') as file:
            kb_temp_def = file.read()

        # Create a bedrock agent with action groups       
        bedrock_agent = bedrock.CfnAgent(self, 'bedrock-agent',
            agent_name='saas-acs-bedrock-agent',
            description="This is a bedrock agent that can be invoked by calling the bedrock agent alias and agent id.",
            auto_prepare=True,
            foundation_model="anthropic.claude-3-haiku-20240307-v1:0",
            instruction=agent_instruction,
            agent_resource_role_arn=str(bedrock_agent_role.role_arn),
            prompt_override_configuration=bedrock.CfnAgent.PromptOverrideConfigurationProperty(
                prompt_configurations=[
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=orc_temp_def,
                        prompt_type="ORCHESTRATION",
                        prompt_state="ENABLED",
                        prompt_creation_mode="OVERRIDDEN",
                        inference_configuration=bedrock.CfnAgent.InferenceConfigurationProperty(
                            maximum_length=2048,
                            stop_sequences=["</error>","</answer>","</invoke>"],
                            temperature=0,
                            top_k=250,
                            top_p=1,
                            )
                        ),
                    # removing the pre-processing as it adds latency to the agent; typically about 5 seconds, as it results in a bedrock model invocation. See logs.
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=pre_temp_def,
                        prompt_type="PRE_PROCESSING",
                        prompt_state="DISABLED",
                        prompt_creation_mode="OVERRIDDEN",
                        inference_configuration=bedrock.CfnAgent.InferenceConfigurationProperty(
                            maximum_length=2048,
                            stop_sequences=["⏎⏎Human:"],
                            temperature=0,
                            top_k=250,
                            top_p=1,
                            )
                        ),
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=kb_temp_def,
                        prompt_type="KNOWLEDGE_BASE_RESPONSE_GENERATION",
                        prompt_state="ENABLED",
                        prompt_creation_mode="OVERRIDDEN",
                        inference_configuration=bedrock.CfnAgent.InferenceConfigurationProperty(
                            maximum_length=2048,
                            stop_sequences=["⏎⏎Human:"],
                            temperature=0,
                            top_k=250,
                            top_p=1,
                            )
                        )
                ]),
            action_groups=[
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="AthenaToolFunction",
                    description="A Function Tool that can access a network metrics dataset.",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=athena_lambda_arn,
                    ),
                    api_schema=bedrock.CfnAgent.APISchemaProperty(
                        payload=athena_schema_def,
                        ),
                    ),
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="WebsearchToolFunction",
                    description="A Function Tool that can search the web.",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=search_lambda_arn,
                    ),
                    api_schema=bedrock.CfnAgent.APISchemaProperty(
                        payload=search_schema_def,
                        ),
                    )
                ],
        )

        CfnOutput(self, "BedrockAgentID",
            value=bedrock_agent.ref,
            export_name="BedrockAgentID"
        )
        
        CfnOutput(self, "BedrockAgentModelName",
            value=bedrock_agent.foundation_model,
            export_name="BedrockAgentModelName"
        )
        
        CfnOutput(self, "BedrockAgentArn",
            value=bedrock_agent.attr_agent_arn,
            export_name="BedrockAgentArn"
        )          

        self.agent_arn = bedrock_agent.ref

        ### 3. Create an alias for the bedrock agent

        # Create an alias for the bedrock agent        
        cfn_agent_alias = bedrock.CfnAgentAlias(self, "MyCfnAgentAlias",
            agent_alias_name="bedrock-agent-alias",
            agent_id=bedrock_agent.ref,
            description="bedrock agent alias to simplify agent invocation",
            # note: when initially creating the agent alias, the agent version is defined automatically
            # routing_configuration=[bedrock.CfnAgentAlias.AgentAliasRoutingConfigurationListItemProperty(
            #     agent_version="1",
            # )],
            tags={
                "owner": "saas"
            }
        )
        cfn_agent_alias.add_dependency(bedrock_agent)     
        
        agent_alias_string = cfn_agent_alias.ref
        agent_alias = agent_alias_string.split("|")[-1]
        
        CfnOutput(self, "BedrockAgentAlias",
            value=agent_alias,
            export_name="BedrockAgentAlias"
        )

        ### 4. Setting up model invocation logging for Amazon Bedrock
        
        # Create a S3 bucket for model invocation logs
        model_invocation_bucket = s3.Bucket(self, "model-invocation-bucket",
            bucket_name=("model-invocation-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="model-invocation-bucket-access-logs/",
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=Duration.days(14)
                )
            ],
        )
        
        # Create S3 bucket policy for bedrock permissions
        add_s3_policy = model_invocation_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:PutObject"
                ],
                resources=[model_invocation_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                )
            )
        
        # Create a Cloudwatch log group for model invocation logs
        model_log_group = logs.LogGroup(self, "model-log-group",
            log_group_name=("model-log-group-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            log_group_class=logs.LogGroupClass.STANDARD,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create a dedicated role with permissions to write logs to cloudwatch logs.
        invocation_logging_role = iam.Role(self, 'invocation-logs-role',
            role_name=("InvocationLogsRole-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'),
        )

        # Add permission to log role to write logs to cloudwatch
        invocation_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[
                    model_log_group.log_group_arn,
                ]
                ,
            )
        )
        
        # Add permission to log role to write large log objects to S3
        invocation_logging_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "S3:PutObject"
                ],
                resources=[
                    model_invocation_bucket.bucket_arn,
                    model_invocation_bucket.bucket_arn + "/*"
                ]
                ,
            )
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/invocation-logs-role/DefaultPolicy/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="Role is controlled to services, and actions where limited service API calls required. Where wildcards are used, these are prefixed with resources partial or complete ARNs.")],
            True
        )
        
        # Custom resource to enable model invocation logging, as cloudformation does not support this feature at this time
        # Define the request body for the api call that the custom resource will use
        modelLoggingParams = {
            "loggingConfig": { 
                "cloudWatchConfig": { 
                    "largeDataDeliveryS3Config": { 
                        "bucketName": model_invocation_bucket.bucket_name,
                        "keyPrefix": "invocation-logs"
                    },
                    "logGroupName": model_log_group.log_group_name,
                    "roleArn": invocation_logging_role.role_arn
                },
                "embeddingDataDeliveryEnabled": False,
                "imageDataDeliveryEnabled": False,
                "textDataDeliveryEnabled": True
            }
        }

        # Define a custom resource to make an AwsSdk startCrawler call to the Glue API     
        model_logging_cr = cr.AwsCustomResource(self, "ModelLoggingCustomResource",
            on_create=cr.AwsSdkCall(
                service="Bedrock",
                action="putModelInvocationLoggingConfiguration",
                parameters=modelLoggingParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
     
        # Define IAM permission policy for the custom resource    
        model_logging_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:PutModelInvocationLoggingConfiguration", 
                "iam:CreateServiceLinkedRole", 
                "iam:PassRole"
            ],
            resources=[
                "*"
            ],
            )
        )  

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/ModelLoggingCustomResource/CustomResourcePolicy/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by Custom Resource."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )
        
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Contains a resouce wildecard for bedrock as this is a global setting."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )

        ### 5. Enable Guardrails for Amazon Bedrock
                
        # Create a guardrail configuration for the bedrock agent
        cfn_guardrail = bedrock.CfnGuardrail(self, "CfnGuardrail",
            name=("guardrail-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            description="Guardrail configuration for the bedrock agent",
            blocked_input_messaging="I'm sorry, I can't accept your prompt, as your prompt been blocked buy Guardrails.",
            blocked_outputs_messaging="I'm sorry, I can't answer that, as the response has been blocked buy Guardrails.",
            # Filter strength for incoming user prompts and outgoing agent responses
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="NONE",
                        output_strength="NONE",
                        type="PROMPT_ATTACK"
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="HIGH",
                        output_strength="HIGH",
                        type="MISCONDUCT"
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="HIGH",
                        output_strength="HIGH",
                        type="INSULTS"
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="HIGH",
                        output_strength="HIGH",
                        type="HATE"
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="HIGH",
                        output_strength="HIGH",
                        type="SEXUAL"
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        input_strength="HIGH",
                        output_strength="HIGH",
                        type="VIOLENCE"
                    )                    
                ]
            )
        )
        
        # Create a Guardrail version
        cfn_guardrail_version = bedrock.CfnGuardrailVersion(self, "MyCfnGuardrailVersion",
            guardrail_identifier=cfn_guardrail.attr_guardrail_id,
            description="This is the deployed version of the guardrail configuration",
        )
        
        # Custom resource to update the agent with the guardrail details, as cloudformation does not support this feature at this time
        # Define the request body for the api call that the custom resource will use. Notice that the agentId is part of the URI and not the request body of the API call, but we can pass it in as a key value pair.
        updateAgentParams = {
            "agentId": bedrock_agent.attr_agent_id,
            "agentName": bedrock_agent.agent_name,
            "agentResourceRoleArn": bedrock_agent.agent_resource_role_arn,
            "foundationModel": bedrock_agent.foundation_model,
            "guardrailConfiguration": { 
                "guardrailIdentifier": cfn_guardrail.attr_guardrail_id,
                "guardrailVersion": cfn_guardrail_version.attr_version
            },
            "idleSessionTTLInSeconds": 600
        }

        # Define a custom resource to make an AwsSdk startCrawler call to the Glue API     
        update_agent_cr = cr.AwsCustomResource(self, "UpdateAgentCustomResource",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="updateAgent",
                parameters=updateAgentParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                ),
            on_update=cr.AwsSdkCall(
                service="bedrock-agent",
                action="updateAgent",
                parameters=updateAgentParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),            
            )
     
        # Define IAM permission policy for the custom resource    
        update_agent_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:UpdateAgent", 
                "iam:CreateServiceLinkedRole", 
                "iam:PassRole"
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}:{self.account}:agent/{bedrock_agent.ref}"
            ],
            )
        )  

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/BedrockAgentStack/UpdateAgentCustomResource/CustomResourcePolicy/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )