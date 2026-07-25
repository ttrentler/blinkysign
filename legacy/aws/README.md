# UNSUPPORTED — KNOWN BROKEN

These scripts are kept for reference only. **They do not work**, and following
them will not produce a working sign. They are not part of the installation
path documented in the top-level README.

If you want remote control, use MQTT instead — see "Remote control" in the main
[README](../../README.md). It works with a local Mosquitto, a free HiveMQ or
EMQX tier, or AWS IoT Core itself, and needs none of the machinery below.

---

## Why this path was retired

### The CloudFormation stack cannot create

`cloudformation.yaml` declares:

```yaml
Outputs:
  IoTEndpoint:
    Value: !GetAtt IoTCertificateCSR.endpoint
```

but the custom-resource Lambda that backs `IoTCertificateCSR` returns only:

```python
response_data = {
    'CSR': keys_cert['certificatePem'],
    'CertificateId': keys_cert['certificateId'],
    'CertificateArn': keys_cert['certificateArn'],
}
```

There is no `endpoint` key, so `!GetAtt` fails and takes the stack with it.
`deploy_aws.py` then indexes `outputs['IoTEndpoint']` unconditionally.

### The device private key is generated and thrown away

The same Lambda writes the key to its own ephemeral filesystem:

```python
with open('/tmp/certs/private.key', 'w') as f:
    f.write(keys_cert['keyPair']['PrivateKey'])
```

`/tmp` there is the Lambda execution environment, not the Pi. The key is
discarded when the sandbox is recycled and is never returned to the caller —
and AWS will not reissue it. Even if the stack completed, the device could
never authenticate.

### The certificate resource is fed the wrong thing

`CertificateSigningRequest: !GetAtt IoTCertificateCSR.CSR` receives a
certificate PEM, not a CSR. `create_keys_and_certificate` has already issued a
certificate by that point.

### The API key written to .env is not the API key

`deploy_aws.py` writes the `ApiKey` stack output, which is `!Ref ApiKey` — the
API key's *ID*, not its value. It is not usable as an `x-api-key` header.

### The API Gateway integration cannot reach IoT

`connect_api_to_iot.py` calls `put_integration` with no `credentials=`
parameter, so API Gateway has no role to assume when calling IoT. Both the
integration URI and the topic-rule SQL also target `$aws/events/...`, which is
AWS's reserved namespace — customer publishes there are rejected. Every failure
in that script is swallowed into a `warning` or a bare `pass`, so it reports
success either way.

### It granted your own account administrative IoT access

`ensure_iot_permissions()` attached `iot:*` on `*` to the calling IAM principal
as both a managed and an inline policy, and nothing ever removed it.
`deploy_aws.py` called it automatically. **If you have ever run these scripts,
see [SECURITY.md](../../SECURITY.md) for how to find and revoke that grant.**

### Cleanup did not clean up

`cleanup_aws.py` deletes resources imperatively instead of deleting the stack,
so it leaves behind the CloudFormation stack itself, the six IoT topic rules,
the `blinkysign-iot-role` IAM role, the admin policy above, the certificate
Lambda and its role, the API key and the usage plan. It also deletes the REST
API out from under the stack that owns it.

### Two parallel implementations

`aws_setup.py` is roughly 700 lines of boto3 that recreates everything
`cloudformation.yaml` declares, including byte-identical copies of the helper
functions in `deploy_aws.py`. The old `setup.sh` pointed users at this one while
the README documented the other.

---

## What was changed before archiving

Two edits only — no attempt at repair:

1. **`update_control_panel_html()` was deleted** from `deploy_aws.py` and
   `aws_setup.py`. It rewrote the git-tracked `control_panel.html` in place,
   substituting a live API key into a file that was staged for commit, with no
   `.gitignore` in the repository to catch it. The panel now reads its settings
   from `/api/config` at runtime.

2. **Three `html.escape(...)` logging calls were removed.** Their `import html`
   existed only as a comment, so every call to `update_env_file` raised
   `NameError` — caught by a bare `except`, which turned it into a spurious
   "Error updating .env file" on every deploy.

## If you want to fix this properly

Roughly, in order: have the Lambda store the private key in Secrets Manager and
return a handle rather than writing it to `/tmp`; add a real `IoTEndpoint`
output via `iot:DescribeEndpoint`; use `GetApiKey(includeValue=true)` instead of
`!Ref`; move the topic rules and integration off the `$aws/` namespace and add
`credentials=`; delete the self-granting IAM code outright; and replace
`cleanup_aws.py` with `delete-stack` plus a waiter.
