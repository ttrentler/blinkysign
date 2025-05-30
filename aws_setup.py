#!/usr/bin/env python3
"""
AWS Setup Script for BlinkySign
Creates necessary AWS resources for the project
"""
import boto3
import json
import os
import logging
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
            iot_client.tag_resource(
                resourceArn=f"arn:aws:iot:{AWS_REGION}:*:policy/{policy_name}",
                tags=[PROJECT_TAG]
            )
        
        # Create keys and certificate
        cert_response = iot_client.create_keys_and_certificate(setAsActive=True)
        cert_arn = cert_response['certificateArn']
        cert_id = cert_response['certificateId']
        cert_pem = cert_response['certificatePem']
        private_key = cert_response['keyPair']['PrivateKey']
        
        logger.info(f"Created certificate: {cert_id}")
        
        # Add tags to certificate
        iot_client.tag_resource(
            resourceArn=cert_arn,
            tags=[PROJECT_TAG]
        )
        
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
            }
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
        
        # Create GET method
        api_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='GET',
            authorizationType='NONE'
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
        
        # Create PUT method
        api_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='PUT',
            authorizationType='NONE'
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
        
        # Create deployment
        deployment = api_client.create_deployment(
            restApiId=api_id,
            stageName='prod',
            description='Production deployment'
        )
        
        # Add tags to stage
        api_client.tag_resource(
            resourceArn=f"arn:aws:apigateway:{AWS_REGION}::/restapis/{api_id}/stages/prod",
            tags={
                'project': 'blinkysign'
            }
        )
        
        # Construct API endpoint
        api_endpoint = f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com/prod"
        
        # Update .env file with API endpoint
        update_env_file('API_ENDPOINT', api_endpoint)
        
        logger.info(f"Created API Gateway methods for /status resource")
        logger.info(f"API Gateway endpoint: {api_endpoint}")
        
        return {
            'apiId': api_id,
            'endpoint': api_endpoint
        }
        
    except Exception as e:
        logger.error(f"Error creating API Gateway: {e}")
        raise

def update_env_file(key, value):
    """Update a key in the .env file"""
    try:
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
        
        # Write the updated content back to the file
        with open('.env', 'w') as f:
            f.writelines(lines)
            
        if updated:
            logger.info(f"Updated {key} in .env file")
        else:
            logger.warning(f"Could not find {key} in .env file")
            
    except Exception as e:
        logger.error(f"Error updating .env file: {e}")

if __name__ == "__main__":
    logger.info("Setting up AWS resources for BlinkySign...")
    
    try:
        iot_result = create_iot_thing()
        logger.info(f"IoT Thing created: {iot_result['thingName']}")
        
        api_result = create_api_gateway()
        logger.info(f"API Gateway created: {api_result['endpoint']}")
        
        logger.info("AWS setup completed successfully!")
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")