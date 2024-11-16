# # tests/test_secrets/conftest.py

# import pytest
# from typing import Dict, Any, Optional
# from datetime import datetime
# import os
# import tempfile
# import json
# import base64
# from cryptography.fernet import Fernet
# from pydantic import SecretStr

# from mountainash_settings.auth.secrets import (
#     CONST_SECRET_PROVIDER_TYPE,
#     CONST_SECRET_AUTH_METHOD,
#     CONST_SECRET_VERSION_HANDLING,
#     CONST_SECRET_ENCODING
# )
# from mountainash_settings.auth.secrets.base import SecretsAuthBase

# @pytest.fixture(autouse=True)
# def clean_environment():
#     """Clean environment variables before each test"""
#     # Save original environment
#     original_env = dict(os.environ)
    
#     # Clean environment for test
#     for key in list(os.environ.keys()):
#         if key.startswith('TEST_'):
#             del os.environ[key]
    
#     yield
    
#     # Restore original environment
#     os.environ.clear()
#     os.environ.update(original_env)

# @pytest.fixture
# def temp_config_file():
#     """Create a temporary configuration file"""
#     with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
#         f.write('{"PROVIDER_TYPE": "mock", "AUTH_METHOD": "mock"}')
#         temp_path = f.name
    
#     yield temp_path
    
#     # Cleanup
#     if os.path.exists(temp_path):
#         os.unlink(temp_path)

# @pytest.fixture
# def temp_encryption_key_file():
#     """Create a temporary encryption key file"""
#     key = Fernet.generate_key()
#     with tempfile.NamedTemporaryFile(mode='wb', suffix='.key', delete=False) as f:
#         f.write(key)
#         temp_path = f.name
    
#     yield temp_path
    
#     # Cleanup
#     if os.path.exists(temp_path):
#         os.unlink(temp_path)

# @pytest.fixture
# def mock_secret_data() -> Dict[str, Any]:
#     """Provide mock secret data for testing"""
#     return {
#         'secret1': {
#             'value': 'value1',
#             'version': '1',
#             'created': datetime.now().isoformat(),
#             'metadata': {'purpose': 'testing'}
#         },
#         'secret2': {
#             'value': 'value2',
#             'version': '1',
#             'created': datetime.now().isoformat(),
#             'metadata': {'environment': 'test'}
#         },
#         'secret3': {
#             'value': 'value3',
#             'version': '2',
#             'created': datetime.now().isoformat(),
#             'metadata': {'type': 'credential'}
#         }
#     }

# @pytest.fixture
# def mock_secrets_with_versions() -> Dict[str, Dict[str, Any]]:
#     """Provide mock secret data with version history"""
#     return {
#         'secret1': {
#             'versions': {
#                 '1': {
#                     'value': 'value1_v1',
#                     'created': (datetime.now().isoformat()),
#                     'status': 'active'
#                 },
#                 '2': {
#                     'value': 'value1_v2',
#                     'created': (datetime.now().isoformat()),
#                     'status': 'active'
#                 }
#             },
#             'metadata': {
#                 'created': datetime.now().isoformat(),
#                 'last_updated': datetime.now().isoformat(),
#                 'tags': {'environment': 'test'}
#             }
#         }
#     }

# class MockSecretsBase(SecretsAuthBase):
#     """Base class for mock secrets implementations"""
#     def __init__(self, mock_data: Optional[Dict[str, Any]] = None, **kwargs):
#         super().__init__(**kwargs)
#         self._mock_data = mock_data or {}
        
#     def _init_provider_specific(self, reinitialise: bool = False):
#         pass

