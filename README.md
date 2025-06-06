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
- Optional: Raspberry Pi Breakout board - https://www.amazon.com/dp/B084C69VSQ
- Look at this site for an example of wiring - https://core-electronics.com.au/guides/fully-addressable-rgb-raspberry-pi/


## Software Requirements

- Python 3.10+
- AWS account with access to IoT Core and API Gateway (for cloud connectivity)
- Dependencies listed in requirements.txt
- System package: `lgpio` (install with `sudo apt-get install -y python3-lgpio`)

## Project Files

The project consists of the following key files:

- **app.py**: Flask web server that provides the HTTP API endpoints for controlling the sign
- **iot_client.py**: Connects to AWS IoT Core and subscribes to MQTT topics to receive commands
- **led_controller.py**: Controls the WS2812B LED strips via SPI interface
- **aws_setup.py**: Sets up all required AWS resources (IoT Thing, API Gateway, etc.)
- **connect_api_to_iot.py**: Connects API Gateway to IoT Core for remote control
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
   source venv/bin/activate
   python app.py
   ```
   
   This will start the local HTTP server on port 5000.

4. **Access the control panel**:
   ```bash
   source venv/bin/activate
   python -m http.server 8000
   ```
   
   Then open a browser on any device on your local network and navigate to:
   ```
   http://192.168.1.X:8000/control_panel.html
   ```
   
   Make sure to select "Local" in the API endpoint dropdown.

5. **For physical button control** (optional):
   ```bash
   source venv/bin/activate
   python physical_button.py
   ```

6. **For remote button control** from another device:
   Edit the `.env` file on the remote device to point to your Raspberry Pi:
   ```
   API_ENDPOINT=http://192.168.1.X:5000
   ```
   
   Then run:
   ```bash
   source venv/bin/activate
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

4. **Deploy AWS resources using CloudFormation**:
   ```bash
   python deploy_aws.py
   ```
   
   This will:
   - Create a CloudFormation stack with all necessary AWS resources
   - Set up IoT Core Thing, certificates, and policies
   - Create API Gateway with all required endpoints and CORS support
   - Configure API key authentication
   - Update your `.env` file with all endpoints and credentials
   - Update the control panel HTML with the new endpoints

5. **Connect API Gateway to IoT Core**:
   ```bash
   python connect_api_to_iot.py
   ```
   
   This will:
   - Create necessary IAM roles and policies
   - Set up IoT Core topic rules
   - Replace mock integrations with real IoT Core integrations
   - Deploy the updated API Gateway configuration

6. **Start the local server**:
   ```bash
   source venv/bin/activate
   python app.py
   ```

7. **Connect to AWS IoT Core**:
   ```bash
   source venv/bin/activate
   python iot_client.py
   ```

8. **Access the control panel**:
   ```bash
   source venv/bin/activate
   python -m http.server 8000
   ```
   
   Then open a browser and navigate to:
   ```
   http://localhost:8000/control_panel.html
   ```
   
   You can switch between local and AWS endpoints in the control panel.
   
9. **Verify the connection**:
   After running the script, test the connection by:
   - Opening the control panel in your browser
   - Selecting the AWS endpoint
   - Clicking any control button (e.g., Toggle Mute)
   - Checking that your Raspberry Pi's LEDs respond to the command

   If the connection doesn't work:
   - Make sure your `.env` file has the correct `API_ID` value (extracted from `API_ENDPOINT`)
   - Ensure your IoT client is running on the Raspberry Pi
   - Check AWS CloudWatch logs for any errors in the API Gateway or IoT Core

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
  - IoT Thing with certificates and policies
  - MQTT topics for device communication
  - IoT Core endpoint for secure connectivity

- **API Gateway**: For HTTP API endpoints
  - REST API with API key authentication
  - CORS support for web clients
  - Mock integrations for initial testing (replaced with real IoT Core integrations during deployment)
  - Endpoints for status, toggle, effects, and health check

