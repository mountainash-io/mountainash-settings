
import pytest
from unittest.mock import Mock, patch
from google.api_core import exceptions as google_exceptions
from pydantic import SecretStr

from mountainash_settings.auth.secrets.providers.gcp_secrets import GCPSecretsSettings
from mountainash_settings.auth.secrets.exceptions import (
    SecretNotFoundError,
    SecretAccessError
)

@pytest.fixture
def mock_gcp_client():
    """Mock GCP Secret Manager client"""
    with patch('google.cloud.secretmanager.SecretManagerServiceClient') as mock_client:
        yield mock_client

@pytest.fixture
def gcp_secrets(mock_gcp_client):
    """Create GCP secrets settings instance"""
    return GCPSecretsSettings(
        PROJECT_ID="test-project",
        SERVICE_ACCOUNT_INFO={"type": "service_account"}
    )

def test_gcp_initialization(gcp_secrets):
    """Test GCP secrets initialization"""
    assert gcp_secrets.PROJECT_ID == "test-project"
    assert gcp_secrets.SERVICE_ACCOUNT_INFO == {"type": "service_account"}

def test_gcp_project_id_validation():
    """Test project ID validation"""
    with pytest.raises(SecretValidationError):
        GCPSecretsSettings(PROJECT_ID=None)

def test_gcp_get_secret(gcp_secrets, mock_gcp_client):
    """Test getting a secret from GCP Secret Manager"""
    mock_client = Mock()
    mock_gcp_client.return_value = mock_client
    
    # Mock successful response
    mock_response = Mock()
    mock_response.payload.data.decode.return_value = "test-value"
    mock_client.access_secret_version.return_value = mock_response
    
    secret = gcp_secrets.get_secret("test-secret")
    assert secret.get_secret_value() == "test-value"
    
    # Test secret not found
    mock_client.access_secret_version.side_effect = google_exceptions.NotFound("not found")
    with pytest.raises(SecretNotFoundError):
        gcp_secrets.get_secret("missing-secret")