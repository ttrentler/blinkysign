#!/usr/bin/env python3
"""
AWS Deployment Script for BlinkySign
Deploys CloudFormation stack and updates local configuration
"""
import boto3
import os
import logging
import json
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
STACK_NAME = f"{THING_NAME}-stack"

def deploy_cloudformation():
    """Deploy CloudFormation stack"""
    try:
        cf_client = boto3.client('cloudformation', region_name=AWS_REGION)
        
        # Read template file
        with open('cloudformation.yaml', 'r') as f:
            template_body = f.read()
        
        # Check if stack exists
        try:
            cf_client.describe_stacks(StackName=STACK_NAME)
            stack_exists = True
        except cf_client.exceptions.ClientError:
            stack_exists = False
        
        # Create or update stack
        parameters = [
            {
                'ParameterKey': 'ThingName',
                'ParameterValue': THING_NAME
            },
            {
                'ParameterKey': 'ProjectTag',
                'ParameterValue': 'blinkysign'
            }
        ]
        
        if stack_exists:
            logger.info(f"Updating stack {STACK_NAME}...")
            cf_client.update_stack(
                StackName=STACK_NAME,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=['CAPABILITY_IAM']
            )
        else:
            logger.info(f"Creating stack {STACK_NAME}...")
            cf_client.create_stack(
                StackName=STACK_NAME,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=['CAPABILITY_IAM']
            )
        
        # Wait for stack to complete
        waiter = cf_client.get_waiter('stack_create_complete' if not stack_exists else 'stack_update_complete')
        logger.info("Waiting for stack operation to complete...")
        waiter.wait(StackName=STACK_NAME)
        
        # Get stack outputs
        stack = cf_client.describe_stacks(StackName=STACK_NAME)['Stacks'][0]
        outputs = {output['OutputKey']: output['OutputValue'] for output in stack['Outputs']}
        
        # Update .env file
        update_env_file('API_ENDPOINT', outputs['ApiEndpoint'])
        update_env_file('API_KEY', outputs['ApiKey'])
        update_env_file('IOT_ENDPOINT', outputs['IoTEndpoint'])
        update_env_file('IOT_THING_NAME', outputs['ThingName'])
        
        # Update control panel HTML
        update_control_panel_html(outputs['ApiEndpoint'], outputs['ApiKey'])
        
        logger.info("Stack deployment completed successfully!")
        logger.info(f"API Endpoint: {outputs['ApiEndpoint']}")
        logger.info(f"IoT Endpoint: {outputs['IoTEndpoint']}")
        logger.info(f"Thing Name: {outputs['ThingName']}")
        logger.info("API Key saved to .env file")
        
    except Exception as e:
        logger.error(f"Error deploying stack: {e}")
        raise

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
        
        # Replace the API Gateway URL placeholder
        html_content = html_content.replace('API_GATEWAY_URL_PLACEHOLDER', api_endpoint)
        
        # Replace the API key placeholder
        html_content = html_content.replace('API_KEY_PLACEHOLDER', api_key)
        
        # Write the updated content back to the file
        with open(control_panel_path, 'w') as f:
            f.write(html_content)
            
        logger.info(f"Updated control panel HTML with new API endpoint and API key")
        
    except Exception as e:
        logger.error(f"Error updating control panel HTML: {e}")

if __name__ == "__main__":
    logger.info("Starting AWS deployment...")
    deploy_cloudformation()
    
    # Connect API Gateway to IoT Core
    logger.info("Connecting API Gateway to IoT Core...")
    try:
        import connect_api_to_iot
        connect_api_to_iot.ensure_iot_permissions()
        role_arn = connect_api_to_iot.create_iot_role()
        connect_api_to_iot.create_iot_topic_rules(role_arn)
        connect_api_to_iot.update_api_gateway_integration()
        logger.info("Successfully connected API Gateway to IoT Core!")
    except Exception as e:
        logger.error(f"Error connecting API Gateway to IoT Core: {e}")
        logger.error("Please run 'python connect_api_to_iot.py' manually to complete the setup.")
    
    logger.info("Deployment completed!")