#!/usr/bin/env python3
import os
from cdk_nag import AwsSolutionsChecks

import aws_cdk as cdk
from stacks.data_stack import DataFoundationStack
from stacks.lambda_stack import LambdaStack
from stacks.bedrock_stack import BedrockStack
from stacks.aoss_stack import AossStack
from stacks.kb_stack import KnowledgeBaseStack
from stacks.streamlit_stack import StreamlitStack

app = cdk.App()

dict1 = {
    "region": 'us-west-2',
    "account_id": '851725325557'
}

stack1 = DataFoundationStack(app, "DataStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Data foundations for the bedrock agent", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
)

stack2 = LambdaStack(app, "LambdaStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Lambda resources for the bedrock action groups", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
)

stack3 = BedrockStack(app, "BedrockAgentStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Bedrock agent resources", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
            athena_lambda_arn=stack2.athena_lambda_arn,
            search_lambda_arn=stack2.search_lambda_arn
)

stack4 = AossStack(app, "AossStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Opensearch Serverless resources", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
            agent_arn=stack3.agent_arn,
)

stack5 = KnowledgeBaseStack(app, "KnowledgebaseStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Bedrock knowledgebase resources", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
            agent_arn=stack3.agent_arn,
)

stack6 = StreamlitStack(app, "StreamlitStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Streamlit app for the bedrock sandbox account", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1
)

stack2.add_dependency(stack1)
stack3.add_dependency(stack2)
stack4.add_dependency(stack3)
stack5.add_dependency(stack4)
stack6.add_dependency(stack5)

cdk.Tags.of(stack1).add(key="owner",value="acs")
cdk.Tags.of(stack2).add(key="owner",value="acs")
cdk.Tags.of(stack3).add(key="owner",value="acs")
cdk.Tags.of(stack4).add(key="owner",value="acs")
cdk.Tags.of(stack5).add(key="owner",value="acs")
cdk.Tags.of(stack6).add(key="owner",value="acs")

cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=False))

app.synth()
