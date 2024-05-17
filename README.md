# Welcome to your CDK Python project!

# A CDK Project for the bedrock sandbox 

This project contains the source code for the Network GenAI Assistant POC based on Amazon Bedrock Agents. 

This code demonstrates what is possible using [generative AI](https://aws.amazon.com/generative-ai/) services including [Amazon Bedrock](https://aws.amazon.com/bedrock/) when empowered with your tabular and panel data.

This CDK codebase and streamlit application is inspired by https://github.com/build-on-aws/bedrock-agent-txt2sql

The Streamlit codebase has been wrapped by [CDK](https://aws.amazon.com/cdk/) to allow for the automatic deployment of the project backed on [AWS Fargate](https://aws.amazon.com/fargate/).

![Architecture diagram, demonstrating workflow](~/cdk-dev/bedrock/diagram.png)

The diagram above demonstrates the workflow of the architecture in the deployed application. The majority of the core logic for the application is within the Fargate container containing the Streamlit app as well as the Bedrock Agent that accesses the data backend via Action Groups. 
The source code for this can be found in the [/bedrock/streamlit](/bedrock/streamlit) folder.

## Instructions

**Before Deployment:** Review the latest supported regions for Amazon Bedrock. The selected region will need to suport Claude Haiku for this deployment to work.

Create the virtual environment within the root of this project using this command

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following step to activate your virtualenv.

```
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

If you have not used CDK before you will need to [install the CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html).

If CDK has not been used in the account or region before you must bootstrap it using the following command.

```
$ cdk bootstrap
```

Finally you can deploy the application by running the below command. **Please Note:** There are additional arguments below which will modify the resources of the deployment. Please take the time to review before deployment.

```
$ cdk deploy
```

Upon completion you will be provided with a DNS domain name and a HTTP/HTTPS URL depending on which configuration setup you have.

## Additional Arguments

You can further refine the logic by applying optional arguments to the deployment. These are each documented below.

### HTTPS Support

To enable HTTPS support you will need to pass a [ACM Certificate](https://aws.amazon.com/certificate-manager/) ARN from the account and region in which the deployment will reside in. You can use the below sample to demonstrate how this flag is activated.

```
$ cdk deploy --context acm_certificate_arn=???
```

### Authentication

To add support for an authenticated user you must use the `email_address` flag which will deploy an [Amazon Cognito](https://aws.amazon.com/cognito/) user pool which sits in front of the application. A user will be created in the user pool and password distributed via email for you to login.

```
$ cdk deploy --context email_address=???
```

### Custom Domain Name

If you would like to add a custom domain name in front of the application you must specify the `domain_name` argument. This will allow Cognito hosts to recognise the domain when authenticating. Once you have deployed with this flag you will need to apply any DNS records resolving to this domain.

```
$ cdk deploy --context domain_name=???
```

##¢ Supporting Multiple Arguments

To support multiple arguments you simply append the `--context` flags after the previous argument. Please see the example below.

```
$ cdk deploy --context acm_certificate_arn=??? --context email_address=??? --context domain_name=???
```