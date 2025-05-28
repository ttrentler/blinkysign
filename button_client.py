#!/usr/bin/env python3
"""
Button Client for BlinkySign
Simple client to send HTTP requests when a button is pressed
"""
import os
import time
import json
import logging
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
API_ENDPOINT = os.getenv('API_ENDPOINT', 'http://localhost:5000')

def send_toggle_request():
    """Send a toggle request to the API"""
    try:
        response = requests.put(f"{API_ENDPOINT}/toggle")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Toggle successful: {data['message']}")
            return True
        else:
            logger.error(f"Toggle failed with status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending toggle request: {e}")
        return False

def send_set_request(muted=True):
    """Send a request to set the mute status explicitly"""
    try:
        response = requests.put(
            f"{API_ENDPOINT}/set",
            json={"muted": muted},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Set status successful: {data['message']}")
            return True
        else:
            logger.error(f"Set status failed with status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending set request: {e}")
        return False

def get_current_status():
    """Get the current status from the API"""
    try:
        response = requests.get(f"{API_ENDPOINT}/status")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Current status: {'muted' if data['muted'] else 'unmuted'}")
            return data
        else:
            logger.error(f"Get status failed with status code {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return None

if __name__ == "__main__":
    logger.info("Button client started")
    logger.info(f"API endpoint: {API_ENDPOINT}")
    
    # Simple demo - toggle every 5 seconds
    try:
        while True:
            logger.info("Press Ctrl+C to exit")
            logger.info("Sending toggle request...")
            send_toggle_request()
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Button client stopped")