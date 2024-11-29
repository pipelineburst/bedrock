# A CDK Project for creating an amazon bedrock agent sandbox 

This project contains an example implementation of a "data analysis chat companion" built with Amazon Bedrock Agents. 

This code demonstrates what is possible using [generative AI](https://aws.amazon.com/generative-ai/) services including [Amazon Bedrock](https://aws.amazon.com/bedrock/) when used in conjunction with "private" tabular and panel data.

This CDK codebase is described and discussed here:
https://medium.com/@micheldirk/on-aws-cdk-and-amazon-bedrock-knowledge-bases-14c7b208e4cb
https://medium.com/@micheldirk/aws-cdk-and-agents-for-amazon-bedrock-e313be7543fe

This CDK codebase and its streamlit application were inspired by:
https://github.com/build-on-aws/bedrock-agent-txt2sql
https://github.com/build-on-aws/agents-for-amazon-bedrock-sample-feature-notebooks/tree/main

## Instructions

### Pre-req setup steps

**Before Use:** Review the latest supported regions for Amazon Bedrock. The selected region will need to suport Claude Haiku for this deployment to work.

Create the virtual environment within the root of this project using this command

```
python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following step to activate your virtualenv.

```
source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
pip install -r requirements.txt
```

If you have not used CDK before you will need to [install the CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html).

If CDK has not been used in the account or region before you must bootstrap it using the following command.

```
cdk bootstrap
```

**Deploy without context:** 

You can use CDK context arguments to make deployment choices and modify the resulting cloud resources. Please take the time to review the available context options before deployment.

Deploy the application without passing in any arguments by running the below command. This installs the basic agent without optional additional resources. 

```
cdk deploy --all
```

Upon completion the CDK output will provide an DNS domain name for the API gateway

## Available Context Arguments

You can choose to deploy additional resources, such as the development resources, knowledgebases, a streamlit web app, for example, by applying optional arguments to the deployment. These are each documented below. Substitute or define the values of the shown environment variables. 

### Deploy additional Development Resources

To enable development resources use the dev=true argument. This will provision a cloud9 instance, an EFS file system, and an additional mountpoint for the application countainer image. You can use the below sample to demonstrate how this flag is activated.

```
cdk deploy --context dev=true
```

### Deploy additional Bedrock Knowledgebase Resources

To enable the agent with acess to a knowledgebase resources ten use the knowledgebase=true argument. This will provision a bedrock knowledgebase, an opensearch serverless cluster, and associate the bedrock knowledgebase with the bedrock agent. 

```
cdk deploy --context knowledgebase=true
```

### Deploy additional API Gateway Resources

To enable the simplified access to the bedrock agent you can enable the api_gateway=true argument. This will provision an API Gateway that accepts a question and returns an answer. This will also provision Lambda function that API Gateway uses to invoke the bedrock agent to return the answer. 

```
cdk deploy --context api_gateway=true
```

### Deploy an additional Strealit demo web app

Use this context argument to deploy a supplementary Streamlit app and its supporting cloud services, such as an [Amazon ECS](https://aws.amazon.com/ecs/) cluster. **Note:** This option builds a container image in your execution environment, e.g. your local machine. You can install e.g. docker for that. 

```
cdk deploy --context email_address=$EMAIL_ADDRESS
```

### Deploy Strealit HTTPS Support

To enable HTTPS support you will need to pass a [ACM Certificate](https://aws.amazon.com/certificate-manager/) ARN from the account and region in which the deployment will reside in. You can use the below sample to demonstrate how this flag is activated. The certificate is not created for you... You need to create it and then provide its ARN as shown below.

```
cdk deploy --context acm_certificate_arn=$ACM_CERT_ARN
```

### Deploy Authentication for the Strealit web app

To add support for an authenticated user you must use the `email_address` flag which will deploy an [Amazon Cognito](https://aws.amazon.com/cognito/) user pool which sits in front of the application. A user will be created in the user pool and password distributed via email for you to login.

```
cdk deploy --context email_address=$EMAIL_ADDRESS
```

### Deploy Strealit Custom Domain Name

If you would like to add a custom domain name in front of the application you must specify the `domain_name` argument. This will allow Cognito hosts to recognise the domain when authenticating. Once you have deployed with this flag you will need to apply any DNS records resolving to this domain.

```
cdk deploy --context domain_name=$DOMAIN_NAME
```

### Supporting Multiple Arguments

To support multiple arguments you simply append the `--context` flags after the previous argument. Please see the example below.

```
cdk deploy --context aacm_certificate_arn=$ACM_CERT_ARN --context email_address=$EMAIL_ADDRESS --context domain_name=$DOMAIN_NAME
```