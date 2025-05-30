#!/usr/bin/env python3
"""
AWS Setup Script for BlinkySign
Creates necessary AWS resources for the project
"""
import boto3
import json
import os
import logging
import time
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
THING_NAME = os.getenv('IOT_THING_NAME', 'blinkysign')

# Project tag
PROJECT_TAG = {"Key": "project", "Value": "blinkysign"}

def create_iot_thing():
    """Create an AWS IoT Thing for the BlinkySign"""
    try:
        iot_client = boto3.client('iot', region_name=AWS_REGION)
        
        # Create IoT Thing
        thing_response = iot_client.create_thing(
            thingName=THING_NAME,
            attributePayload={
                'attributes': {
                    'project': 'blinkysign'
                }
            }
        )
        logger.info(f"Created IoT Thing: {thing_response['thingName']}")
        
        # Create policy
        policy_name = f"{THING_NAME}_policy"
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:Connect",
                        "iot:Publish",
                        "iot:Subscribe",
                        "iot:Receive"
                    ],
                    "Resource": [
                        f"arn:aws:iot:{AWS_REGION}:*:client/{THING_NAME}",
                        f"arn:aws:iot:{AWS_REGION}:*:topic/{THING_NAME}/*",
                        f"arn:aws:iot:{AWS_REGION}:*:topicfilter/{THING_NAME}/*"
                    ]
                }
            ]
        }
        
        try:
            policy_response = iot_client.create_policy(
                policyName=policy_name,
                policyDocument=json.dumps(policy_document),
                tags=[PROJECT_TAG]
            )
            logger.info(f"Created IoT Policy: {policy_response['policyName']}")
        except iot_client.exceptions.ResourceAlreadyExistsException:
            logger.info(f"Policy {policy_name} already exists")
            # Add tags to existing policy
            try:
                iot_client.tag_resource(
                    resourceArn=f"arn:aws:iot:{AWS_REGION}:{get_account_id()}:policy/{policy_name}",
                    tags=[PROJECT_TAG]
                )
            except Exception as e:
                logger.warning(f"Could not tag existing policy: {e}")
        
        # Create keys and certificate
        cert_response = iot_client.create_keys_and_certificate(setAsActive=True)
        cert_arn = cert_response['certificateArn']
        cert_id = cert_response['certificateId']
        cert_pem = cert_response['certificatePem']
        private_key = cert_response['keyPair']['PrivateKey']
        
        logger.info(f"Created certificate: {cert_id}")
        
        # Skip tagging certificates as it's not supported directly
        # IoT certificates can't be tagged with the TagResource API
        
        # Attach policy to certificate
        iot_client.attach_policy(
            policyName=policy_name,
            target=cert_arn
        )
        logger.info(f"Attached policy {policy_name} to certificate")
        
        # Attach certificate to thing
        iot_client.attach_thing_principal(
            thingName=THING_NAME,
            principal=cert_arn
        )
        logger.info(f"Attached certificate to thing {THING_NAME}")
        
        # Save certificates and keys to files
        os.makedirs('certs', exist_ok=True)
        with open('certs/certificate.pem', 'w') as f:
            f.write(cert_pem)
        with open('certs/private.key', 'w') as f:
            f.write(private_key)
            
        # Get IoT endpoint
        endpoint = iot_client.describe_endpoint(endpointType='iot:Data-ATS')
        with open('certs/endpoint.txt', 'w') as f:
            f.write(endpoint['endpointAddress'])
            
        # Update .env file with IoT endpoint
        update_env_file('IOT_ENDPOINT', endpoint['endpointAddress'])
            
        logger.info(f"Saved certificates and endpoint to 'certs/' directory")
        logger.info(f"IoT Endpoint: {endpoint['endpointAddress']}")
        
        return {
            'thingName': THING_NAME,
            'certificateId': cert_id,
            'endpoint': endpoint['endpointAddress']
        }
        
    except Exception as e:
        logger.error(f"Error creating IoT resources: {e}")
        raise

