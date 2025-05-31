# Stream Deck Button Integration

These HTML files allow you to control BlinkySign using an Elgato Stream Deck.

## Setup Instructions

1. Make sure your BlinkySign is running and accessible on your network
2. Install the Stream Deck software on your computer
3. Add a "System: Open" action to your Stream Deck
4. Configure the URL to point to one of these HTML files

## Available Buttons

- **mute.html**: Sets the BlinkySign to muted state (red)
- **unmute.html**: Sets the BlinkySign to unmuted state (green)
- **toggle.html**: Toggles between muted and unmuted states
- **rainbow.html**: Triggers the rainbow effect
- **aws-mute.html**: Template for AWS API Gateway integration (requires customization)

## Local vs AWS

- The standard HTML files are configured for local network use with `http://raspberrypi.local:5000`
- For AWS API Gateway, use the aws-*.html templates and customize with your API Gateway URL and API key

## Customization

Edit the HTML files to:
1. Change the hostname if your Raspberry Pi has a different hostname
2. Add your AWS API Gateway URL and API key for cloud control
3. Adjust the auto-close timeout (default is 1 second)

## Troubleshooting

If the buttons don't work:
1. Make sure your BlinkySign is running and accessible
2. Check that the hostname or IP address in the HTML files is correct
3. Verify that your network allows the connection
4. For AWS endpoints, ensure your API key is valid