from distutils.log import Log
from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_bedrock as bedrock,
    Fn as Fn,
    custom_resources as cr,
    aws_iam as iam,
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib

class KnowledgeBaseStack(Stack):

    def __init__(self, scope: Construct, id: str, dict1, agent_arn, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        # Importing values from the other stacks        
        bedrock_agent_id = Fn.import_value("BedrockAgentID")
        bedrock_role_arn = Fn.import_value("BedrockAgentRoleArn")
        kb_bucket_name = Fn.import_value("KnowledgebaseBucketName")
        kb_bucket_arn = Fn.import_value("KnowledgebaseBucketArn")
        kb_role_arn = Fn.import_value("BedrockKbRoleArn")
        aoss_collection_arn = Fn.import_value("OpenSearchCollectionArn")        
        
        ### 1. Create bedrock knowledgebase for the agent
        
        index_name = "kb-docs"

        # Create the bedrock knowledgebase with the role arn that is referenced in the opensearch data access policy
        bedrock_knowledge_base = bedrock.CfnKnowledgeBase(self, "KnowledgeBaseDocs",
            name="bedrock-kb-docs",
            description="Bedrock knowledge base that contains a corpus of documents",
            role_arn=kb_role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{dict1['region']}::foundation-model/amazon.titan-embed-text-v1"
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=aoss_collection_arn,
                    vector_index_name=index_name,
                    field_mapping = bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        metadata_field="metadataField",
                        text_field="textField",
                        vector_field="vectorField"
                        )
                    ),
                ),
            tags={
                "owner": "saas"
                }
        )

        CfnOutput(self, "BedrockKbName",
            value=bedrock_knowledge_base.name,
            export_name="BedrockKbName"
        )           
        
        # Create the data source for the bedrock knowledgebase. Chunking max tokens of 300 is bedrock's sensible default.
        kb_data_source = bedrock.CfnDataSource(self, "KbDataSource",
            name="KbDataSource",
            description="The S3 data source definition for the bedrock knowledge base",
            data_deletion_policy="RETAIN",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=kb_bucket_arn,
                    inclusion_prefixes=["eaa-docs"],
                ),
                type="S3"
            ),
            knowledge_base_id=bedrock_knowledge_base.ref,
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300,
                        overlap_percentage=20
                    )
                )
            )
        )

        CfnOutput(self, "BedrockKbDataSourceName",
            value=kb_data_source.name,
            export_name="BedrockKbDataSourceName"
        ) 

        # Only trigger the custom resource when the kb is completed    
        kb_data_source.node.add_dependency(bedrock_knowledge_base)

        ## 2. Start ingestion job for the knowdledebase data source

        # Custom resource to start the data source synch job, aka the data ingestion job
        # Define the parameters for the ingestion job. the boto3 client will create the correct PUT request to the bedrock-agent API
        # This is an example of passing the params as a dictionary, although the direct API call uses a PUT to pass the params
        dataSourceIngestionParams = {
            "dataSourceId": kb_data_source.attr_data_source_id,
            "knowledgeBaseId": bedrock_knowledge_base.attr_knowledge_base_id,
        }

        # Define a custom resource to make an AwsSdk startCrawler call to the Glue API     
        ingestion_job_cr = cr.AwsCustomResource(self, "IngestionCustomResource",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="startIngestionJob",
                parameters=dataSourceIngestionParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
     
        # Define IAM permission policy for the custom resource    
        ingestion_job_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:*", 
                "iam:CreateServiceLinkedRole", 
                "iam:PassRole"
            ],
            resources=["*"],
            )
        )  

        # Only trigger the custom resource when the kb data source is created    
        ingestion_job_cr.node.add_dependency(kb_data_source)
        
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/KnowledgebaseStack/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by Custom Resource."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )
        
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/KnowledgebaseStack/IngestionCustomResource/CustomResourcePolicy/Resource',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by Custom Resource."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )

        ### 3. Associate the knowdledebase with the agent
        
        agent_id = Fn.import_value("BedrockAgentID")

        # Custom resource to associate the knowledge base with the agent
        # Define the parameters. the boto3 client will create the correct PUT request to the bedrock-agent API
        # This is an example of passing the params as a dictionary, although the direct API call uses a PUT to pass the params
        # The agent version must always be DRAFT as its being patter matched in the bedrock-agent API   
        
        ### Associate the agent with a knowledge base 
        agentKbAssociationParams = {
            "agentId": agent_id,
            "agentVersion": "DRAFT",
            "description": "This knowledge base contains EAA product infomation. You can use it to answer questions about various production, including proptima, netexpert, proassure, proactor, and more.",
            "knowledgeBaseId": bedrock_knowledge_base.attr_knowledge_base_id,
            "knowledgeBaseState": "ENABLED",
        }

        # Define a custom resource to make an AwsSdk call to associate the knowledge base with the agent     
        agent_kb_association_cr = cr.AwsCustomResource(self, "AssociateAgentKnowledgeBase",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="AssociateAgentKnowledgeBase",
                parameters=agentKbAssociationParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
     
        # Define IAM permission policy for the custom resource    
        agent_kb_association_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:AssociateAgentKnowledgeBase", 
                "iam:CreateServiceLinkedRole", 
                "iam:PassRole",
                "lambda:invoke",
            ],
            resources=["*"],
            )
        )  

        NagSuppressions.add_resource_suppressions(
            agent_kb_association_cr,
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="We support the use of wildcards. But a backlog item should be added to restrict the resources to the specific resources that the custom resource needs to access")],
            True
        )
        
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/KnowledgebaseStack/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by Custom Resource."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by Custom Resource.")],
            True
        )

        # Only trigger the custom resource when the kb data source resource is completed    
        agent_kb_association_cr.node.add_dependency(kb_data_source)
        
        ### 3. Create an agent alias to deploy agent
        
        ### Start by preparing the draft agent version

        prepareAgentParams = {
            "agentId": agent_id,
        }

        # Define a custom resource to make an AwsSdk call to prepare the agent     
        prepare_agent_cr = cr.AwsCustomResource(self, "PrepareAgent",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="prepareAgent",
                parameters=prepareAgentParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
     
        # Define IAM permission policy for the custom resource    
        prepare_agent_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:prepareAgent", 
                "iam:CreateServiceLinkedRole", 
                "iam:PassRole",
                "lambda:*",
            ],
            resources=["*"],
            )
        )  

        NagSuppressions.add_resource_suppressions(
            prepare_agent_cr,
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="We support the use of wildcards. But a backlog item should be added to restrict the resources to the specific resources that the custom resource needs to access")],
            True
        )

        prepare_agent_cr.node.add_dependency(agent_kb_association_cr)     

        ### Then create an alias to deploy the agent

        # Create an alias for the bedrock agent        
        cfn_agent_alias = bedrock.CfnAgentAlias(self, "MyCfnAgentAlias",
            agent_alias_name="bedrock-agent-alias",
            agent_id=bedrock_agent_id,
            description="bedrock agent alias to simplify agent invocation",
            # note: when initially creating the agent alias, the agent version is defined automatically
            # routing_configuration=[bedrock.CfnAgentAlias.AgentAliasRoutingConfigurationListItemProperty(
            #     agent_version="1",
            # )],
            tags={
                "owner": "saas"
            }
        )  
        
        agent_alias_string = cfn_agent_alias.ref
        agent_alias = agent_alias_string.split("|")[-1]
        
        CfnOutput(self, "BedrockAgentAlias",
            value=agent_alias,
            export_name="BedrockAgentAlias"
        )

        cfn_agent_alias.node.add_dependency(prepare_agent_cr)  