
# import pytest
# from unittest.mock import Mock, patch
# from azure.core.exceptions import HttpResponseError
# from pydantic import SecretStr

# from mountainash_settings.auth.secrets.providers.azure_keyvault import AzureKeyVaultSettings
# from mountainash_settings.auth.secrets.exceptions import (
#     SecretNotFoundError,
#     SecretValidationError
# )

# @pytest.fixture
# def mock_azure_client():
#     """Mock Azure KeyVault client"""
#     with patch('azure.keyvault.secrets.SecretClient') as mock_client:
#         yield mock_client

# @pytest.fixture
# def azure_secrets(mock_azure_client):
#     """Create Azure secrets settings instance"""
#     return AzureKeyVaultSettings(
#         VAULT_NAME="test-vault",
#         TENANT_ID="test-tenant",
#         CLIENT_ID="test-client",
#         CLIENT_SECRET=SecretStr("test-secret")
#     )

# def test_azure_initialization(azure_secrets):
#     """Test Azure secrets initialization"""
#     assert azure_secrets.VAULT_NAME == "test-vault"
#     assert azure_secrets.TENANT_ID == "test-tenant"
#     assert azure_secrets.CLIENT_ID == "test-client"

# def test_azure_vault_name_validation():
#     """Test vault name validation"""
#     with pytest.raises(SecretValidationError):
#         AzureKeyVaultSettings(
#             VAULT_NAME="invalid vault",
#             TENANT_ID="test-tenant",
#             CLIENT_ID="test-client",
#             CLIENT_SECRET=SecretStr("test-secret")
#         )

# def test_azure_get_secret(azure_secrets, mock_azure_client):
#     """Test getting a secret from Azure KeyVault"""
#     mock_client = Mock()
#     mock_azure_client.return_value = mock_client
    
#     # Mock successful response
#     mock_secret = Mock()
#     mock_secret.value = "test-value"
#     mock_client.get_secret.return_value = mock_secret
    
#     secret = azure_secrets.get_secret("test-secret")
#     assert secret.get_secret_value() == "test-value"
    
#     # Test secret not found
#     mock_client.get_secret.side_effect = HttpResponseError(status_code=404)
#     with pytest.raises(SecretNotFoundError):
#         azure_secrets.get_secret("missing-secret")