def create_api_gateway():
    """Create API Gateway to control the BlinkySign"""
    try:
        api_client = boto3.client('apigateway', region_name=AWS_REGION)
        
        # Create API
        api_response = api_client.create_rest_api(
            name=f"{THING_NAME}-api",
            description='API for controlling BlinkySign',
            endpointConfiguration={
                'types': ['REGIONAL']
            },
            tags={
                'project': 'blinkysign'
            },
            apiKeySource='HEADER'  # Enable API key authentication
        )
        api_id = api_response['id']
        logger.info(f"Created API Gateway: {api_id}")
        
        # Get root resource ID
        resources = api_client.get_resources(restApiId=api_id)
        root_id = [resource for resource in resources['items'] if resource['path'] == '/'][0]['id']
        
        # Create resource and methods
        resource_response = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='status'
        )
        resource_id = resource_response['id']
        
        # Create GET method with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for GET
        api_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for GET
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "off"}'
            }
        )
        
        # Create method response for GET
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create PUT method with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for PUT
        api_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='PUT',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for PUT
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='PUT',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "updated"}'
            }
        )
        
        # Create method response for PUT
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='PUT',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create toggle resource
        toggle_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='toggle'
        )
        toggle_id = toggle_resource['id']
        
        # Create PUT method for toggle with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=toggle_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for toggle
        api_client.put_integration(
            restApiId=api_id,
            resourceId=toggle_id,
            httpMethod='PUT',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for toggle
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=toggle_id,
            httpMethod='PUT',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "toggled"}'
            }
        )
        
        # Create method response for toggle
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=toggle_id,
            httpMethod='PUT',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create effects resource
        effects_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='effects'
        )
        effects_id = effects_resource['id']
        
        # Create rainbow resource
        rainbow_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=effects_id,
            pathPart='rainbow'
        )
        rainbow_id = rainbow_resource['id']
        
        # Create PUT method for rainbow with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=rainbow_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for rainbow
        api_client.put_integration(
            restApiId=api_id,
            resourceId=rainbow_id,
            httpMethod='PUT',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for rainbow
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=rainbow_id,
            httpMethod='PUT',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "rainbow effect triggered"}'
            }
        )
        
        # Create method response for rainbow
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=rainbow_id,
            httpMethod='PUT',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create pulse resource
        pulse_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=effects_id,
            pathPart='pulse'
        )
        pulse_id = pulse_resource['id']
        
        # Create PUT method for pulse with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=pulse_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for pulse
        api_client.put_integration(
            restApiId=api_id,
            resourceId=pulse_id,
            httpMethod='PUT',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for pulse
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=pulse_id,
            httpMethod='PUT',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "pulse effect triggered"}'
            }
        )
        
        # Create method response for pulse
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=pulse_id,
            httpMethod='PUT',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create off resource
        off_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='off'
        )
        off_id = off_resource['id']
        
        # Create PUT method for off with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=off_id,
            httpMethod='PUT',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for off
        api_client.put_integration(
            restApiId=api_id,
            resourceId=off_id,
            httpMethod='PUT',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for off
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=off_id,
            httpMethod='PUT',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "LEDs turned off"}'
            }
        )
        
        # Create method response for off
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=off_id,
            httpMethod='PUT',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Create health resource
        health_resource = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='health'
        )
        health_id = health_resource['id']
        
        # Create GET method for health with API key required
        api_client.put_method(
            restApiId=api_id,
            resourceId=health_id,
            httpMethod='GET',
            authorizationType='NONE',
            apiKeyRequired=True
        )
        
        # Create mock integration for health
        api_client.put_integration(
            restApiId=api_id,
            resourceId=health_id,
            httpMethod='GET',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Create integration response for health
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=health_id,
            httpMethod='GET',
            statusCode='200',
            responseTemplates={
                'application/json': '{"status": "healthy"}'
            }
        )
        
        # Create method response for health
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=health_id,
            httpMethod='GET',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            }
        )
        
        # Enable CORS for all resources
        enable_cors_for_resource(api_client, api_id, resource_id)
        enable_cors_for_resource(api_client, api_id, toggle_id)
        enable_cors_for_resource(api_client, api_id, rainbow_id)
        enable_cors_for_resource(api_client, api_id, pulse_id)
        enable_cors_for_resource(api_client, api_id, off_id)
        enable_cors_for_resource(api_client, api_id, health_id)
        
        # Create deployment
        deployment = api_client.create_deployment(
            restApiId=api_id,
            stageName='prod',
            description='Production deployment'
        )
        
        # Add tags to stage
        try:
            api_client.tag_resource(
                resourceArn=f"arn:aws:apigateway:{AWS_REGION}::/restapis/{api_id}/stages/prod",
                tags={
                    'project': 'blinkysign'
                }
            )
        except Exception as e:
            logger.warning(f"Could not tag API Gateway stage: {e}")
        
        # Create API key
        api_key_name = f"{THING_NAME}-api-key"
        api_key_response = api_client.create_api_key(
            name=api_key_name,
            description='API key for BlinkySign',
            enabled=True,
            tags={
                'project': 'blinkysign'
            }
        )
        api_key_id = api_key_response['id']
        api_key_value = api_key_response['value']
        logger.info(f"Created API key: {api_key_id}")
        
        # Create usage plan
        usage_plan_name = f"{THING_NAME}-usage-plan"
        usage_plan_response = api_client.create_usage_plan(
            name=usage_plan_name,
            description='Usage plan for BlinkySign',
            apiStages=[
                {
                    'apiId': api_id,
                    'stage': 'prod'
                }
            ],
            tags={
                'project': 'blinkysign'
            }
        )
        usage_plan_id = usage_plan_response['id']
        logger.info(f"Created usage plan: {usage_plan_id}")
        
        # Add API key to usage plan
        api_client.create_usage_plan_key(
            usagePlanId=usage_plan_id,
            keyId=api_key_id,
            keyType='API_KEY'
        )
        logger.info(f"Added API key to usage plan")
        
        # Save API key to file
        with open('certs/api_key.txt', 'w') as f:
            f.write(api_key_value)
        logger.info(f"Saved API key to 'certs/api_key.txt'")
        
        # Construct API endpoint
        api_endpoint = f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com/prod"
        
        # Update .env file with API endpoint
        update_env_file('API_ENDPOINT', api_endpoint)
        
        # Update control panel HTML with the new API endpoint
        update_control_panel_html(api_endpoint, api_key_value)
        
        logger.info(f"Created API Gateway methods for all resources")
        logger.info(f"API Gateway endpoint: {api_endpoint}")
        
        return {
            'apiId': api_id,
            'endpoint': api_endpoint,
            'apiKeyId': api_key_id,
            'apiKeyValue': api_key_value
        }
        
    except Exception as e:
        logger.error(f"Error creating API Gateway: {e}")
        raise

