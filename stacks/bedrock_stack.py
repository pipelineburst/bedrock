from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_s3_deployment as s3d,
    aws_s3 as s3,
    Fn as Fn,
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

        # Create a bedrock agent execution role with permissions to interact with the services
        bedrock_agent_role = iam.Role(self, 'bedrock-agent-role',
            role_name='AmazonBedrockExecutionRoleForAgents_KIUEYHSVDR',
            assumed_by=iam.ServicePrincipal('bedrock.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonBedrockFullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AWSLambda_FullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3FullAccess'),                
            ],
        )
        
        CfnOutput(self, "BedrockAgentRoleArn",
            value=bedrock_agent_role.role_arn,
            export_name="BedrockAgentRoleArn"
        )

        # Add iam resource to the bedrock agent
        bedrock_agent_role.add_to_policy(
            iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelEndpoint", "bedrock:InvokeModelEndpointAsync"],
            resources=["*"],
            )
        )

        # Create S3 bucket for the data set
        schema_bucket = s3.Bucket(self, "schema-bucket",
            bucket_name=("schema-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
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

        NagSuppressions.add_resource_suppressions(
            schema_bucket,
            [NagPackSuppression(id="BedrockAgentSolutions", reason="The bucket is not for production and should not require debug.")],
            True
        )
    
        # Upload data from asset to S3 bucket
        s3d.BucketDeployment(self, "DataDeployment",
            sources=[s3d.Source.asset("assets/schema/")],
            destination_bucket=schema_bucket,
            destination_key_prefix="schema/"
        )
        
        # Export the data set bucket name
        CfnOutput(self, "APISchemaBucket",
            value=schema_bucket.bucket_name,
            export_name="APISchemaBucket"
        )

        # Add instuctions for the bedrock agent
        with open('assets/agent_instructions.txt', 'r') as file:
            agent_instruction = file.read()

        # Add schema for the bedrock agent
        with open('assets/schema/athena_ag_schema.json', 'r') as file:
            athena_schema_def = file.read()
            
        with open('assets/schema/search_ag_schema.json', 'r') as file:
            search_schema_def = file.read()

        # Define advanced prompt - orchestation template - override orchestration template defaults
        with open('assets/agent_orchenstation_template.json', 'r') as file:
            orc_temp_def = file.read()

        # Define advanced prompt - pre-processing template - override pre-processing template defaults
        with open('assets/agent_preprocessing_template.json', 'r') as file:
            pre_temp_def = file.read()

        # Create a bedrock agent        
        bedrock_agent = bedrock.CfnAgent(self, 'bedrock-agent',
            agent_name='saas-acs-bedrock-agent',
            description="This is a bedrock agent that can be invoked by calling the bedrock agent alias and agent id.",
            auto_prepare=True,
            foundation_model="anthropic.claude-3-haiku-20240307-v1:0",
            instruction=agent_instruction,
            agent_resource_role_arn=str(bedrock_agent_role.role_arn),
            prompt_override_configuration=bedrock.CfnAgent.PromptOverrideConfigurationProperty(
                prompt_configurations=[bedrock.CfnAgent.PromptConfigurationProperty(
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
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=pre_temp_def,
                        prompt_type="PRE_PROCESSING",
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
            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="AthenaToolFunction",
                    description="A Function Tool that can access a network metrics dataset.",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=athena_lambda_arn,
                    ),
                    api_schema=bedrock.CfnAgent.APISchemaProperty(
                        payload=athena_schema_def,
                        ### leaving this here for future reference as the 3 bucket option fails with cloudformation error
                        # s3=bedrock.CfnAgent.S3IdentifierProperty(
                        #     s3_bucket_name=schema_bucket.bucket_name,
                        #     s3_object_key="schema/open_api_schema.json",
                        #),
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

        