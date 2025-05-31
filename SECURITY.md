# Security Policy

Be Very Careful When Setting Up AWS Connectivity
The current version of blinkysign requires AWS credentials to deploy the project using local scripts. As such, we urge all users to follow strict security practices when working with AWS credentials during setup and deployment.

⚠️ Important Warnings:

Never commit credentials to source control.
Double-check that your .env file and any AWS credential files are listed in your .gitignore.
Local AWS credentials are required for deployment scripts.
These credentials are used to configure and deploy infrastructure. They grant significant permissions and must be protected accordingly.
Manually clean up after deployment:
Immediately remove any AWS access keys or tokens from your .env file once the deployment has succeeded.
Delete any temporary AWS access tokens or keys from your AWS account that were used in the process. Leaving unused credentials active exposes your account to unnecessary risk.
Use the principle of least privilege.
If you must generate credentials for deployment, restrict permissions only to the specific services and actions required for the setup.


## Supported Versions

TBD

## Reporting a Vulnerability

Report a vulnarabil;ity here!!

