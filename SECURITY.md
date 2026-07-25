# 🔒 Security Policy

## ⚠️ If you have ever run `deploy_aws.py` or `connect_api_to_iot.py`, read this first

`connect_api_to_iot.py` contains a function, `ensure_iot_permissions()`, that grants
**your own IAM principal `iot:*` on `*`** — full administrative access to IoT Core across
your entire account. It does this twice: once as a customer-managed policy, and again as
an inline policy "for immediate effect." `deploy_aws.py` calls it automatically as part of
a normal deployment. Nothing in this repository ever revokes it.

If you have run either script, that grant is still live in your account. Check and remove it:

```bash
# Who am I, and is this a user or an assumed role?
aws sts get-caller-identity

# For an IAM user (substitute your username):
aws iam list-attached-user-policies --user-name YOUR_USERNAME
aws iam list-user-policies --user-name YOUR_USERNAME

aws iam detach-user-policy --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/blinkysign-iot-admin-policy
aws iam delete-user-policy --user-name YOUR_USERNAME \
  --policy-name blinkysign-iot-admin-policy-inline
aws iam delete-policy \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/blinkysign-iot-admin-policy
```

For an assumed role, use `list-attached-role-policies` / `detach-role-policy` /
`delete-role-policy` with `--role-name` instead.

Also check for the deployment role and its inline policy, which `cleanup_aws.py` does not
remove either:

```bash
aws iam list-role-policies --role-name blinkysign-iot-role
aws iam delete-role-policy --role-name blinkysign-iot-role \
  --policy-name blinkysign-iot-publish-policy
aws iam delete-role --role-name blinkysign-iot-role
```

The AWS deployment path is unsupported and known broken — see `legacy/aws/README.md`.
Remote control is now provided over standard MQTT and requires no AWS account at all.

---

## Be Very Careful When Setting Up AWS Connectivity

The current version of `blinkysign` requires AWS credentials to deploy the project using local scripts. This gives deployment scripts access to your AWS account, so it's critical to follow safe handling practices.

---

### ⚠️ Important Security Guidelines

- **NEVER commit your credentials** (`.env` file, AWS config files, etc.) to version control.  
  Ensure your `.env` file is included in `.gitignore`.

- **Local AWS credentials are required** only during the initial deployment process.

- After a successful deployment:
  - **Remove** any credentials from the `.env` file.
  - **Delete** access tokens or keys from your AWS account to reduce attack surface.

- **Use least-privilege access.**  
  Generate access keys with only the permissions necessary for deployment (e.g., Lambda, API Gateway).

- **Rotate keys regularly.**  
  If credentials are exposed or compromised, rotate them immediately.

- **Audit your AWS usage.**  
  Use AWS IAM logs and CloudTrail to monitor any unauthorized or unexpected activity.

---

## 🔐 Best Practices

- Use tools like [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) for managing secrets securely.
- Avoid long-lived access keys; prefer short-term credentials or IAM roles when possible.
- Consider setting up a secure CI/CD pipeline to handle deployments without needing to store local credentials.

---

## 🆘 Need Help?

If you have any concerns or questions about the security of your deployment, please:

- Open an issue in this repository
- Refer to [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- Contact the repository maintainer

Stay safe and secure while using `blinkysign`! 🚦

