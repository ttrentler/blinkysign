#!/bin/bash
# Setup script for BlinkySign

echo "Setting up BlinkySign..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create certificates directory
echo "Creating certificates directory..."
mkdir -p certs

# Download Amazon root CA certificate
echo "Downloading Amazon root CA certificate..."
curl -o certs/AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please edit .env file with your AWS credentials and configuration"
fi

echo "Setup complete!"
echo "Next steps:"
echo "1. Edit .env file with your AWS credentials and configuration"
echo "2. Run 'python aws_setup.py' to set up AWS resources"
echo "3. Run 'python app.py' to start the local server"
echo "4. Run 'python iot_client.py' to connect to AWS IoT Core"