The deployment process involves two steps:
1. Initial setup with mock integrations for testing
2. Connecting to IoT Core with real integrations

All AWS resources are managed through CloudFormation for consistent and repeatable deployments. The CloudFormation template (`cloudformation.yaml`) defines:

1. IoT Core resources:
   - IoT Thing
   - Thing policy
   - Certificates and attachments

2. API Gateway resources:
   - REST API with regional endpoint
   - API key and usage plan
   - Resources and methods for all endpoints
   - CORS configuration
   - Initial mock integrations (replaced with real IoT Core integrations)

3. Lambda function for certificate management:
   - Creates and manages IoT certificates
   - Saves certificates to local files
   - Updates environment configuration

To deploy or update the AWS infrastructure:
```bash
python deploy_aws.py
```

This script will create or update the CloudFormation stack and configure your local environment.

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

## Auto-Start on Boot

To configure BlinkySign to automatically start on boot:

### Local-Only Installation

1. **Create a startup script**:

```bash
sudo nano /path/to/blinkysign/startup.sh
```

Add this content:
```bash
#!/bin/bash
# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"
source venv/bin/activate
python app.py &
python -m http.server 8000 &
```

Make it executable:
```bash
chmod +x /path/to/blinkysign/startup.sh
```

2. **Create a systemd service file**:

```bash
sudo nano /etc/systemd/system/blinkysign.service
```

Add this content:
```
[Unit]
Description=BlinkySign Service
After=network.target

[Service]
ExecStart=/path/to/blinkysign/startup.sh
User=your-username
WorkingDirectory=/path/to/blinkysign
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. **Enable and start the service**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable blinkysign.service
sudo systemctl start blinkysign.service
```

### AWS + Local Installation

If you've chosen the AWS + Local installation option, you'll also want to start the IoT client on boot:

1. **Create an IoT client startup script**:

```bash
sudo nano /path/to/blinkysign/iot_startup.sh
```

Add this content:
```bash
#!/bin/bash
# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"
source venv/bin/activate
python iot_client.py
```

Make it executable:
```bash
chmod +x /path/to/blinkysign/iot_startup.sh
```

2. **Create a systemd service file for the IoT client**:

```bash
sudo nano /etc/systemd/system/blinkysign-iot.service
```

Add this content:
```
[Unit]
Description=BlinkySign IoT Client Service
After=network.target
Wants=blinkysign.service

[Service]
ExecStart=/path/to/blinkysign/iot_startup.sh
User=your-username
WorkingDirectory=/path/to/blinkysign
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. **Enable and start the IoT service**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable blinkysign-iot.service
sudo systemctl start blinkysign-iot.service
```

4. **Check the status of both services**:

```bash
sudo systemctl status blinkysign.service
sudo systemctl status blinkysign-iot.service
```

## Installation Path

When following the instructions in this README, replace `/path/to/blinkysign` with your actual installation path. For example:
- If you installed in your home directory: `/home/username/blinkysign`
- If you installed on your desktop: `/home/username/Desktop/blinkysign`

Also replace `your-username` with your actual system username.

Make sure to use the correct path in all configuration files, especially in the systemd service files.

After rebooting, your BlinkySign will automatically start the Flask app, HTTP server, and IoT client (if enabled). You can access the control panel by navigating to `http://[raspberry-pi-ip]:8000/control_panel.html` from any device on your network.

## Cleaning Up AWS Resources

When you're done with the project or want to remove all AWS resources created by it, you can delete the CloudFormation stack:

```bash
aws cloudformation delete-stack --stack-name blinkysign-stack
```

This will automatically delete all AWS resources created by the stack, including:
- IoT Thing, certificates, and policies
- API Gateway, stages, and API keys
- Lambda functions and IAM roles
- Any other resources created by the CloudFormation template

The stack deletion will be clean and complete, ensuring no orphaned resources are left behind.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
