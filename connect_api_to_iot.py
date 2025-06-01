#!/usr/bin/env python3
"""
Connect API Gateway to IoT Core for BlinkySign
"""
import boto3
import json
import os
import logging
import time
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
API_ID = os.getenv('API_ID', '')  # Will be extracted from API_ENDPOINT if not provided

def get_account_id():
    """Get the AWS account ID"""
    sts_client = boto3.client('sts')
    return sts_client.get_caller_identity()['Account']

def create_iot_role():
    """Create IAM role for IoT to republish messages"""
    iam_client = boto3.client('iam')
    role_name = f"{THING_NAME}-iot-role"
    
    # Check if role already exists
    try:
        iam_client.get_role(RoleName=role_name)
        logger.info(f"Role {role_name} already exists")
        
        # Get the role ARN
        role_response = iam_client.get_role(RoleName=role_name)
        role_arn = role_response['Role']['Arn']
        return role_arn
    except iam_client.exceptions.NoSuchEntityException:
        # Create the role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "iot.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        role_response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Role for {THING_NAME} IoT republish actions"
        )
        
        role_arn = role_response['Role']['Arn']
        logger.info(f"Created IAM role: {role_name}")
        
        # Attach policy to the role
        account_id = get_account_id()
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "iot:Publish",
                    "Resource": f"arn:aws:iot:{AWS_REGION}:{account_id}:topic/{THING_NAME}/*"
                }
            ]
        }
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{THING_NAME}-iot-publish-policy",
            PolicyDocument=json.dumps(policy_document)
        )
        
        logger.info(f"Attached policy to role {role_name}")
        
        # Wait for role to propagate
        logger.info("Waiting for role to propagate...")
        time.sleep(10)
        
        return role_arn

def create_iot_topic_rules(role_arn):
    """Create IoT topic rules to forward API requests to device"""
    # Try with a new client session to pick up the new permissions
    session = boto3.session.Session()
    iot_client = session.client('iot', region_name=AWS_REGION)
    
    # Create rules for each API endpoint
    endpoints = ['toggle', 'status', 'set', 'effects/rainbow', 'effects/pulse', 'off']
    
    # First, try to delete any existing rules that might be causing conflicts
    for endpoint in endpoints:
        rule_name = f"{THING_NAME}_{endpoint.replace('/', '_')}_rule"
        
        try:
            # Try to delete the rule if it exists
            try:
                iot_client.delete_topic_rule(ruleName=rule_name)
                logger.info(f"Deleted existing rule: {rule_name}")
                time.sleep(2)  # Give AWS time to process the deletion
            except Exception:
                # Rule doesn't exist or can't be deleted, continue
                pass
            
            # Create the rule
            topic_pattern = endpoint.replace('/', '\/') 
            sql_statement = f"SELECT * FROM '$aws/events/api/{THING_NAME}/{topic_pattern}'"
            
            rule_payload = {
                "sql": sql_statement,
                "actions": [
                    {
                        "republish": {
                            "topic": f"{THING_NAME}/{endpoint}",
                            "roleArn": role_arn
                        }
                    }
                ],
                "ruleDisabled": False
            }
            
            iot_client.create_topic_rule(
                ruleName=rule_name,
                topicRulePayload=rule_payload
            )
            
            logger.info(f"Created IoT topic rule: {rule_name}")
            
        except Exception as e:
            logger.warning(f"Could not create rule {rule_name}: {e}")
            # Continue with other rules even if one fails

