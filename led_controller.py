#!/usr/bin/env python3
"""
LED Controller for BlinkySign
Controls WS2812B LED strips connected to Raspberry Pi using SPI interface
"""
import os
import time
import logging
import board
import busio
import neopixel_spi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# LED Configuration
LED_COUNT = int(os.getenv('LED_COUNT', 30))  # Number of LED pixels per strip
LED_BRIGHTNESS = float(os.getenv('LED_BRIGHTNESS', 0.5))  # Brightness (0.0 to 1.0)

# Color definitions
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
WHITE = (255, 255, 255)
OFF = (0, 0, 0)

# Default colors for different states
MUTED_COLOR = RED
UNMUTED_COLOR = GREEN
CONNECTING_COLOR = BLUE
ERROR_COLOR = YELLOW

class LEDController:
    """Controller for WS2812B LED strips using SPI interface"""
    
    def __init__(self):
        """Initialize LED strips using SPI"""
        self.strips = []
        self.active_strips = 0
        
        # Try to initialize SPI bus
        try:
            # Initialize main SPI bus
            spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
            
            # Create NeoPixel_SPI object
            pixels = neopixel_spi.NeoPixel_SPI(
                spi, LED_COUNT, brightness=LED_BRIGHTNESS, auto_write=False
            )
            
            self.strips.append(pixels)
            self.active_strips += 1
            logger.info("SPI NeoPixel strip initialized")
            
            # Additional strips could be added here if multiple SPI buses are available
            # For now, we'll use a single strip as demonstrated in boardtest.py
            
        except Exception as e:
            logger.error(f"Failed to initialize LED strip: {e}")
        
        logger.info(f"Initialized {self.active_strips} LED strips")
    
    def set_all_strips(self, color):
        """Set all strips to the same color"""
        for strip in self.strips:
            strip.fill(color)
            strip.show()
        logger.info(f"All strips set to color: {color}")
    
    def set_strip(self, strip_index, color):
        """Set a specific strip to a color"""
        if 0 <= strip_index < len(self.strips):
            self.strips[strip_index].fill(color)
            self.strips[strip_index].show()
            logger.info(f"Strip {strip_index} set to color: {color}")
        else:
            logger.error(f"Invalid strip index: {strip_index}")
    
    def set_muted(self):
        """Set LEDs to muted state (red)"""
        self.set_all_strips(MUTED_COLOR)
        logger.info("LEDs set to MUTED state")
    
    def set_unmuted(self):
        """Set LEDs to unmuted state (green)"""
        self.set_all_strips(UNMUTED_COLOR)
        logger.info("LEDs set to UNMUTED state")
    
    def set_connecting(self):
        """Set LEDs to connecting state (blue)"""
        self.set_all_strips(CONNECTING_COLOR)
        logger.info("LEDs set to CONNECTING state")
    
    def set_error(self):
        """Set LEDs to error state (yellow)"""
        self.set_all_strips(ERROR_COLOR)
        logger.info("LEDs set to ERROR state")
    
    def turn_off(self):
        """Turn off all LEDs"""
        self.set_all_strips(OFF)
        logger.info("All LEDs turned off")
    
    def rainbow_cycle(self, wait=0.01):
        """Rainbow cycle animation across all strips"""
        def wheel(pos):
            # Generate rainbow colors across 0-255 positions
            if pos < 85:
                return (pos * 3, 255 - pos * 3, 0)
            elif pos < 170:
                pos -= 85
                return (255 - pos * 3, 0, pos * 3)
            else:
                pos -= 170
                return (0, pos * 3, 255 - pos * 3)
        
        for j in range(255):
            for strip in self.strips:
                for i in range(len(strip)):
                    strip[i] = wheel((i + j) & 255)
                strip.show()
            time.sleep(wait)
    
    def theater_chase(self, color, wait=0.05, iterations=10):
        """Movie theater light style chaser animation."""
        for j in range(iterations):
            for q in range(3):
                for i in range(0, LED_COUNT, 3):
                    if i + q < LED_COUNT:
                        for strip in self.strips:
                            strip[i + q] = color
                
                for strip in self.strips:
                    strip.show()
                    
                time.sleep(wait)
                
                for i in range(0, LED_COUNT, 3):
                    if i + q < LED_COUNT:
                        for strip in self.strips:
                            strip[i + q] = OFF
    
    def color_wipe(self, color, wait=0.05):
        """Fill the dots one after the other with a color."""
        for i in range(LED_COUNT):
            for strip in self.strips:
                strip[i] = color
                strip.show()
            time.sleep(wait)
    
    def pulse(self, color, cycles=3, duration=1.0):
        """Pulse effect on all strips"""
        steps = 50
        for _ in range(cycles):
            # Fade in
            for i in range(steps):
                brightness = i / steps
                for strip in self.strips:
                    strip.brightness = brightness
                    strip.fill(color)
                    strip.show()
                time.sleep(duration / (2 * steps))
            
            # Fade out
            for i in range(steps, 0, -1):
                brightness = i / steps
                for strip in self.strips:
                    strip.brightness = brightness
                    strip.fill(color)
                    strip.show()
                time.sleep(duration / (2 * steps))
        
        # Reset brightness
        for strip in self.strips:
            strip.brightness = LED_BRIGHTNESS

# Singleton instance
led_controller = LEDController()

# Test function
if __name__ == "__main__":
    try:
        logger.info("Testing LED strips...")
        
        # Test basic colors
        logger.info("Testing RED")
        led_controller.set_all_strips(RED)
        time.sleep(1)
        
        logger.info("Testing GREEN")
        led_controller.set_all_strips(GREEN)
        time.sleep(1)
        
        logger.info("Testing BLUE")
        led_controller.set_all_strips(BLUE)
        time.sleep(1)
        
        logger.info("Testing YELLOW")
        led_controller.set_all_strips(YELLOW)
        time.sleep(1)
        
        # Test muted/unmuted states
        logger.info("Testing MUTED state")
        led_controller.set_muted()
        time.sleep(1)
        
        logger.info("Testing UNMUTED state")
        led_controller.set_unmuted()
        time.sleep(1)
        
        # Test rainbow effect
        logger.info("Testing rainbow cycle")
        led_controller.rainbow_cycle()
        
        # Test pulse effect
        logger.info("Testing pulse effect")
        led_controller.pulse(BLUE)
        
        # Turn off
        led_controller.turn_off()
        logger.info("Test complete")
        
    except KeyboardInterrupt:
        led_controller.turn_off()
        logger.info("Test interrupted")
    except Exception as e:
        logger.error(f"Test error: {e}")
        led_controller.set_error()
        time.sleep(2)
        led_controller.turn_off()