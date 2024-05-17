#!/usr/bin/env python3
import os

import aws_cdk as cdk
from stacks.kb_stack import KnowledgebaseStack
from stacks.lambda_stack import LambdaStack
from stacks.bedrock_stack import BedrockStack
from stacks.streamlit_stack import StreamlitStack

app = cdk.App()

dict1 = {
    "region": 'us-west-2',
    "account_id": '851725325557'
}

stack1 = KnowledgebaseStack(app, "DataStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Data lake resources for the bedrock sandbox account", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
)

stack2 = LambdaStack(app, "LambdaStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Lambda resources for the bedrock sandbox account", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
)

stack3 = BedrockStack(app, "BedrockAgentStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Bedrock agent resources for the bedrock sandbox account", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1,
            lambda_arn=stack2.lambda_arn
)

stack4 = StreamlitStack(app, "StreamlitStack",
            env=cdk.Environment(account=dict1['account_id'], region=dict1['region']),
            description="Streamlit app for the bedrock sandbox account", 
            termination_protection=False, 
            tags={"project":"bedrock-agents"},
            dict1=dict1
)

stack2.add_dependency(stack1)
stack3.add_dependency(stack2)
stack4.add_dependency(stack3)

cdk.Tags.of(stack1).add(key="owner",value="saas")
cdk.Tags.of(stack2).add(key="owner",value="saas")
cdk.Tags.of(stack3).add(key="owner",value="saas")
cdk.Tags.of(stack4).add(key="owner",value="saas")

app.synth()
