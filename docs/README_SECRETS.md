# MountainAsh Settings - Secrets Module

A robust, extensible secrets management module for secure credential handling across multiple cloud providers and local storage.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Provider Support](#provider-support)
  - [AWS Secrets Manager](#aws-secrets-manager)
  - [Azure Key Vault](#azure-key-vault)
  - [Google Cloud Secret Manager](#google-cloud-secret-manager)
  - [HashiCorp Vault](#hashicorp-vault)
  - [Local Secrets](#local-secrets)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Security Features](#security-features)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Secrets Module provides a unified interface for managing secrets across different cloud providers and local storage solutions. It offers secure secret storage, retrieval, and management with features like caching, encryption, and version control.

### Key Benefits
- Unified interface across multiple providers
- Built-in security features
- Extensive configuration options
- Robust error handling
- Comprehensive testing support

## Features

- **Multi-Provider Support**: 
  - AWS Secrets Manager
  - Azure Key Vault
  - Google Cloud Secret Manager
  - HashiCorp Vault
  - Local storage options

- **Security Features**:
  - Automatic encryption
  - Secure secret handling
  - Cache management
  - Version control
  - Access control

- **Core Functionality**:
  - Secret retrieval
  - Secret listing
  - Metadata management
  - Version tracking
  - Namespace support

## Installation

```bash
pip install mountainash-settings[secrets]
```

For provider-specific dependencies:

```bash
# AWS Support
pip install mountainash-settings[aws]

# Azure Support
pip install mountainash-settings[azure]

# GCP Support
pip install mountainash-settings[gcp]

# HashiCorp Support
pip install mountainash-settings[vault]

# All Providers
pip install mountainash-settings[all]
```

## Quick Start

```python
from mountainash_settings.auth.secrets import create_secrets_settings
from mountainash_settings.auth.secrets.constants import CONST_SECRET_PROVIDER_TYPE

# Create AWS Secrets Manager settings
aws_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.AWS_SECRETS,
    settings_namespace="aws_prod",
    REGION="us-west-2",
    ACCESS_KEY_ID="your-access-key",
    SECRET_ACCESS_KEY="your-secret-key"
)

# Get a secret
secret_value = aws_secrets.get_secret("database-password")
```

## Provider Support

### AWS Secrets Manager

```python
aws_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.AWS_SECRETS,
    settings_namespace="aws_prod",
    REGION="us-west-2",
    ACCESS_KEY_ID="access-key",
    SECRET_ACCESS_KEY="secret-key",
    # Optional settings
    SESSION_TOKEN="session-token",
    ROLE_ARN="role-arn",
    MAX_RETRIES=3
)
```

Features:
- IAM role support
- KMS integration
- Regional endpoints
- Version stages

### Azure Key Vault

```python
azure_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.AZURE_KEYVAULT,
    settings_namespace="azure_prod",
    VAULT_NAME="your-vault",
    TENANT_ID="tenant-id",
    CLIENT_ID="client-id",
    CLIENT_SECRET="client-secret"
)
```

Features:
- Managed Identity support
- Certificate-based auth
- Soft delete
- Tags support

### Google Cloud Secret Manager

```python
gcp_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.GCP_SECRETS,
    settings_namespace="gcp_prod",
    PROJECT_ID="your-project",
    SERVICE_ACCOUNT_INFO={
        "type": "service_account",
        # ... other service account details
    }
)
```

Features:
- Project isolation
- Service account support
- Labels support
- Customer managed encryption

### HashiCorp Vault

```python
vault_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.HASHICORP,
    settings_namespace="vault_prod",
    VAULT_HOST="vault.example.com",
    VAULT_PORT=8200,
    VAULT_TOKEN="your-token",
    KV_VERSION=2
)
```

Features:
- KV v1 and v2 support
- Multiple mount points
- Certificate auth
- Namespace isolation

### Local Secrets

```python
local_secrets = create_secrets_settings(
    provider_type=CONST_SECRET_PROVIDER_TYPE.LOCAL,
    settings_namespace="local_dev",
    STORAGE_TYPE="file",
    STORAGE_PATH="/path/to/secrets.json",
    ENCODING_TYPE="fernet"
)
```

Features:
- File-based storage
- System keyring support
- Environment variables
- Local encryption

## Configuration

### Common Settings

```python
settings = create_secrets_settings(
    provider_type="provider_type",
    settings_namespace="namespace",
    
    # Connection Settings
    TIMEOUT=30,
    MAX_RETRIES=3,
    RETRY_DELAY=1,
    
    # Cache Settings
    ENABLE_CACHE=True,
    CACHE_TTL=300,
    
    # Security Settings
    ENCRYPTION_TYPE="none",
    ENCRYPTION_KEY="your-key",
    
    # Version Settings
    VERSION_HANDLING="latest"
)
```

### Environment Variables

```bash
export MA_AWS_ACCESS_KEY_ID="your-access-key"
export MA_AWS_SECRET_ACCESS_KEY="your-secret-key"
export MA_AWS_REGION="us-west-2"
```

### Configuration File

```json
{
  "PROVIDER_TYPE": "aws_secrets",
  "REGION": "us-west-2",
  "ACCESS_KEY_ID": "your-access-key",
  "SECRET_ACCESS_KEY": "your-secret-key",
  "MAX_RETRIES": 3
}
```

## Usage Examples

### Basic Operations

```python
# Get a secret
secret = settings.get_secret("my-secret")
value = secret.get_secret_value()

# List secrets
secrets = settings.list_secrets()
filtered = settings.list_secrets(prefix="dev/")

# Get metadata
metadata = settings.get_secret_metadata("my-secret")

# Get versions
versions = settings.get_secret_versions("my-secret")
```

### Error Handling

```python
from mountainash_settings.auth.secrets.exceptions import (
    SecretNotFoundError,
    SecretAccessError
)

try:
    secret = settings.get_secret("missing-secret")
except SecretNotFoundError:
    print("Secret not found")
except SecretAccessError as e:
    print(f"Access error: {e}")
```

### Caching

```python
# Configure caching
settings.ENABLE_CACHE = True
settings.CACHE_TTL = 300  # 5 minutes

# Get cached secret
secret = settings.get_secret("my-secret")  # First call fetches
cached = settings.get_secret("my-secret")  # Second call uses cache
```

### Custom Validation

```python
def validate_password(secret):
    value = secret.get_secret_value()
    return len(value) >= 8 and any(c.isdigit() for c in value)

is_valid = settings.validate_secret("password", validate_password)
```

## Security Features

### Encryption

```python
# Configure encryption
settings = create_secrets_settings(
    provider_type="local",
    ENCRYPTION_TYPE="fernet",
    ENCRYPTION_KEY="your-base64-key"
)
```

### Secret Protection

- All secrets are handled using `SecretStr`
- Memory protection where possible
- Automatic cache clearing
- Secure error messages

## Error Handling

The module provides specific exceptions for different scenarios:

```python
from mountainash_settings.auth.secrets.exceptions import (
    SecretConfigurationError,  # Configuration issues
    SecretAuthenticationError,  # Auth failures
    SecretNotFoundError,       # Missing secrets
    SecretAccessError,         # Access issues
    SecretValidationError,     # Validation failures
    SecretOperationError       # General operations
)
```

## Best Practices

1. **Configuration**:
   - Use environment variables for credentials
   - Implement proper secret rotation
   - Configure appropriate timeouts
   - Use namespaces for isolation

2. **Security**:
   - Enable encryption for local storage
   - Set appropriate cache TTLs
   - Implement proper access controls
   - Use version control where available

3. **Error Handling**:
   - Catch specific exceptions
   - Implement proper logging
   - Use validation functions
   - Handle connection failures

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/mountainash-settings.git
cd mountainash-settings

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Unix
venv\Scripts\activate    # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest tests/test_secrets

# Run specific provider tests
pytest tests/test_secrets/test_aws.py
pytest tests/test_secrets/test_azure.py

# Run with coverage
pytest --cov=mountainash_settings.auth.secrets tests/test_secrets
```

### Type Checking

```bash
mypy mountainash_settings/auth/secrets
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Support

For support, please:
1. Check the documentation
2. Search existing issues
3. Open a new issue if needed

## Changelog

See CHANGELOG.md for version history and updates.
