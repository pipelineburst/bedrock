from http import server
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
    Size,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3d,
    aws_glue as glue,
    aws_athena as athena,
    aws_kms as kms
)
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib

class DataFoundationStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        ### 0. Create access log bucket
        logs_bucket = s3.Bucket(self, "LogsBucket",
            bucket_name=("logs-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED
        )

        # Export the bucket name
        CfnOutput(self, "AccessLogsBucketName",
            value=logs_bucket.bucket_name,
            export_name="AccessLogsBucketName"
        )
        
        # Export the bucket name
        CfnOutput(self, "AccessLogsBucketArn",
            value=logs_bucket.bucket_arn,
            export_name="AccessLogsBucketArn"
        )

        ### 1. Create data-set resources
        
        # Create S3 bucket for the data set
        data_bucket = s3.Bucket(self, "DataLake",
            bucket_name=("data-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=logs_bucket,
            server_access_logs_prefix="data-bucket-access-logs/",
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
            
        # Upload data from asset to S3 bucket - with the prefix for incoming "raw" data
        upload_dataset = s3d.BucketDeployment(self, "DataDeployment",
            sources=[s3d.Source.asset("assets/data-set/")],
            destination_bucket=data_bucket,
            destination_key_prefix="data-set/"
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/DataStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by the Construct.")],
            True
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/DataStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/Resource',
            [NagPackSuppression(id="AwsSolutions-L1", reason="Lambda is owned by AWS construct")],
            True
        )
        
        # Export the data set bucket name
        CfnOutput(self, "DataSetBucketName",
            value=data_bucket.bucket_name,
            export_name="DataSetBucketName"
        )
        
        CfnOutput(self, "DataSetBucketArn",
            value=data_bucket.bucket_arn,
            export_name="DataSetBucketArn"
        )

        ### 2. Create glue resources

        # Create Glue Service Role
        glue_service_role = iam.Role(self, "GlueServiceRole",
            role_name=("GlueServiceRole-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
            ]
        )
        
        NagSuppressions.add_resource_suppressions(
            glue_service_role,
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="We support the use of managed policies.")],
            True
        )

        # Create Glue Database
        glue_database_name = "data_set_db"
        
        glue_db = glue.CfnDatabase(self, "DataSetDatabase", catalog_id=self.account, database_input=glue.CfnDatabase.DatabaseInputProperty(name=glue_database_name))

        # Export the glue database name
        CfnOutput(self, "GlueDatabaseName",
            value=glue_database_name,
            export_name="GlueDatabaseName"
        )        

        # Create KMS key for Glue job encryption configuration and allow the cloudwatch logs service to associate the key to the log group
        glue_job_key = kms.Key(self, "GlueJobEncryptionKey",
            enable_key_rotation=True,
            enabled=True,
            alias="GlueJobEncryptionKey",
            removal_policy=RemovalPolicy.DESTROY,
            key_usage=kms.KeyUsage.ENCRYPT_DECRYPT,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:GenerateDataKey",
                            "kms:DescribeKey"
                        ],
                        principals=[iam.ServicePrincipal("glue.amazonaws.com")],
                        resources=["*"]
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:*"
                        ],
                        resources=["*"],
                        principals=[iam.AccountPrincipal(self.account)]
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:GenerateDataKey",
                            "kms:DescribeKey"
                        ],
                        resources=["*"],
                        principals=[iam.ServicePrincipal("logs.amazonaws.com")]
                    ),
                ],
            )
        )
 
         # Grant the Glue service role permissions to use the KMS key       
        glue_job_key.grant(glue_service_role, "kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey")

        # Create Glue role for the etl job
        glue_job_role = iam.Role(self, "GlueEtlJobRole",
            role_name=("GlueEtlJobRole-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole"),
            ]
        )

        glue_job_role.add_to_policy(
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
                    "s3:PutObject"
                    ],
                resources=[
                    data_bucket.bucket_arn,
                    data_bucket.bucket_arn + "/*"
                ]
            )
        )

        glue_job_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:AssociateKmsKey",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                    ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws-glue/jobs:*",
                    f"arn:aws:logs:{self.region}:{self.account}:*:/aws-glue/*"
                ]
            )
        )

        glue_job_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:Encrypt",
                    "kms:GenerateDataKey"
                    ],
                resources=[
                    glue_job_key.key_arn
                ]
            )
        )

        NagSuppressions.add_resource_suppressions(
            glue_job_role,
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="We support the use of managed policies.")],
            True
        )

        NagSuppressions.add_resource_suppressions(
            glue_job_role,
            [NagPackSuppression(id="AwsSolutions-IAM5", reason="We support the wild cards that are specific behing a resource locator.")],
            True
        )

        # Grant read and write access to the data bucket
        data_bucket.grant_read_write(glue_job_role)
        
        # Upload glue etl script from asset to S3 bucket. The script will be used by the Glue etl job, creates compressed parquet files, creates a schema, and creates a glue db table partitions
        upload_scripts = s3d.BucketDeployment(self, "GlueJobScript",
            sources=[s3d.Source.asset("assets/glue/")],
            destination_bucket=data_bucket,
            destination_key_prefix="scripts/"
        )

        # Creating the Glue security configuration for the etl job
        cfn_security_configuration = glue.CfnSecurityConfiguration(self, "MyCfnSecurityConfiguration",
            name="glue-job-security-config",
            encryption_configuration=glue.CfnSecurityConfiguration.EncryptionConfigurationProperty(
                cloud_watch_encryption=glue.CfnSecurityConfiguration.CloudWatchEncryptionProperty(
                    cloud_watch_encryption_mode="SSE-KMS",
                    kms_key_arn=glue_job_key.key_arn
                ),
                job_bookmarks_encryption=glue.CfnSecurityConfiguration.JobBookmarksEncryptionProperty(
                    job_bookmarks_encryption_mode="CSE-KMS",
                    kms_key_arn=glue_job_key.key_arn
                ),
                s3_encryptions=[glue.CfnSecurityConfiguration.S3EncryptionProperty(
                    s3_encryption_mode="SSE-S3",
                )]
            ),

        )

        # Create a Glue etl job that processes the data set
        etl_job = glue.CfnJob(self, "DataSetETLJob",
            name="DataSetETLJob",
            role=glue_job_role.role_arn,
            execution_class="FLEX",
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                script_location="s3://{}/scripts/etl.py".format(data_bucket.bucket_name),
                python_version="3",
            ),
            default_arguments={
            "--job-bookmark-option": "job-bookmark-enable",
            "--enable-metrics": "true",
            "--enable-observability-metrics": "true",
            "--enable-continuous-cloudwatch-log": "true",
            "--customer-driver-env-vars": f"CUSTOMER_BUCKET_NAME={data_bucket.bucket_name}",
            "--customer-executor-env-vars": f"CUSTOMER_BUCKET_NAME={data_bucket.bucket_name}"
            },
            glue_version="4.0",
            max_retries=0,
            number_of_workers=10,
            worker_type="G.1X",
            security_configuration=cfn_security_configuration.name, 
        )
        
        # Create a Glue schedule for the etl job that processes the data set with the bookmark option enabled
        glue_schedule = glue.CfnTrigger(self, "DataSetETLSchedule",
            name="DataSetETLSchedule",
            description="Schedule for the DataSetETLJob to discover and process incoming data",
            type="SCHEDULED",
            start_on_creation=True,
            actions=[glue.CfnTrigger.ActionProperty(
                job_name=etl_job.ref,
                arguments={
                    "--job-bookmark-option": "job-bookmark-enable",
                    "--enable-metrics": "true",
                    "--enable-observability-metrics": "true",
                    "--enable-continuous-cloudwatch-log": "true",
                    "--customer-driver-env-vars": f"CUSTOMER_BUCKET_NAME={data_bucket.bucket_name}",
                    "--customer-executor-env-vars": f"CUSTOMER_BUCKET_NAME={data_bucket.bucket_name}"
                }
            )],
            schedule="cron(0/15 * * * ? *)"
        ) 
        
        ### 3. Create Athena resources
        
        # Create S3 athena destination bucket 
        athena_bucket = s3.Bucket(self, "AthenaDestination",
            bucket_name=("athena-destination-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=logs_bucket,
            server_access_logs_prefix="athena-destination-access-logs/",
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
        
        # Export the athena workgroup name
        CfnOutput(self, "AthenaWorkGroupName",
            value=athena_workgroup.name,
            export_name="AthenaWorkGroupName"
        )

        ### 4. Create knowledgebase bucket and upload corpus of documents
        
        # Create S3 bucket for the knowledgebase assets
        kb_bucket = s3.Bucket(self, "Knowledgebase",
            bucket_name=("knowledgebase-bucket-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]).lower(),
            auto_delete_objects=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=logs_bucket,
            server_access_logs_prefix="knowledgebase-access-logs/",
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

        kb_bucket.grant_read_write(iam.ServicePrincipal("bedrock.amazonaws.com"))

        # Upload doc assets to S3 bucket. may contain large files so use the ephemeral storage size and increase timeout
        upload_docs = s3d.BucketDeployment(self, "KnowledgebaseDocs",
            sources=[s3d.Source.asset("assets/kb-docs/")],
            destination_bucket=kb_bucket,
            destination_key_prefix="eaa-docs/",
            ephemeral_storage_size=Size.gibibytes(1),
            memory_limit=1024,
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/DataStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C1024MiB1024MiB/ServiceRole',
            [NagPackSuppression(id="AwsSolutions-IAM4", reason="Policies are set by the Construct."), NagPackSuppression(id="AwsSolutions-IAM5", reason="Policies are set by the Construct.")],
            True
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            '/DataStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C1024MiB1024MiB/Resource',
            [NagPackSuppression(id="AwsSolutions-L1", reason="Lambda is owned by AWS construct")],
            True
        )

        # Export the kb bucket bucket name
        CfnOutput(self, "KnowledgebaseBucketName",
            value=kb_bucket.bucket_name,
            export_name="KnowledgebaseBucketName"
        )
        
        # Export the kb bucket bucket arn
        CfnOutput(self, "KnowledgebaseBucketArn",
            value=kb_bucket.bucket_arn,
            export_name="KnowledgebaseBucketArn"
        )