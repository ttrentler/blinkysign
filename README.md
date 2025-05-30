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
- AWS account with access to IoT Core and API Gateway (for cloud connectivity)
- Dependencies listed in requirements.txt

## Project Files

The project consists of the following key files:

- **app.py**: Flask web server that provides the HTTP API endpoints for controlling the sign
- **iot_client.py**: Connects to AWS IoT Core and subscribes to MQTT topics to receive commands
- **led_controller.py**: Controls the WS2812B LED strips via SPI interface
- **aws_setup.py**: Sets up all required AWS resources (IoT Thing, API Gateway, etc.)
- **cleanup_aws.py**: Removes all AWS resources created by the project
- **button_client.py**: Simple client for sending commands to the sign from a remote device
- **physical_button.py**: Controls the sign using a physical button connected to GPIO
- **control_panel.html**: Web-based control panel for the sign
- **web_button.html**: Simple web page with a button to toggle the sign
- **setup.sh**: Installation script for setting up the project
- **.env.example**: Example environment variables file
- **requirements.txt**: Python dependencies

## Installation Options

You can install BlinkySign in two ways:
1. **Local-Only Install**: For use on a local network without AWS connectivity
2. **AWS + Local Install**: Full installation with cloud connectivity

### Local-Only Install

If you want to run BlinkySign on a local network without AWS connectivity:

1. **Clone the repository and install dependencies**:
   ```bash
   git clone https://github.com/ttrentler/blinkysign.git
   cd blinkysign
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create a minimal `.env` file**:
   ```bash
   cp .env.example .env
   ```
   
   Edit the `.env` file to include only the local settings:
   ```
   # Flask server port
   PORT=5000
   
   # LED Configuration
   LED_COUNT=30
   LED_BRIGHTNESS=0.5
   
   # Button Configuration
   BUTTON_PIN=17
   
   # API endpoint for button client (use your Raspberry Pi's local IP)
   API_ENDPOINT=http://192.168.1.X:5000
   ```
   
   Replace `192.168.1.X` with your Raspberry Pi's actual IP address.

3. **Run the Flask server**:
   ```bash
   python app.py
   ```
   
   This will start the local HTTP server on port 5000.

4. **Access the control panel**:
   ```bash
   python -m http.server 8000
   ```
   
   Then open a browser on any device on your local network and navigate to:
   ```
   http://192.168.1.X:8000/control_panel.html
   ```
   
   Make sure to select "Local" in the API endpoint dropdown.

5. **For physical button control** (optional):
   ```bash
   python physical_button.py
   ```

6. **For remote button control** from another device:
   Edit the `.env` file on the remote device to point to your Raspberry Pi:
   ```
   API_ENDPOINT=http://192.168.1.X:5000
   ```
   
   Then run:
   ```bash
   python button_client.py
   ```

### AWS + Local Install

For full installation with cloud connectivity:

1. **Clone the repository and install dependencies**:
   ```bash
   git clone https://github.com/ttrentler/blinkysign.git
   cd blinkysign
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure AWS CLI** (if not already done):
   ```bash
   aws configure
   ```
   
   Enter your AWS Access Key ID, Secret Access Key, default region, and output format.

3. **Create a `.env` file**:
   ```bash
   cp .env.example .env
   ```
   
   Edit the `.env` file with your LED configuration:
   ```
   # Flask server port
   PORT=5000
   
   # LED Configuration
   LED_COUNT=30
   LED_BRIGHTNESS=0.5
   
   # Button Configuration
   BUTTON_PIN=17
   
   # AWS Configuration
   AWS_REGION=us-east-1
   ```

4. **Set up AWS resources**:
   ```bash
   python aws_setup.py
   ```
   
   This will create all necessary AWS resources and update your `.env` file with the endpoints.

5. **Start the local server**:
   ```bash
   python app.py
   ```

6. **Connect to AWS IoT Core**:
   ```bash
   python iot_client.py
   ```

7. **Access the control panel**:
   ```bash
   python -m http.server 8000
   ```
   
   Then open a browser and navigate to:
   ```
   http://localhost:8000/control_panel.html
   ```
   
   You can switch between local and AWS endpoints in the control panel.

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