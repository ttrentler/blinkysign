# BlinkySign

A project for creating an internet-connected 3D printed sign controlled via AWS.

## Description

BlinkySign is a Raspberry Pi-powered LED sign that uses WS2812B LED strips to indicate mute/unmute status. It can be remotely controlled via HTTP requests from a remote button and integrates with AWS IoT Core for cloud connectivity.

## Features

- Control up to 4 WS2812B LED strips from a single Raspberry Pi
- Remote control via HTTP requests
- AWS IoT Core integration for reliable connectivity
- Simple REST API for status control
- Multiple lighting effects (solid colors, rainbow, pulse)
- 3D printable enclosure

## Hardware Requirements

- Raspberry Pi (Nano or other model)
- Up to 4 WS2812B LED strips
- Jumper wires
- 5V power supply (adequate for your LED strips)
- 3D printed enclosure (see 3dprints folder)
- Optional: Physical button for local control

## Software Requirements

- Python 3.6+
- AWS account with access to IoT Core and API Gateway
- Dependencies listed in requirements.txt

## AWS Setup

The project uses AWS IoT Core and API Gateway. You can deploy the required AWS resources using the CloudFormation template:

```bash
# Deploy the CloudFormation stack
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name blinkysign \
  --capabilities CAPABILITY_IAM

# Get the outputs from the stack
aws cloudformation describe-stacks \
  --stack-name blinkysign \
  --query 'Stacks[0].Outputs'
```

After deployment, you'll need to save the certificate and private key to the `certs/` directory:

```bash
mkdir -p certs
aws cloudformation describe-stacks \
  --stack-name blinkysign \
  --query 'Stacks[0].Outputs[?OutputKey==`CertificatePem`].OutputValue' \
  --output text > certs/certificate.pem

aws cloudformation describe-stacks \
  --stack-name blinkysign \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateKey`].OutputValue' \
  --output text > certs/private.key

aws cloudformation describe-stacks \
  --stack-name blinkysign \
  --query 'Stacks[0].Outputs[?OutputKey==`IoTEndpoint`].OutputValue' \
  --output text > certs/endpoint.txt
```

## Getting Started

1. Clone this repository to your Raspberry Pi
2. Run the setup script:
   ```
   chmod +x setup.sh
   ./setup.sh
   ```
3. Edit the `.env` file with your AWS credentials and LED configuration
4. Deploy AWS resources using CloudFormation (see AWS Setup section)
5. Start the local server:
   ```
   python app.py
   ```
6. Connect to AWS IoT Core:
   ```
   python iot_client.py
   ```

## LED Strip Connection

WS2812B LED strips require three connections:
- Power (5V)
- Ground (GND)
- Data (GPIO pin)

Default GPIO pins:
- Strip 1: GPIO 18
- Strip 2: GPIO 19
- Strip 3: GPIO 21
- Strip 4: GPIO 13

You can configure these pins in the `.env` file.

**Important**: WS2812B strips may require a separate power supply if you're using many LEDs, as they can draw significant current. The Raspberry Pi GPIO pins cannot provide enough power for long strips.

## API Endpoints

- `GET /status` - Get current mute status
- `PUT /toggle` - Toggle mute status
- `PUT /set` - Set mute status explicitly (requires JSON body with `muted` field)
- `PUT /effects/rainbow` - Trigger rainbow effect
- `PUT /effects/pulse` - Trigger pulse effect (optional JSON body with `color` and `cycles` fields)
- `PUT /off` - Turn off all LEDs
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

## Testing the LED Strips

You can test your LED strips with:

```
python led_controller.py
```

This will run through various colors and effects to verify your LED strips are working correctly.

## License

This project is licensed under the MIT License - see the LICENSE file for details.