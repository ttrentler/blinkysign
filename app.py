#!/usr/bin/env python3
"""
BlinkySign - Main application for controlling LED sign based on mute status
"""
import os
import time
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from led_controller import led_controller

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
# Enable CORS with more explicit configuration
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "X-Api-Key"]}})

# Current state
current_state = {
    "muted": False,
    "led_on": False
}

def update_led_state():
    """Update the LED based on current state"""
    if current_state["muted"]:
        led_controller.set_muted()
        current_state["led_on"] = True
    else:
        led_controller.set_unmuted()
        current_state["led_on"] = True
    logger.info(f"LED state updated: {'MUTED' if current_state['muted'] else 'UNMUTED'}")

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

@app.route('/effects/rainbow', methods=['PUT'])
def rainbow_effect():
    """Trigger rainbow effect"""
    try:
        led_controller.rainbow_cycle()
        update_led_state()  # Return to normal state after effect
        return jsonify({
            "status": "success",
            "message": "Rainbow effect completed"
        })
    except Exception as e:
        logger.error(f"Error in rainbow effect: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/effects/pulse', methods=['PUT'])
def pulse_effect():
    """Trigger pulse effect"""
    try:
        data = request.get_json() or {}
        color = data.get("color", "blue").lower()
        cycles = int(data.get("cycles", 3))
        
        # Map color names to RGB values
        color_map = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "purple": (128, 0, 128),
            "cyan": (0, 255, 255),
            "white": (255, 255, 255)
        }
        
        rgb_color = color_map.get(color, (0, 0, 255))  # Default to blue
        
        led_controller.pulse(rgb_color, cycles=cycles)
        update_led_state()  # Return to normal state after effect
        
        return jsonify({
            "status": "success",
            "message": f"Pulse effect completed with color {color}"
        })
    except Exception as e:
        logger.error(f"Error in pulse effect: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/off', methods=['PUT'])
def turn_off():
    """Turn off all LEDs"""
    try:
        led_controller.turn_off()
        current_state["led_on"] = False
        return jsonify({
            "status": "success",
            "message": "LEDs turned off",
            "state": current_state
        })
    except Exception as e:
        logger.error(f"Error turning off LEDs: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    try:
        # Show connecting state
        led_controller.set_connecting()
        time.sleep(1)
        
        # Initial LED state
        update_led_state()
        
        # Start the Flask app
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error: {e}")
        led_controller.set_error()
        time.sleep(2)
        led_controller.turn_off()