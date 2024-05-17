from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
)
from constructs import Construct

class InitialSetupStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
            
        # define a cross account iam role
        
        trusted_account_id = "860259298614"
        
        cross_account_role = iam.Role(
            self,
            "CrossAccountRole",
            assumed_by=iam.AccountPrincipal(trusted_account_id),
            role_name="CrossAccountRole"
        )
            
        # define a policy statement
        
        cross_account_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )
        
        # define a new iam user
        iam_user1 = iam.User(
            self,
            "STalluri",
            user_name="STalluri"
        )
        
        # define a new iam group
        iam_admin_group = iam.Group(
            self,
            "AdminGroup",
            group_name="AdminGroup"
        )
        
        # add iam user to iam group
        iam_admin_group.add_user(iam_user1)
        
        # add admin policy to group
        iam_admin_group.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )