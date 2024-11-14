
import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from pydantic import SecretStr

from mountainash_settings.auth.secrets.providers.aws_secrets import AWSSecretsSettings
from mountainash_settings.auth.secrets.exceptions import (
    SecretNotFoundError,
    SecretAccessError,
    SecretAuthenticationError,
    SecretValidationError
)

@pytest.fixture
def mock_boto3():
    """Mock boto3 client"""
    with patch('boto3.client') as mock_client:
        yield mock_client

@pytest.fixture
def aws_secrets(mock_boto3):
    """Create AWS secrets settings instance"""
    return AWSSecretsSettings(
        REGION="us-west-2",
        ACCESS_KEY_ID="test-key",
        SECRET_ACCESS_KEY=SecretStr("test-secret"),
        SECRET_NAMESPACE="test"
    )

def test_aws_initialization(aws_secrets):
    """Test AWS secrets initialization"""
    assert aws_secrets.REGION == "us-west-2"
    assert aws_secrets.ACCESS_KEY_ID == "test-key"
    assert aws_secrets.SECRET_ACCESS_KEY.get_secret_value() == "test-secret"

def test_aws_region_validation():
    """Test AWS region validation"""
    with pytest.raises(SecretValidationError):
        AWSSecretsSettings(
            REGION="invalid-region",
            ACCESS_KEY_ID="test-key",
            SECRET_ACCESS_KEY=SecretStr("test-secret")
        )

def test_aws_get_secret(aws_secrets, mock_boto3):
    """Test getting a secret from AWS"""
    mock_client = Mock()
    mock_boto3.return_value = mock_client
    
    # Mock successful response
    mock_client.get_secret_value.return_value = {
        'SecretString': 'test-value'
    }
    
    secret = aws_secrets.get_secret("test-secret")
    assert secret.get_secret_value() == "test-value"
    
    # Test secret not found
    mock_client.get_secret_value.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}},
        'GetSecretValue'
    )
    with pytest.raises(SecretNotFoundError):
        aws_secrets.get_secret("missing-secret")

def test_aws_list_secrets(aws_secrets, mock_boto3):
    """Test listing secrets from AWS"""
    mock_client = Mock()
    mock_boto3.return_value = mock_client
    
    # Mock paginator
    mock_paginator = Mock()
    mock_client.get_paginator.return_value = mock_paginator
    
    mock_paginator.paginate.return_value = [{
        'SecretList': [
            {'Name': 'test/secret1'},
            {'Name': 'test/secret2'}
        ]
    }]
    
    secrets = aws_secrets.list_secrets()
    assert len(secrets) == 2
    assert "secret1" in secrets
    assert "secret2" in secrets