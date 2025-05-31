# 🔒 Security Policy

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