def enable_cors_for_resource(api_client, api_id, resource_id):
    """Enable CORS for a resource"""
    try:
        # Add OPTIONS method
        api_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            authorizationType='NONE',
            apiKeyRequired=False
        )
        
        # Add mock integration for OPTIONS
        api_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            type='MOCK',
            requestTemplates={
                'application/json': '{"statusCode": 200}'
            }
        )
        
        # Add method response for OPTIONS
        api_client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseModels={
                'application/json': 'Empty'
            },
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True,
                'method.response.header.Access-Control-Allow-Origin': True
            }
        )
        
        # Add integration response for OPTIONS
        api_client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'",
                'method.response.header.Access-Control-Allow-Origin': "'*'"
            },
            responseTemplates={
                'application/json': ''
            }
        )
        
        logger.info(f"Enabled CORS for resource {resource_id}")
    except Exception as e:
        logger.warning(f"Could not enable CORS for resource {resource_id}: {e}")

def update_env_file(key, value):
    """Update a key in the .env file"""
    try:
        # Create .env file from example if it doesn't exist
        if not os.path.exists('.env') and os.path.exists('.env.example'):
            with open('.env.example', 'r') as src, open('.env', 'w') as dest:
                dest.write(src.read())
            logger.info("Created .env file from .env.example")
        elif not os.path.exists('.env'):
            # Create a new .env file with minimal content
            with open('.env', 'w') as f:
                f.write(f"{key}={value}\n")
            logger.info(f"Created new .env file with {key}={value}")
            return
            
        # Read the current .env file
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        # Update the key with the new value
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                updated = True
                break
        
        # Add the key if it doesn't exist
        if not updated:
            lines.append(f"{key}={value}\n")
            
        # Write the updated content back to the file
        with open('.env', 'w') as f:
            f.writelines(lines)
            
        logger.info(f"Updated {key} in .env file")
            
    except Exception as e:
        logger.error(f"Error updating .env file: {e}")

def update_control_panel_html(api_endpoint, api_key):
    """Update the control panel HTML with the new API endpoint and key"""
    try:
        control_panel_path = 'control_panel.html'
        
        # Check if the file exists
        if not os.path.exists(control_panel_path):
            logger.warning(f"Control panel file not found: {control_panel_path}")
            return
        
        # Read the current HTML file
        with open(control_panel_path, 'r') as f:
            html_content = f.read()
        
        # Update the AWS endpoint
        aws_endpoint_pattern = r"aws: '(https://[^']*)',"
        new_aws_endpoint = f"aws: '{api_endpoint}',"
        html_content = re.sub(aws_endpoint_pattern, new_aws_endpoint, html_content)
        
        # Add a placeholder for the API key
        api_key_placeholder = f"<!-- API Key: {api_key} -->"
        if "<!-- API Key:" not in html_content:
            html_content = html_content.replace("<head>", f"<head>\n    {api_key_placeholder}")
        
        # Write the updated content back to the file
        with open(control_panel_path, 'w') as f:
            f.write(html_content)
            
        logger.info(f"Updated control panel HTML with new API endpoint")
        
    except Exception as e:
        logger.error(f"Error updating control panel HTML: {e}")

def get_account_id():
    """Get the AWS account ID"""
    try:
        sts_client = boto3.client('sts')
        return sts_client.get_caller_identity()['Account']
    except Exception as e:
        logger.error(f"Error getting AWS account ID: {e}")
        return "*"  # Fallback to wildcard

if __name__ == "__main__":
    logger.info("Setting up AWS resources for BlinkySign...")
    
    try:
        iot_result = create_iot_thing()
        logger.info(f"IoT Thing created: {iot_result['thingName']}")
        
        api_result = create_api_gateway()
        logger.info(f"API Gateway created: {api_result['endpoint']}")
        logger.info(f"API Key created: {api_result['apiKeyId']}")
        logger.info(f"API Key value saved to certs/api_key.txt")
        
        logger.info("AWS setup completed successfully!")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")