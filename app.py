#!/usr/bin/env python3
"""
BlinkySign - Main application for controlling LED sign based on mute status
"""
import os
import time
import json
import logging
from flask import Flask, request, jsonify
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

# Initialize Flask app
app = Flask(__name__)

# GPIO Configuration
LED_PIN = int(os.getenv('LED_PIN', 18))  # Default to GPIO 18 if not specified
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

@app.route('/status', methods=['GET'])
def get_status():
    """Get the current mute status"""
    return jsonify(current_state)

@app.route('/toggle', methods=['PUT'])
def toggle_mute():
    """Toggle the mute status"""
    current_state["muted"] = not current_state["muted"]
    update_led_state()
    return jsonify({
        "status": "success",
        "message": f"Mute toggled to {'muted' if current_state['muted'] else 'unmuted'}",
        "state": current_state
    })

@app.route('/set', methods=['PUT'])
def set_status():
    """Set the mute status explicitly"""
    data = request.get_json()
    if data and "muted" in data:
        current_state["muted"] = bool(data["muted"])
        update_led_state()
        return jsonify({
            "status": "success",
            "message": f"Status set to {'muted' if current_state['muted'] else 'unmuted'}",
            "state": current_state
        })
    return jsonify({
        "status": "error",
        "message": "Invalid request. Expected JSON with 'muted' field."
    }), 400

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    try:
        # Initial LED state
        update_led_state()
        # Start the Flask app
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Clean up GPIO on exit
        GPIO.cleanup()