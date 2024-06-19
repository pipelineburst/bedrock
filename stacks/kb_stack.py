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
        
        bedrock_role_arn = Fn.import_value("BedrockAgentRoleArn")
        
        ### 1. Create bedrock knowledgebase for the agent
        
        kb_bucket_name = Fn.import_value("KnowledgebaseBucketName")
        index_name = "kb-docs"

        # Create the bedrock knowledgebase with the role arn that is referenced in the opensearch data access policy
        bedrock_knowledge_base = bedrock.CfnKnowledgeBase(self, "KnowledgeBaseDocs",
            name="bedrock-kb-docs",
            description="Bedrock knowledge base that contains a corpus of documents",
            role_arn=Fn.import_value("BedrockKbRoleArn"),
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{dict1['region']}::foundation-model/amazon.titan-embed-text-v1"
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=Fn.import_value("OpenSearchCollectionArn"),
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
        
        # Create the data source for the bedrock knowledgebase. Chunking max tokens of 300 is bedrock's sensible default.
        kb_data_source = bedrock.CfnDataSource(self, "KbDataSource",
            name="KbDataSource",
            description="The S3 data source definition for the bedrock knowledge base",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=Fn.import_value("KnowledgebaseBucketArn"),
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

        # Only trigger the custom resource when the kb is completed    
        kb_data_source.node.add_dependency(bedrock_knowledge_base)

        ### 2. Associate the knowdledebase with the agent
        
        # A bug prevents the use of the association "DRAFT because it doesn't exist", which is forced due to pattern matching in the bedrock-agent API 
        
        # agent_id = Fn.import_value("BedrockAgentID")

        # # Custom resource to associate the knowledge base with the agent
        # # Define the parameters. the boto3 client will create the correct PUT request to the bedrock-agent API
        # # This is an example of passing the params as a dictionary, although the direct API call uses a PUT to pass the params
        # # The agent version must always be DRAFT as its being patter matched in the bedrock-agent API
        # agentKbAssociationParams = {
        #     "agentId": agent_id,
        #     "agentVersion": "DRAFT",
        #     "description": "This knowledge base contains EAA product infomation. You can use it to answer questions about various production, including proptima, netexpert, proassure, proactor, and more.",
        #     "knowledgeBaseId": bedrock_knowledge_base.attr_knowledge_base_id,
        #     "knowledgeBaseState": "ENABLED",
        # }

        # # Define a custom resource to make an AwsSdk call to associate the knowledge base with the agent     
        # agent_kb_cr = cr.AwsCustomResource(self, "AgentKbCustomResource",
        #     on_create=cr.AwsSdkCall(
        #         service="bedrock-agent",
        #         action="updateAgentKnowledgeBase",
        #         parameters=agentKbAssociationParams,
        #         physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
        #         ),
        #     policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
        #         resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
        #         )
        #     )
     
        # # Define IAM permission policy for the custom resource    
        # agent_kb_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
        #     effect=iam.Effect.ALLOW,
        #     actions=["bedrock:*", "iam:CreateServiceLinkedRole", "iam:PassRole"],
        #     resources=["*"],
        #     )
        # )  

        # # Only trigger the custom resource when the kb is completed    
        # agent_kb_cr.node.add_dependency(kb_data_source)
        
        ### 3. Start ingestion job for the knowdledebase data source
        
        # Perhaps best hanlded outside of AWS CDK as it is a long running job

        # # Custom resource to start the data source synch job, aka the data ingestion job
        # # Define the parameters for the ingestion job. the boto3 client will create the correct PUT request to the bedrock-agent API
        # # This is an example of passing the params as a dictionary, although the direct API call uses a PUT to pass the params
        # dataSourceIngestionParams = {
        #     "dataSourceId": kb_data_source.attr_data_source_id,
        #     "knowledgeBaseId": bedrock_knowledge_base.attr_knowledge_base_id,
        # }

        # # Define a custom resource to make an AwsSdk startCrawler call to the Glue API     
        # ingestion_job_cr = cr.AwsCustomResource(self, "IngestionCustomResource",
        #     on_create=cr.AwsSdkCall(
        #         service="bedrock-agent",
        #         action="startIngestionJob",
        #         parameters=dataSourceIngestionParams,
        #         physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
        #         ),
        #     policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
        #         resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
        #         )
        #     )
     
        # # Define IAM permission policy for the custom resource    
        # ingestion_job_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
        #     effect=iam.Effect.ALLOW,
        #     actions=["bedrock:*", "iam:CreateServiceLinkedRole", "iam:PassRole"],
        #     resources=["*"],
        #     )
        # )  

        # # Only trigger the custom resource when the kb is completed    
        # ingestion_job_cr.node.add_dependency(agent_kb_cr)