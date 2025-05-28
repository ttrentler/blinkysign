#!/usr/bin/env python3
"""
Physical Button Client for BlinkySign
Uses a physical button connected to Raspberry Pi GPIO to send toggle requests
"""
import os
import time
import logging
import requests
import RPi.GPIO as GPIO
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
BUTTON_PIN = int(os.getenv('BUTTON_PIN', 17))  # Default to GPIO 17
DEBOUNCE_TIME = 0.3  # Debounce time in seconds

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Last button press time for debouncing
last_press_time = 0

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

def button_callback(channel):
    """Callback function for button press"""
    global last_press_time
    
    # Debounce
    current_time = time.time()
    if (current_time - last_press_time) < DEBOUNCE_TIME:
        return
    
    last_press_time = current_time
    logger.info("Button pressed!")
    send_toggle_request()

if __name__ == "__main__":
    try:
        logger.info("Physical button client started")
        logger.info(f"API endpoint: {API_ENDPOINT}")
        logger.info(f"Button connected to GPIO {BUTTON_PIN}")
        
        # Add event detection for button press
        GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, 
                             callback=button_callback, bouncetime=300)
        
        # Keep the script running
        logger.info("Waiting for button presses... (Press Ctrl+C to exit)")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Button client stopped")
    finally:
        GPIO.cleanup()