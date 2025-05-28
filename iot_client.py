#!/usr/bin/env python3
"""
AWS IoT Client for BlinkySign
Connects to AWS IoT Core and subscribes to topics for controlling the sign
"""
import os
import json
import time
import logging
import threading
import RPi.GPIO as GPIO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
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
IOT_ENDPOINT = os.getenv('IOT_ENDPOINT')
THING_NAME = os.getenv('IOT_THING_NAME', 'blinkysign')
LED_PIN = int(os.getenv('LED_PIN', 18))

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# Current state
current_state = {
    "muted": False,
    "led_on": False
}

def update_led_state():
    """Update the LED based on current state"""
    if current_state["muted"]:
        GPIO.output(LED_PIN, GPIO.HIGH)  # Turn on LED when muted
        current_state["led_on"] = True
    else:
        GPIO.output(LED_PIN, GPIO.LOW)   # Turn off LED when unmuted
        current_state["led_on"] = False
    logger.info(f"LED state updated: {'ON' if current_state['led_on'] else 'OFF'}")

def status_callback(client, userdata, message):
    """Callback when status messages are received"""
    try:
        payload = json.loads(message.payload.decode('utf-8'))
        logger.info(f"Received message: {payload}")
        
        if "muted" in payload:
            current_state["muted"] = bool(payload["muted"])
            update_led_state()
            
            # Publish state update
            mqtt_client.publish(
                f"{THING_NAME}/state",
                json.dumps(current_state),
                0
            )
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def toggle_callback(client, userdata, message):
    """Callback when toggle messages are received"""
    try:
        logger.info("Received toggle command")
        current_state["muted"] = not current_state["muted"]
        update_led_state()
        
        # Publish state update
        mqtt_client.publish(
            f"{THING_NAME}/state",
            json.dumps(current_state),
            0
        )
    except Exception as e:
        logger.error(f"Error processing toggle: {e}")

def connect_to_iot():
    """Connect to AWS IoT Core"""
    # Initialize MQTT client
    mqtt_client = AWSIoTMQTTClient(THING_NAME)
    mqtt_client.configureEndpoint(IOT_ENDPOINT, 8883)
    mqtt_client.configureCredentials(
        "certs/AmazonRootCA1.pem",
        "certs/private.key",
        "certs/certificate.pem"
    )
    
    # Configure MQTT client
    mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
    mqtt_client.configureOfflinePublishQueueing(-1)
    mqtt_client.configureDrainingFrequency(2)
    mqtt_client.configureConnectDisconnectTimeout(10)
    mqtt_client.configureMQTTOperationTimeout(5)
    
    # Connect
    logger.info(f"Connecting to AWS IoT Core at {IOT_ENDPOINT}...")
    mqtt_client.connect()
    logger.info("Connected to AWS IoT Core")
    
    # Subscribe to topics
    mqtt_client.subscribe(f"{THING_NAME}/status", 1, status_callback)
    mqtt_client.subscribe(f"{THING_NAME}/toggle", 1, toggle_callback)
    logger.info(f"Subscribed to {THING_NAME}/status and {THING_NAME}/toggle topics")
    
    # Publish initial state
    mqtt_client.publish(
        f"{THING_NAME}/state",
        json.dumps(current_state),
        0
    )
    
    return mqtt_client

def heartbeat_task(mqtt_client):
    """Send periodic heartbeat messages"""
    while True:
        try:
            mqtt_client.publish(
                f"{THING_NAME}/heartbeat",
                json.dumps({
                    "timestamp": time.time(),
                    "state": current_state
                }),
                0
            )
            time.sleep(60)  # Send heartbeat every minute
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            time.sleep(5)  # Retry after 5 seconds on error

if __name__ == "__main__":
    try:
        # Connect to AWS IoT Core
        mqtt_client = connect_to_iot()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=heartbeat_task, args=(mqtt_client,))
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
        # Initial LED state
        update_led_state()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Clean up GPIO on exit
        GPIO.cleanup()