# @pytest.fixture
# def mock_provider_configs() -> Dict[str, Dict[str, Any]]:
#     """Provide mock configurations for different providers"""
#     return {
#         'aws': {
#             'PROVIDER_TYPE': CONST_SECRET_PROVIDER_TYPE.AWS_SECRETS,
#             'REGION': 'us-west-2',
#             'ACCESS_KEY_ID': 'test-key',
#             'SECRET_ACCESS_KEY': SecretStr('test-secret'),
#             'SECRET_NAMESPACE': 'test'
#         },
#         'azure': {
#             'PROVIDER_TYPE': CONST_SECRET_PROVIDER_TYPE.AZURE_KEYVAULT,
#             'VAULT_NAME': 'test-vault',
#             'TENANT_ID': 'test-tenant',
#             'CLIENT_ID': 'test-client',
#             'CLIENT_SECRET': SecretStr('test-secret')
#         },
#         'gcp': {
#             'PROVIDER_TYPE': CONST_SECRET_PROVIDER_TYPE.GCP_SECRETS,
#             'PROJECT_ID': 'test-project',
#             'SERVICE_ACCOUNT_INFO': {'type': 'service_account'}
#         },
#         'hashicorp': {
#             'PROVIDER_TYPE': CONST_SECRET_PROVIDER_TYPE.HASHICORP,
#             'VAULT_HOST': 'localhost',
#             'VAULT_TOKEN': SecretStr('test-token'),
#             'KV_VERSION': 2
#         }
#     }

# @pytest.fixture
# def temp_secrets_directory():
#     """Create a temporary directory for secret storage"""
#     with tempfile.TemporaryDirectory() as temp_dir:
#         yield temp_dir

# @pytest.fixture
# def mock_encryption():
#     """Provide encryption-related test utilities"""
#     key = Fernet.generate_key()
#     f = Fernet(key)
    
#     class EncryptionUtils:
#         @staticmethod
#         def encrypt(value: str) -> str:
#             return f.encrypt(value.encode()).decode()
        
#         @staticmethod
#         def decrypt(value: str) -> str:
#             return f.decrypt(value.encode()).decode()
        
#         @property
#         def key(self) -> bytes:
#             return key
    
#     return EncryptionUtils()

# @pytest.fixture
# def encoded_secrets():
#     """Provide pre-encoded secret values"""
#     plain_values = {
#         'secret1': 'test-value-1',
#         'secret2': 'test-value-2',
#         'secret3': 'test-value-3'
#     }
    
#     return {
#         'none': {name: value for name, value in plain_values.items()},
#         'base64': {
#             name: base64.b64encode(value.encode()).decode()
#             for name, value in plain_values.items()
#         }
#     }

# @pytest.fixture
# def mock_validation_functions():
#     """Provide common validation functions for testing"""
#     def validate_length(secret: SecretStr, min_length: int = 8) -> bool:
#         return len(secret.get_secret_value()) >= min_length
    
#     def validate_format(secret: SecretStr, prefix: str = '') -> bool:
#         return secret.get_secret_value().startswith(prefix)
    
#     def validate_content(secret: SecretStr, required_chars: str = '') -> bool:
#         return all(char in secret.get_secret_value() for char in required_chars)
    
#     return {
#         'length': validate_length,
#         'format': validate_format,
#         'content': validate_content
#     }

# @pytest.fixture
# def mock_error_responses():
#     """Provide mock error responses for different providers"""
#     return {
#         'aws': {
#             'not_found': {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
#             'access_denied': {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
#             'validation': {'Error': {'Code': 'ValidationException', 'Message': 'Validation failed'}}
#         },
#         'azure': {
#             'not_found': {'status_code': 404, 'message': 'Secret not found'},
#             'access_denied': {'status_code': 403, 'message': 'Access denied'},
#             'validation': {'status_code': 400, 'message': 'Validation failed'}
#         },
#         'gcp': {
#             'not_found': 'NOT_FOUND',
#             'access_denied': 'PERMISSION_DENIED',
#             'validation': 'INVALID_ARGUMENT'
#         },
#         'vault': {
#             'not_found': 'Secret not found at: test-secret',
#             'access_denied': 'permission denied',
#             'validation': 'invalid secret'
#         }
#     }

# @pytest.fixture
# def mock_cache_data():
#     """Provide mock cache data with timestamps"""
#     now = datetime.now()
#     return {
#         'fresh': {
#             'value': 'cached-value-1',
#             'timestamp': now
#         },
#         'stale': {
#             'value': 'cached-value-2',
#             'timestamp': now - timedelta(minutes=10)
#         }
#     }