# Stream Deck Button Integration

These HTML files let you control BlinkySign from an Elgato Stream Deck.

## Setup Instructions

1. Make sure your BlinkySign is running and accessible on your network
2. Install the Stream Deck software on your computer
3. Add a "System: Open" action to your Stream Deck
4. Configure the URL to point to one of these HTML files

## Available Buttons

- **mute.html**: Sets the BlinkySign to its muted colour
- **unmute.html**: Sets the BlinkySign to its unmuted colour
- **toggle.html**: Toggles between muted and unmuted
- **rainbow.html**: Triggers the rainbow effect
- **aws-mute.html**: See the note below — this one no longer applies

## Set the hostname before using these

These files point at `http://raspberrypi.local:5000`, the Pi's default
hostname. BlinkySign now *also* advertises itself over mDNS as
`http://blinkysign.local:5000`.

Both may work, or only one, depending on your setup:

- `raspberrypi.local` works if you never changed the Pi's hostname.
- `blinkysign.local` works once BlinkySign is running, unless another device on
  the network already claimed the name — Avahi silently renames the second one
  to `blinkysign-2.local`. The service log records the name it actually
  registered.

If neither resolves — mDNS is unreliable on some networks, and on much of
Android — use the Pi's IP address. The installer prints it when it finishes.

Edit the URL in each file to whichever of the three works for you. Nothing
rewrites these files automatically.

## If you set an API token

If `BLINKYSIGN_API_TOKEN` is set on the sign, add the header to each `fetch`
call in these files:

```js
headers: {
    'Content-Type': 'application/json',
    'x-api-key': 'your-token'
}
```

## About aws-mute.html

This targeted the AWS API Gateway deployment, which has been retired — it did
not work, and the reasons are in [../legacy/aws/README.md](../legacy/aws/README.md).
The file is kept only as a shape to copy for any HTTPS endpoint you put in
front of the sign. For remote control, use the MQTT support described in the
main [README](../README.md).

## Troubleshooting

1. Confirm the sign responds: `curl http://blinkysign.local:5000/health`
2. If that returns `"status": "degraded"`, the sign is running but its LEDs are
   not available — usually SPI not enabled, or a reboot still pending
3. Check that the hostname or IP in the HTML file is reachable from your computer
4. If you set an API token, make sure the header is present
