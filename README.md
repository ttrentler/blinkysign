# BlinkySign

A project for creating an internet-connected 3D printed sign controlled via Raspberry Pi.

## Description

BlinkySign is a Raspberry Pi-powered LED sign that uses WS2812B LED strips to indicate mute/unmute status. It can be remotely controlled via HTTP requests from a remote button and integrates with AWS IoT Core for cloud connectivity.

## Features

- Control WS2812B LED strips from a Raspberry Pi using SPI interface
- Remote control via HTTP requests
- AWS IoT Core integration for reliable connectivity
- Simple REST API for status control
- Multiple lighting effects (solid colors, rainbow, pulse)
- 3D printable enclosure
- API key authentication for secure remote access
- Stream Deck integration support

## Hardware Requirements

- Raspberry Pi (Pi 5 recommended for SPI interface)
- WS2812B LED strips
- Jumper wires
- 5V power supply (adequate for your LED strips)
- 3D printed enclosure (see 3dprints folder)
- Optional: Physical button for local control
- Optional: Elgato Stream Deck for remote control

## Software Requirements

- Python 3.10+
- AWS account with access to IoT Core and API Gateway
- Dependencies listed in requirements.txt

## AWS Setup

The project uses AWS IoT Core and API Gateway. You can set up the required AWS resources using the provided script:

```bash
# Run the AWS setup script
python aws_setup.py
```

This script will:
1. Create an AWS IoT Thing for your BlinkySign
2. Create and attach the necessary policies
3. Generate certificates and save them to the `certs/` directory
4. Create an API Gateway with API key authentication for remote control
5. Create an API key and save it to `certs/api_key.txt`
6. Update your `.env` file with the endpoints
7. Update the control panel HTML with the new API endpoint

## Getting Started

1. Clone this repository to your Raspberry Pi
2. Run the setup script:
   ```
   chmod +x setup.sh
   ./setup.sh
   ```
3. Edit the `.env` file with your AWS credentials and LED configuration
4. Set up AWS resources using the AWS setup script:
   ```
   python aws_setup.py
   ```
5. Start the local server:
   ```
   python app.py
   ```
6. Connect to AWS IoT Core:
   ```
   python iot_client.py
   ```

## LED Strip Connection

WS2812B LED strips with SPI interface require these connections:
- Power (5V)
- Ground (GND)
- Data (MOSI pin)
- Clock (SCK pin)

The default configuration uses the Raspberry Pi's SPI interface which is more compatible with Pi 5.

**Important**: WS2812B strips may require a separate power supply if you're using many LEDs, as they can draw significant current. The Raspberry Pi GPIO pins cannot provide enough power for long strips.

## API Endpoints

All API endpoints require an API key when accessed through the AWS API Gateway:

- `GET /status` - Get current mute status
- `PUT /toggle` - Toggle mute status
- `PUT /set` - Set mute status explicitly (requires JSON body with `muted` field)
- `PUT /effects/rainbow` - Trigger rainbow effect
- `PUT /effects/pulse` - Trigger pulse effect (optional JSON body with `color` and `cycles` fields)
- `PUT /off` - Turn off all LEDs
- `GET /health` - Health check endpoint

## Web Control Panel

A web-based control panel is included in the project:

```bash
# Run a simple HTTP server
python -m http.server 8000
```

Then open your browser to:
```
http://localhost:8000/control_panel.html
```

The control panel allows you to:
- Switch between local and AWS API endpoints
- Enter your API key for AWS authentication
- Control all BlinkySign functions through a user-friendly interface

## Stream Deck Integration

You can control your BlinkySign using an Elgato Stream Deck:

1. Install the Stream Deck software on your computer
2. Install the "System: Website" plugin
3. Configure buttons with the following settings:

   **Toggle Mute Button:**
   - URL: `https://[your-api-gateway-url]/toggle`
   - Method: PUT
   - Headers: `x-api-key: [your-api-key]`

   **Set Muted (Red) Button:**
   - URL: `https://[your-api-gateway-url]/set`
   - Method: PUT
   - Body: `{"muted": true}`
   - Content Type: application/json
   - Headers: `x-api-key: [your-api-key]`

   **Rainbow Effect Button:**
   - URL: `https://[your-api-gateway-url]/effects/rainbow`
   - Method: PUT
   - Headers: `x-api-key: [your-api-key]`

Your API Gateway URL and API key are saved in:
- API URL: `.env` file under `API_ENDPOINT`
- API Key: `certs/api_key.txt`

## Remote Button Setup

The remote button can be any device capable of sending HTTP requests. You can use:

1. Another Raspberry Pi with a physical button
2. A smartphone app with a virtual button
3. A web interface with a button
4. Elgato Stream Deck (see Stream Deck Integration section)

To use the provided button client:

1. Edit the `.env` file with the API endpoint
2. Run the button client:
   ```
   python button_client.py
   ```

## AWS Architecture

The project uses the following AWS services:

- **IoT Core**: For reliable MQTT communication
- **API Gateway**: For HTTP API endpoints with API key authentication
- **Lambda** (optional): For additional processing logic
- **DynamoDB** (optional): For storing state history

## Testing the LED Strips

You can test your LED strips with:

```
python led_controller.py
```

This will run through various colors and effects to verify your LED strips are working correctly.

You can also test the SPI interface specifically with:

```
python boardtest.py
```

## Cleaning Up AWS Resources

When you're done with the project or want to remove all AWS resources created by it, you can use the cleanup script:

```bash
python cleanup_aws.py
```

This script will:
1. Delete the IoT Thing
2. Detach and delete all policies
3. Detach, deactivate, and delete all certificates
4. Delete the API Gateway and API keys
5. Find and remove all resources tagged with `project:blinkysign`

## License

This project is licensed under the MIT License - see the LICENSE file for details.