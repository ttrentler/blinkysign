# BlinkySign

A project for creating an internet-connected 3D printed sign controlled via AWS.

## Description

BlinkySign is a Raspberry Pi-powered LED sign that can be remotely controlled to indicate mute/unmute status. It uses AWS IoT Core for cloud connectivity and can be controlled via HTTP requests from a remote button.

## Features

- Remote control via HTTP requests
- AWS IoT Core integration for reliable connectivity
- Simple REST API for status control
- LED indicator for mute/unmute status
- 3D printable enclosure

## Hardware Requirements

- Raspberry Pi (Nano or other model)
- LEDs for status indication
- Resistors for LEDs (typically 220-330 ohm)
- Jumper wires
- 3D printed enclosure (see 3dprints folder)
- Power supply for Raspberry Pi

## Software Requirements

- Python 3.6+
- AWS account with access to IoT Core and API Gateway
- Dependencies listed in requirements.txt

## Getting Started

1. Clone this repository to your Raspberry Pi
2. Run the setup script:
   ```
   chmod +x setup.sh
   ./setup.sh
   ```
3. Edit the `.env` file with your AWS credentials and configuration
4. Set up AWS resources:
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

## API Endpoints

- `GET /status` - Get current mute status
- `PUT /toggle` - Toggle mute status
- `PUT /set` - Set mute status explicitly (requires JSON body with `muted` field)
- `GET /health` - Health check endpoint

## Remote Button Setup

The remote button can be any device capable of sending HTTP requests. You can use:

1. Another Raspberry Pi with a physical button
2. A smartphone app with a virtual button
3. A web interface with a button

To use the provided button client:

1. Edit the `.env` file with the API endpoint
2. Run the button client:
   ```
   python button_client.py
   ```

## AWS Architecture

The project uses the following AWS services:

- **IoT Core**: For reliable MQTT communication
- **API Gateway**: For HTTP API endpoints
- **Lambda** (optional): For additional processing logic
- **DynamoDB** (optional): For storing state history

## Circuit Diagram

Connect the LED to the Raspberry Pi as follows:

```
Raspberry Pi GPIO Pin (default: GPIO18) --> 220 ohm resistor --> LED anode (+) --> LED cathode (-) --> GND
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.