def update_api_gateway_integration():
    """Update API Gateway to use AWS service integration"""
    # Extract API ID from API_ENDPOINT if not provided
    global API_ID
    if not API_ID:
        api_endpoint = os.getenv('API_ENDPOINT', '')
        if api_endpoint:
            # Extract API ID from endpoint URL
            # Format: https://abcdef123.execute-api.region.amazonaws.com/stage
            parts = api_endpoint.split('.')
            if len(parts) > 0:
                API_ID = parts[0].split('//')[1]
        
    if not API_ID:
        logger.error("API_ID not found. Please set API_ID environment variable.")
        return False
    
    api_client = boto3.client('apigateway', region_name=AWS_REGION)
    
    # Get resources
    resources = api_client.get_resources(restApiId=API_ID)
    
    # Update integration for each resource
    for resource in resources['items']:
        resource_id = resource['id']
        
        # Skip root resource
        if resource['path'] == '/':
            continue
        
        # Get resource methods
        try:
            for method in ['GET', 'PUT']:
                try:
                    # Check if method exists
                    api_client.get_method(
                        restApiId=API_ID,
                        resourceId=resource_id,
                        httpMethod=method
                    )
                    
                    # Update integration
                    path = resource['path'].lstrip('/')
                    
                    api_client.put_integration(
                        restApiId=API_ID,
                        resourceId=resource_id,
                        httpMethod=method,
                        type='AWS',
                        integrationHttpMethod='POST',
                        uri=f"arn:aws:apigateway:{AWS_REGION}:iot:path/topics/$aws/events/api/{THING_NAME}/{path}",
                        requestTemplates={
                            'application/json': '{"message": $input.json("$")}'
                        }
                    )
                    
                    logger.info(f"Updated integration for {method} {path}")
                    
                except Exception as e:
                    # Method doesn't exist for this resource
                    pass
        except Exception as e:
            logger.warning(f"Could not update resource {resource['path']}: {e}")
    
    # Create deployment
    api_client.create_deployment(
        restApiId=API_ID,
        stageName='prod',
        description='Updated integration with IoT'
    )
    
    logger.info("Deployed API with updated integrations")
    return True

def ensure_iot_permissions():
    """Add necessary IoT permissions to the current user"""
    try:
        iam_client = boto3.client('iam')
        
        # Get current user info
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        user_arn = caller_identity['Arn']
        account_id = caller_identity['Account']
        
        # Determine if this is a user or role
        if ':user/' in user_arn:
            username = user_arn.split('/')[-1]
            is_role = False
        elif ':assumed-role/' in user_arn:
            role_name = user_arn.split('/')[-2]
            is_role = True
        else:
            logger.warning(f"Could not determine if ARN is user or role: {user_arn}")
            return False
            
        policy_name = f"{THING_NAME}-iot-admin-policy"
        
        # Create policy document with full IoT permissions
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iot:*"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # Check if policy exists
        try:
            policy = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{account_id}:policy/{policy_name}")
            policy_arn = policy['Policy']['Arn']
            logger.info(f"Policy {policy_name} already exists")
        except iam_client.exceptions.NoSuchEntityException:
            # Create policy
            policy_response = iam_client.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description=f"IoT admin permissions for {THING_NAME}"
            )
            policy_arn = policy_response['Policy']['Arn']
            logger.info(f"Created policy {policy_name}")
        
        # Attach policy to user or role
        try:
            if is_role:
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                logger.info(f"Attached policy {policy_name} to role {role_name}")
            else:
                iam_client.attach_user_policy(
                    UserName=username,
                    PolicyArn=policy_arn
                )
                logger.info(f"Attached policy {policy_name} to user {username}")
            
            # Wait for permissions to propagate
            logger.info("Waiting for permissions to propagate...")
            time.sleep(15)  # Increased wait time
        except Exception as e:
            logger.warning(f"Could not attach policy: {e}")
            
        # Create inline policy for immediate effect
        try:
            if is_role:
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"{policy_name}-inline",
                    PolicyDocument=json.dumps(policy_document)
                )
                logger.info(f"Added inline policy to role {role_name}")
            else:
                iam_client.put_user_policy(
                    UserName=username,
                    PolicyName=f"{policy_name}-inline",
                    PolicyDocument=json.dumps(policy_document)
                )
                logger.info(f"Added inline policy to user {username}")
        except Exception as e:
            logger.warning(f"Could not add inline policy: {e}")
            
        return True
    except Exception as e:
        logger.error(f"Error ensuring IoT permissions: {e}")
        return False

if __name__ == "__main__":
    logger.info("Connecting API Gateway to IoT Core...")
    
    try:
        # Ensure we have IoT permissions
        ensure_iot_permissions()
        
        # Create IAM role
        role_arn = create_iot_role()
        
        # Create IoT topic rules
        create_iot_topic_rules(role_arn)
        
        # Update API Gateway integration
        update_api_gateway_integration()
        
        logger.info("Successfully connected API Gateway to IoT Core!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
