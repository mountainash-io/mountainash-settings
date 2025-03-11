
# import pytest
# from unittest.mock import Mock, patch
# from hvac.exceptions import InvalidPath, Forbidden
# from pydantic import SecretStr

# from mountainash_settings.auth.secrets.providers.hashicorp_vault import HashiCorpVaultSettings
# from mountainash_settings.auth.secrets.exceptions import (
#     SecretNotFoundError,
#     SecretAccessError
# )

# @pytest.fixture
# def mock_hvac_client():
#     """Mock HashiCorp Vault client"""
#     with patch('hvac.Client') as mock_client:
#         yield mock_client

# @pytest.fixture
# def vault_secrets(mock_hvac_client):
#     """Create HashiCorp Vault secrets settings instance"""
#     return HashiCorpVaultSettings(
#         VAULT_HOST="localhost",
#         VAULT_TOKEN=SecretStr("test-token")
#     )

# def test_vault_initialization(vault_secrets):
#     """Test HashiCorp Vault initialization"""
#     assert vault_secrets.VAULT_HOST == "localhost"
#     assert vault_secrets.VAULT_TOKEN == "test-token"

# def test_vault_host_validation():
#     """Test vault host validation"""
#     with pytest.raises(SecretValidationError):
#         HashiCorpVaultSettings(
#             VAULT_HOST=None,
#             VAULT_TOKEN=SecretStr("test-token")
#         )

# def test_vault_get_secret(vault_secrets, mock_hvac_client):
#     """Test getting a secret from HashiCorp Vault"""
#     mock_client = Mock()
#     mock_hvac_client.return_value = mock_client
    
#     # Mock successful response
#     mock_client.secrets.kv.v2.read_secret_version.return_value = {
#         'data': {'data': {'value': 'test-value'}}
#     }
    
#     secret = vault_secrets.get_secret("test-secret")
#     assert secret == "test-value"
    
#     # Test secret not found
#     mock_client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath("not found")
#     with pytest.raises(SecretNotFoundError):
#         vault_secrets.get_secret("missing-secret")