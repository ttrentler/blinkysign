#!/usr/bin/env python3
"""
AWS Cleanup Script for BlinkySign
Deletes all AWS resources created for the project
"""
import boto3
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

def cleanup_iot_resources():
    """Delete IoT Core resources"""
    try:
        iot_client = boto3.client('iot', region_name=AWS_REGION)
        
        # Get certificates attached to the thing
        principals = iot_client.list_thing_principals(
            thingName=THING_NAME
        )
        
        for principal in principals.get('principals', []):
            cert_id = principal.split('/')[-1]
            logger.info(f"Found certificate: {cert_id}")
            
            # Get policies attached to the certificate
            policies = iot_client.list_attached_policies(
                target=principal
            )
            
            # Detach policies from certificate
            for policy in policies.get('policies', []):
                policy_name = policy['policyName']
                logger.info(f"Detaching policy {policy_name} from certificate {cert_id}")
                iot_client.detach_policy(
                    policyName=policy_name,
                    target=principal
                )
                
                # Delete policy
                logger.info(f"Deleting policy: {policy_name}")
                iot_client.delete_policy(
                    policyName=policy_name
                )
            
            # Detach certificate from thing
            logger.info(f"Detaching certificate {cert_id} from thing {THING_NAME}")
            iot_client.detach_thing_principal(
                thingName=THING_NAME,
                principal=principal
            )
            
            # Update certificate to inactive
            logger.info(f"Deactivating certificate: {cert_id}")
            iot_client.update_certificate(
                certificateId=cert_id,
                newStatus='INACTIVE'
            )
            
            # Delete certificate
            logger.info(f"Deleting certificate: {cert_id}")
            iot_client.delete_certificate(
                certificateId=cert_id,
                forceDelete=True
            )
        
        # Delete thing
        logger.info(f"Deleting thing: {THING_NAME}")
        iot_client.delete_thing(
            thingName=THING_NAME
        )
        
        logger.info("IoT resources deleted successfully")
        
    except Exception as e:
        logger.error(f"Error deleting IoT resources: {e}")

def cleanup_api_gateway():
    """Delete API Gateway resources"""
    try:
        api_client = boto3.client('apigateway', region_name=AWS_REGION)
        
        # List APIs
        apis = api_client.get_rest_apis()
        
        # Find and delete the BlinkySign API
        for api in apis.get('items', []):
            if api['name'] == f"{THING_NAME}-api":
                api_id = api['id']
                logger.info(f"Found API Gateway: {api_id}")
                
                # Delete API
                logger.info(f"Deleting API Gateway: {api_id}")
                api_client.delete_rest_api(
                    restApiId=api_id
                )
                
                logger.info("API Gateway deleted successfully")
                return
        
        logger.info("No matching API Gateway found")
        
    except Exception as e:
        logger.error(f"Error deleting API Gateway: {e}")

if __name__ == "__main__":
    logger.info("Starting cleanup of AWS resources...")
    
    # Confirm deletion
    confirm = input(f"This will delete all AWS resources for {THING_NAME}. Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        logger.info("Cleanup cancelled")
        exit(0)
    
    # Delete resources
    cleanup_iot_resources()
    cleanup_api_gateway()
    
    logger.info("AWS cleanup completed")