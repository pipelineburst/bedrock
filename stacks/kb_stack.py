from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3d,
    aws_glue as glue,
    aws_athena as athena,
    custom_resources as cr
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib

class KnowledgebaseStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        ### Create data-set resources
        
        # Create S3 bucket for the data set
        data_bucket = s3.Bucket(self, "DataLake",
            bucket_name=("data-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
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
        add_s3_policy = data_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject","s3:PutObject","s3:AbortMultipartUpload"],
                resources=[data_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                )
            )

        NagSuppressions.add_resource_suppressions(
            data_bucket,
            [NagPackSuppression(id="BedrockAgentSolutions", reason="The bucket is not for production and should not require debug.")],
            True
        )
    
        # Upload data from asset to S3 bucket
        s3d.BucketDeployment(self, "DataDeployment",
            sources=[s3d.Source.asset("assets/data-set/")],
            destination_bucket=data_bucket,
            destination_key_prefix="data-set/"
        )
        
        # Export the data set bucket name
        CfnOutput(self, "DataSetBucketName",
            value=data_bucket.bucket_name,
            export_name="DataSetBucketName"
        )

        ### Create glue resources

        # Create Glue Service Role
        glue_service_role = iam.Role(self, "GlueServiceRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ]
        )

        # Create Glue Database
        glue_database_name = "data_set_db"
        
        glue.CfnDatabase(self, "DataSetDatabase", catalog_id=self.account, database_input=glue.CfnDatabase.DatabaseInputProperty(name=glue_database_name))
        
        # Create Glue Crawler Role
        crawler_role = iam.Role(self, "CrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            inline_policies={
                "CrawlerPolicy": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(
                        actions=[
                            "glue:Get*",
                            "glue:List*",
                            "glue:Query*",
                            "glue:Search*",
                            "glue:Batch*",
                            "glue:Create*",
                            "glue:CheckSchemaVersionValidity",
                            "glue:Import*",
                            "glue:Put*",
                            "glue:UpdateTable"
                        ],
                        resources=[
                            "arn:aws:glue:{}:{}:catalog".format(self.region, self.account),
                            "arn:aws:glue:{}:{}:database/{}".format(self.region, self.account, glue_database_name),
                            "arn:aws:glue:{}:{}:table/{}/*".format(self.region, self.account, glue_database_name)
                        ]
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "s3:PutObject",
                            "s3:GetObject",
                            "s3:PutBucketLogging",
                            "s3:ListBucket",
                            "s3:PutBucketVersioning"
                        ],
                        resources=[
                            data_bucket.bucket_arn,
                            data_bucket.bucket_arn + "/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "s3:PutObject",
                            "s3:GetObject",
                            "s3:PutBucketLogging",
                            "s3:ListBucket",
                            "s3:PutBucketVersioning"
                        ],
                        resources=[
                            data_bucket.bucket_arn,
                            data_bucket.bucket_arn + "/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:AssociateKmsKey"
                        ],
                        resources=[
                            "arn:aws:logs:*:*:log-group:/aws-glue/*"
                        ]
                    )                    
                ])
            }
        )

        # Create Glue Crawler
        dataset_crawler = glue.CfnCrawler(self, "DataSetCrawler",
            name="DataSetCrawler",
            database_name=glue_database_name,
            role=crawler_role.role_arn,
            targets=glue.CfnCrawler.TargetsProperty(
            s3_targets=[
                glue.CfnCrawler.S3TargetProperty(path="s3://{}/data-set/".format(data_bucket.bucket_name))
            ]
            ),
            schedule=glue.CfnCrawler.ScheduleProperty(
            schedule_expression="cron(0 0 * * ? *)"  # Run once a day at midnight
            )
        )
        
        # Trigger the crawer on create so we have a table to query before the first scheduled run
        # Define the input dictionary content for the start_crawler AwsSdk call
        onCreateCrawlerParams = {
                    "Name": dataset_crawler.name
        }

        # Define a custom resource to make an AwsSdk startCrawler call to the Glue API     
        crawler_cr = cr.AwsCustomResource(self, "GlueCrawlerCustomResource",
            on_create=cr.AwsSdkCall(
                service="Glue",
                action="startCrawler",
                parameters=onCreateCrawlerParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
     
        # Define IAM permission policy for the custom resource    
        crawler_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["glue:StartCrawler", "glue:ListCrawlers", "iam:CreateServiceLinkedRole"],
            resources=["*"],
            )
        )        
        
        ### Create Athena resources
        
        # Create S3 athena destination bucket 
        athena_bucket = s3.Bucket(self, "AthenaDestination",
            bucket_name=("athena-destination-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
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
        
        athena_bucket.grant_read_write(iam.ServicePrincipal("athena.amazonaws.com"))

        # Export the athena destination bucket name
        CfnOutput(self, "AthenaDestBucketName",
            value=athena_bucket.bucket_name,
            export_name="AthenaDestinationBucketName"
        )
        
        # Set the query result location for Athena
        athena_bucket_uri = f"s3://{athena_bucket.bucket_name}/query-results/"
        
        athena_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetBucketLocation"],
                resources=[athena_bucket.bucket_arn],
                principals=[iam.ServicePrincipal("athena.amazonaws.com")],
            )
        )
        athena_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListBucket"],
                resources=[athena_bucket.bucket_arn],
                principals=[iam.ServicePrincipal("athena.amazonaws.com")],
                conditions={"StringEquals": {"s3:prefix": ["query-results/"]}},
            )
        )
        athena_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:PutObject", "s3:GetObject"],
                resources=[f"{athena_bucket.bucket_arn}/query-results/*"],
                principals=[iam.ServicePrincipal("athena.amazonaws.com")],
            )
        )
        athena_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:PutObject"],
                resources=[f"{athena_bucket.bucket_arn}/query-results/*"],
                principals=[iam.ServicePrincipal("athena.amazonaws.com")],
                conditions={"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
            )
        )
        
        # Configure Athena Query Editor and set the athena destination bucket
        athena_workgroup = athena.CfnWorkGroup(self, "AthenaWorkGroup",
            name="bedrock-workgroup",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=athena_bucket_uri,
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                )
            )
        )
