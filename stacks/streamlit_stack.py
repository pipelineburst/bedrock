from aws_cdk import (
    Stack,
    aws_certificatemanager as acm,
    aws_cognito as cognito,
    aws_efs as efs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    Duration as Duration,
    Fn as Fn,
    RemovalPolicy,
    CfnOutput,
)
import aws_cdk
from cdk_nag import (
    NagPackSuppression,
    NagSuppressions
)
from constructs import Construct
import hashlib

class StreamlitStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, dict1, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Creating the VPC for the ECS service
        vpc = ec2.Vpc(self, "CompanionVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateway_subnets=None,
            subnet_configuration=[ec2.SubnetConfiguration(name="public",subnet_type=ec2.SubnetType.PUBLIC,cidr_mask=24)]
        )

        # Create a unique string to create unique resource names
        hash_base_string = (self.account + self.region)
        hash_base_string = hash_base_string.encode("utf8")

        # Was the certificate argument been added as part of the cdk deploy? If so then a certification will be created for the load_balanced_service
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
            # Builds and imports the container image directly from the local directory (requires Docker to be installed on the local machine)
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
                    "bedrock:*"
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

        # Was the dev argument passed in as part of the cdk deploy? 
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

        # Was the email address argument passed in as part of the cdk deploy? If so then authentication will be applied to the ALB
        email_address = self.node.try_get_context('email_address')

        if email_address:
            # Are we using a custom domain name?
            custom_domain_name = self.node.try_get_context('domain_name')

            #Declare variables here for logic that is reused
            domain_name = (custom_domain_name if custom_domain_name else load_balanced_service.load_balancer.load_balancer_dns_name)
            full_domain_name = ("https://" if acm_certificate_arn else "http://") + domain_name

            #Create a Cognito User Pool for user authentication
            user_pool = cognito.UserPool(self, "NetworkAssistantUserPool",
                self_sign_up_enabled=False,
                user_invitation=cognito.UserInvitationConfig(
                    email_subject="New Dashboard Account",
                    email_body="""Hi there,
                    
                    You've been granted permission to use a dashboard:
                    """ + full_domain_name + """

                    Your username is '<b>{username}</b>' and your temporary password is <b>{####}</b>"""
                ),
                auto_verify=cognito.AutoVerifiedAttrs(email=True),
                password_policy=cognito.PasswordPolicy(min_length=8, require_digits=True, require_symbols=True, require_lowercase=True, require_uppercase=True),
                advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED
            )

            NagSuppressions.add_resource_suppressions(
                user_pool,
                [NagPackSuppression(id="AwsSolutions-COG2", reason="MFA is not required as a POC.")],
                True
            )

            #Create a Cognito User Pool Domain for the ALB to use for authentication
            user_pool_domain = user_pool.add_domain("NetworkAssistantUserPoolDomain",
                cognito_domain=cognito.CognitoDomainOptions(
                    domain_prefix="saas-acs-genai-" + str(hashlib.sha384(hash_base_string).hexdigest())[:15]
                )
            )

            #Create a Cognito User Pool Client for the ALB to use for authentication. This is required for the ALB to use the Cognito User Pool.
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

            #Create a Cognito User Pool User based on the provided email address for the ALB to use for authentication. This is required for the ALB to use the Cognito User Pool. This user is the only user that will be able to access the ALB.
            cognito.CfnUserPoolUser(self, "UserPoolUser",
                desired_delivery_mediums=["EMAIL"],
                user_attributes=[cognito.CfnUserPoolUser.AttributeTypeProperty(
                    name="email",
                    value=email_address
                )],
                username="dashboard_user",
                user_pool_id=user_pool.user_pool_id
            )

            #Apply the Cognito User Pool to the ALB. This will cause the ALB to use the Cognito User Pool for authentication. This is required for the ALB to use the Cognito User Pool. This user is the only user that will be able to access the ALB.
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
            
            