# path: tests/auth/storage/test_storage_auth.py


# path: tests/auth/storage/base/test_storage_auth_base.py

import pytest
from datetime import datetime
import tempfile
import os
from pathlib import Path
from typing import Type, Any, Dict

from mountainash_settings.auth.storage.base import StorageAuthBase
from mountainash_settings.auth.storage.constants import (
    CONST_STORAGE_PROVIDER_TYPE,
    CONST_STORAGE_AUTH_METHOD,
    CONST_STORAGE_ACCESS_TYPE
)
from mountainash_settings.auth.storage.exceptions import (
    StorageValidationError,
    StorageConfigError,
    StorageSecurityError
)

class BaseStorageAuthTests:
    """
    Base class for storage authentication tests.
    Each storage provider's test class should inherit from this.
    """
    
    # To be implemented by child classes
    provider_class: Type[StorageAuthBase] = None
    provider_type: str = None
    
    # Example valid config - override in child classes
    valid_config: Dict[str, Any] = {
        "PROVIDER_TYPE": None,  # Set in child class
        "AUTH_METHOD": CONST_STORAGE_AUTH_METHOD.KEY.value,
        "ACCESS_KEY": "test_key",
        "SECRET_KEY": "test_secret"
    }
    
    # @pytest.fixture
    # def storage_auth(self):
    #     """Create instance of storage auth class with valid config"""
    #     if not self.provider_class or not self.provider_type:
    #         pytest.skip("Test class not properly configured")
            
    #     config = self.valid_config.copy()
    #     config["PROVIDER_TYPE"] = self.provider_type
    #     return self.provider_class(**config)

    @pytest.fixture
    def temp_key_file(self):
        """Create a temporary encryption key file"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test-encryption-key")
            return f.name

    def test_basic_initialization(self, storage_auth):
        """Test basic initialization with valid config"""
        assert storage_auth.PROVIDER_TYPE == self.provider_type
        assert storage_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY.value
        assert storage_auth.ACCESS_KEY_ID == "test_key"
        assert storage_auth.SECRET_KEY.get_secret_value() == "test_secret"

    def test_provider_type_validation(self):
        """Test validation of provider type"""
        config = self.valid_config.copy()
        config["PROVIDER_TYPE"] = "invalid_provider"
        
        with pytest.raises(StorageValidationError) as exc_info:
            self.provider_class(**config)
        assert "Invalid provider type" in str(exc_info.value)

    def test_auth_method_validation(self, storage_auth):
        """Test validation of authentication method"""
        with pytest.raises(StorageValidationError) as exc_info:
            storage_auth.AUTH_METHOD = "invalid_method"
        assert "Invalid authentication method" in str(exc_info.value)

    def test_access_type_validation(self, storage_auth):
        """Test validation of access type"""
        # Valid access types
        for access_type in [
            CONST_STORAGE_ACCESS_TYPE.READ_ONLY.value,
            CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY.value,
            CONST_STORAGE_ACCESS_TYPE.READ_WRITE.value,
            CONST_STORAGE_ACCESS_TYPE.ADMIN.value
        ]:
            storage_auth.ACCESS_TYPE = access_type
            assert storage_auth.ACCESS_TYPE == access_type
        
        # Invalid access type
        with pytest.raises(StorageValidationError) as exc_info:
            storage_auth.ACCESS_TYPE = "invalid_access"
        assert "Invalid access type" in str(exc_info.value)

    @pytest.mark.parametrize("timeout", [-1, 0, 3601])
    def test_timeout_validation(self, storage_auth, timeout):
        """Test validation of timeout values"""
        with pytest.raises(StorageValidationError) as exc_info:
            storage_auth.TIMEOUT = timeout
        assert "Invalid timeout value" in str(exc_info.value)

    def test_encryption_validation(self, storage_auth):
        """Test validation of encryption settings"""
        # Test with encryption enabled but no key
        storage_auth.ENCRYPTION_ENABLED = True
        with pytest.raises(StorageSecurityError) as exc_info:
            storage_auth._validate_security_config()
        assert "Encryption enabled but no encryption key provided" in str(exc_info.value)

    def test_encryption_key_file(self, storage_auth, temp_key_file):

        """Test encryption key file handling"""
        storage_auth.ENCRYPTION_ENABLED = True
        storage_auth.ENCRYPTION_KEY_FILE = temp_key_file
        
        # Should not raise exception
        storage_auth._validate_security_config()
        
        # Test with non-existent key file
        storage_auth.ENCRYPTION_KEY_FILE = "/nonexistent/path"
        with pytest.raises(StorageSecurityError) as exc_info:
            storage_auth._validate_security_config()
        assert "Encryption key file not found" in str(exc_info.value)

    def test_ssl_validation(self, storage_auth):

        """Test SSL configuration validation"""
        storage_auth.USE_SSL = True
        storage_auth.VERIFY_SSL = True
        
        # Should raise error when no CA cert provided
        with pytest.raises(StorageSecurityError) as exc_info:
            storage_auth._validate_security_config()
        assert "SSL verification enabled but no CA certificate provided" in str(exc_info.value)

    # def test_cache_operations(self, storage_auth):
    #     """Test cache operations"""
    #     test_key = "test_key"
    #     test_value = "test_value"
        
    #     # Test cache set and get
    #     storage_auth._cache_set(test_key, test_value)
    #     assert storage_auth._cache_get(test_key) == test_value
        
    #     # Test cache expiration
    #     storage_auth.CACHE_TTL = 0
    #     assert storage_auth._cache_get(test_key) is None
        
    #     # Test cache deletion
    #     storage_auth.CACHE_TTL = 300
    #     storage_auth._cache_set(test_key, test_value)
    #     storage_auth._cache_delete(test_key)
    #     assert storage_auth._cache_get(test_key) is None

    def test_connection_url(self, storage_auth):
        """Test connection URL generation"""
        url = storage_auth.get_connection_url()
        assert isinstance(url, str)
        assert url  # URL should not be empty

    def test_connection_args(self, storage_auth):
        """Test connection arguments generation"""
        args = storage_auth.get_connection_args()
        assert isinstance(args, dict)
        
        # Check credential handling
        if storage_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY.value:
            assert "access_key" in args
            assert isinstance(args.get("secret_key"), str)

    def test_permission_validation(self, storage_auth):
        """Test permission validation"""
        # Set up test permissions for read-only access
        storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_ONLY.value
        storage_auth.REQUIRED_PERMISSIONS = {"read"}
        
        # Should pass validation
        storage_auth._validate_permissions()
        
        # Test insufficient permissions
        storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_WRITE.value
        with pytest.raises(StorageValidationError) as exc_info:
            storage_auth._validate_permissions()
        assert "Missing required permissions" in str(exc_info.value)

    @pytest.mark.parametrize("access_type,required_perms", [
        (CONST_STORAGE_ACCESS_TYPE.READ_ONLY, {"read"}),
        (CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY, {"write"}),
        (CONST_STORAGE_ACCESS_TYPE.READ_WRITE, {"read", "write"}),
        (CONST_STORAGE_ACCESS_TYPE.ADMIN, {"read", "write", "admin"})
    ])
    def test_access_type_permissions(self, storage_auth, access_type, required_perms):
        """Test permission requirements for different access types"""
        storage_auth.ACCESS_TYPE = access_type
        storage_auth.REQUIRED_PERMISSIONS = required_perms
        storage_auth._validate_permissions()

    def test_required_fields(self):
        """Test validation of required fields"""
        # Try to create instance with minimal config
        minimal_config = {"PROVIDER_TYPE": self.provider_type}
        with pytest.raises(StorageConfigError) as exc_info:
            self.provider_class(**minimal_config)
        assert "Required field" in str(exc_info.value)

    # def test_connection_validation(self, storage_auth):
    #     """Test connection validation"""
    #     # This is a basic test - providers should override with specific tests
    #     result = storage_auth.validate_connection()
    #     assert isinstance(result, bool)

    def test_post_init_hook(self, storage_auth):
        """Test post-initialization hook"""
        # Force reinitialize
        storage_auth.post_init(reinitialise=True)
        assert storage_auth._connection_tested is False

    @pytest.mark.benchmark
    # def test_performance_cache(self, storage_auth, benchmark):
    #     """Benchmark cache operations"""
    #     def cache_operation():
    #         storage_auth._cache_set("test_key", "test_value")
    #         return storage_auth._cache_get("test_key")
            
    #     result = benchmark(cache_operation)
    #     assert result == "test_value"

    @pytest.mark.benchmark
    def test_performance_url(self, storage_auth, benchmark):
        """Benchmark connection URL generation"""
        result = benchmark(storage_auth.get_connection_url)
        assert isinstance(result, str)



# import pytest
# from unittest.mock import Mock, patch
# import os
# # from upath import UPath
# import tempfile
# from datetime import datetime

# from mountainash_settings.auth.storage import StorageAuthBase
# from mountainash_settings.auth.storage import (
#     CONST_STORAGE_PROVIDER_TYPE,
#     CONST_STORAGE_AUTH_METHOD,
#     CONST_STORAGE_ACCESS_TYPE
# )
# from mountainash_settings.auth.storage import (
#     StorageValidationError,
#     StorageConfigError,
#     StorageSecurityError,
#     StorageConnectionError
# )

# # Test base configuration class
# class TestStorageAuthBase:
#     @pytest.fixture
#     def mock_storage_auth(self):
#         """Create a concrete implementation of StorageAuthBase for testing"""
#         class MockStorageAuth(StorageAuthBase):
#             def _init_provider_specific(self, reinitialise: bool) -> None:
#                 pass
                
#             def get_connection_url(self) -> str:
#                 return "mock://localhost/test"
            
#             def _validate_permissions(self) -> None:
#                 pass
                
#         return MockStorageAuth(
#             PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
#             AUTH_METHOD=CONST_STORAGE_AUTH_METHOD.KEY,
#             ACCESS_KEY="test_key",
#             SECRET_KEY="test_secret"
#         )

#     def test_basic_initialization(self, mock_storage_auth):
#         """Test basic initialization of storage auth settings"""
#         assert mock_storage_auth.PROVIDER_TYPE == CONST_STORAGE_PROVIDER_TYPE.LOCAL
#         assert mock_storage_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY
#         assert mock_storage_auth.ACCESS_KEY == "test_key"
#         assert mock_storage_auth.SECRET_KEY.get_secret_value() == "test_secret"

#     def test_invalid_provider_type(self, mock_storage_auth):
#         """Test validation of invalid provider type"""
#         with pytest.raises(StorageValidationError) as exc_info:
#             mock_storage_auth(PROVIDER_TYPE="invalid")
#         assert "Invalid provider type" in str(exc_info.value)

#     def test_missing_required_fields(self, mock_storage_auth):
#         """Test validation of missing required fields"""
#         with pytest.raises(StorageConfigError) as exc_info:
#             mock_storage_auth()
#         assert "Required field missing" in str(exc_info.value)

#     def test_invalid_auth_method(self, mock_storage_auth):
#         """Test validation of invalid authentication method"""
#         with pytest.raises(StorageValidationError) as exc_info:
#             mock_storage_auth.AUTH_METHOD = "invalid"
#         assert "Invalid authentication method" in str(exc_info.value)

#     def test_access_type_validation(self, mock_storage_auth):
#         """Test validation of access type"""
#         # Valid access types
#         mock_storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_ONLY
#         assert mock_storage_auth.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY
        
#         # Invalid access type
#         with pytest.raises(StorageValidationError) as exc_info:
#             mock_storage_auth.ACCESS_TYPE = "invalid"
#         assert "Invalid access type" in str(exc_info.value)

#     @pytest.mark.parametrize("timeout", [-1, 0, 3601])
#     def test_invalid_timeout_values(self, mock_storage_auth, timeout):
#         """Test validation of timeout values"""
#         with pytest.raises(StorageValidationError) as exc_info:
#             mock_storage_auth.TIMEOUT = timeout
#         assert "Invalid timeout value" in str(exc_info.value)

# # Test encryption and security features
# class TestStorageSecurity:
#     @pytest.fixture
#     def temp_key_file(self):
#         """Create a temporary encryption key file"""
#         with tempfile.NamedTemporaryFile(delete=False) as f:
#             f.write(b"test-encryption-key")
#             return f.name

#     def test_encryption_key_validation(self, mock_storage_auth):
#         """Test validation of encryption settings"""
#         # Test with encryption enabled but no key
#         mock_storage_auth.ENCRYPTION_ENABLED = True
#         with pytest.raises(StorageSecurityError) as exc_info:
#             mock_storage_auth._validate_security_config()
#         assert "Encryption enabled but no encryption key provided" in str(exc_info.value)

#     def test_encryption_key_file_handling(self, mock_storage_auth, temp_key_file):
#         """Test handling of encryption key files"""
#         mock_storage_auth.ENCRYPTION_ENABLED = True
#         mock_storage_auth.ENCRYPTION_KEY_FILE = temp_key_file
        
#         # Should not raise exception
#         mock_storage_auth._validate_security_config()
        
#         # Test with non-existent key file
#         mock_storage_auth.ENCRYPTION_KEY_FILE = "/nonexistent/path"
#         with pytest.raises(StorageSecurityError) as exc_info:
#             mock_storage_auth._validate_security_config()
#         assert "Encryption key file not found" in str(exc_info.value)

#     def test_ssl_configuration(self, mock_storage_auth):
#         """Test SSL configuration validation"""
#         mock_storage_auth.USE_SSL = True
#         mock_storage_auth.VERIFY_SSL = True
        
#         # Should raise error when no CA cert provided
#         with pytest.raises(StorageSecurityError) as exc_info:
#             mock_storage_auth._validate_security_config()
#         assert "SSL verification enabled but no CA certificate provided" in str(exc_info.value)

# # Test caching functionality
# class TestStorageCaching:
#     def test_cache_operations(self, mock_storage_auth):
#         """Test basic cache operations"""
#         test_key = "test_key"
#         test_value = "test_value"
        
#         # Test cache set
#         mock_storage_auth._cache_set(test_key, test_value)
        
#         # Test cache get
#         cached = mock_storage_auth._cache_get(test_key)
#         assert cached == test_value
        
#         # Test cache expiration
#         mock_storage_auth.CACHE_TTL = 0  # Immediate expiration
#         cached = mock_storage_auth._cache_get(test_key)
#         assert cached is None

#     def test_cache_cleanup(self, mock_storage_auth):
#         """Test cache cleanup operations"""
#         # Add some test data
#         mock_storage_auth._cache_set("key1", "value1")
#         mock_storage_auth._cache_set("key2", "value2")
        
#         # Delete specific key
#         mock_storage_auth._cache_delete("key1")
#         assert mock_storage_auth._cache_get("key1") is None
#         assert mock_storage_auth._cache_get("key2") == "value2"

# # Test connection handling
# class TestStorageConnection:
#     def test_connection_url_generation(self, mock_storage_auth):
#         """Test generation of connection URLs"""
#         url = mock_storage_auth.get_connection_url()
#         assert url == "mock://localhost/test"

#     def test_connection_args(self, mock_storage_auth):
#         """Test generation of connection arguments"""
#         args = mock_storage_auth.get_connection_args()
        
#         # Check basic args
#         assert "endpoint" in args
#         assert "timeout" in args
        
#         # Check credential handling
#         assert "access_key" in args
#         assert isinstance(args.get("secret_key"), str)

#     # @patch("mountainash_settings.auth.storage.base.StorageAuthBase._test_connection")
#     # def test_connection_validation(self, mock_test, mock_storage_auth):
#     #     """Test connection validation logic"""
#     #     # Test successful validation
#     #     mock_test.return_value = True
#     #     assert mock_storage_auth.validate_connection()
        
#     #     # Test failed validation
#     #     mock_test.return_value = False
#     #     with pytest.raises(StorageConnectionError):
#     #         mock_storage_auth.validate_connection()

# # Test provider-specific implementations
# class TestStorageProviders:
#     @pytest.fixture
#     def s3_settings(self):
#         """Create S3 storage settings fixture"""
#         from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
#         return S3StorageAuthSettings(
#             PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.S3,
#             REGION="us-west-2",
#             BUCKET="test-bucket",
#             ACCESS_KEY_ID="test-key",
#             SECRET_ACCESS_KEY="test-secret"
#         )

#     @pytest.fixture
#     def azure_blob_settings(self):
#         """Create Azure Blob storage settings fixture"""
#         from mountainash_settings.auth.storage.providers.cloud.azure_blob import AzureBlobStorageAuthSettings
#         return AzureBlobStorageAuthSettings(
#             PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
#             ACCOUNT_NAME="testaccount",
#             CONTAINER_NAME="testcontainer",
#             CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
#         )

#     def test_s3_validation(self, s3_settings):
#         """Test S3-specific validation"""
#         # Test region validation
#         with pytest.raises(StorageValidationError) as exc_info:
#             s3_settings.REGION = "invalid-region"
#         assert "Invalid AWS region format" in str(exc_info.value)
        
#         # Test bucket name validation
#         with pytest.raises(StorageValidationError) as exc_info:
#             s3_settings.BUCKET = "Invalid.Bucket.Name"
#         assert "Invalid bucket name format" in str(exc_info.value)

#     def test_azure_blob_validation(self, azure_blob_settings):
#         """Test Azure Blob-specific validation"""
#         # Test account name validation
#         with pytest.raises(StorageValidationError) as exc_info:
#             azure_blob_settings.ACCOUNT_NAME = "invalid@account"
#         assert "Invalid account name format" in str(exc_info.value)
        
#         # Test container name validation
#         with pytest.raises(StorageValidationError) as exc_info:
#             azure_blob_settings.CONTAINER_NAME = "Invalid-Container"
#         assert "Invalid container name format" in str(exc_info.value)

# # Test permission handling
# class TestStoragePermissions:
#     def test_permission_validation(self, mock_storage_auth):
#         """Test permission validation logic"""
#         # Set up test permissions
#         mock_storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_ONLY
#         mock_storage_auth.REQUIRED_PERMISSIONS = {"read"}
        
#         # Should pass validation
#         mock_storage_auth._validate_permissions()
        
#         # Test insufficient permissions
#         mock_storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_WRITE
#         with pytest.raises(StorageValidationError) as exc_info:
#             mock_storage_auth._validate_permissions()
#         assert "Missing required permissions" in str(exc_info.value)

#     def test_access_type_permissions(self, mock_storage_auth):
#         """Test permission requirements for different access types"""
#         test_cases = [
#             (CONST_STORAGE_ACCESS_TYPE.READ_ONLY, {"read"}),
#             (CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY, {"write"}),
#             (CONST_STORAGE_ACCESS_TYPE.READ_WRITE, {"read", "write"}),
#             (CONST_STORAGE_ACCESS_TYPE.ADMIN, {"read", "write", "admin"})
#         ]
        
#         for access_type, required_perms in test_cases:
#             mock_storage_auth.ACCESS_TYPE = access_type
#             mock_storage_auth.REQUIRED_PERMISSIONS = required_perms
#             mock_storage_auth._validate_permissions()

# # Integration tests
# class TestStorageIntegration:
#     @pytest.fixture
#     def storage_factory(self):
#         """Create storage settings factory fixture"""
#         from mountainash_settings.auth.storage.factory import StorageAuthFactory
#         return StorageAuthFactory()

#     def test_provider_registration(self, storage_factory):
#         """Test provider registration and lookup"""
#         from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
        
#         # Register provider
#         storage_factory.register_provider(CONST_STORAGE_PROVIDER_TYPE.S3, S3StorageAuthSettings)
        
#         # Look up provider
#         provider_class = storage_factory.get_provider_class(CONST_STORAGE_PROVIDER_TYPE.S3)
#         assert provider_class == S3StorageAuthSettings
        
#         # Test unknown provider
#         with pytest.raises(StorageConfigError):
#             storage_factory.get_provider_class("unknown")

#     def test_settings_creation(self, storage_factory):
#         """Test creation of storage settings"""
#         # Register test provider
#         from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
#         storage_factory.register_provider(CONST_STORAGE_PROVIDER_TYPE.S3, S3StorageAuthSettings)
        
#         # Create settings
#         settings = storage_factory.create_auth_settings(
#             provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
#             settings_namespace="test",
#             REGION="us-west-2",
#             BUCKET="test-bucket",
#             ACCESS_KEY_ID="test-key",
#             SECRET_ACCESS_KEY="test-secret"
#         )
        
#         assert isinstance(settings, S3StorageAuthSettings)
#         assert settings.REGION == "us-west-2"
#         assert settings.BUCKET == "test-bucket"

#     def test_provider_capabilities(self, storage_factory):
#         """Test provider capability checking"""
#         from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
#         storage_factory.register_provider(CONST_STORAGE_PROVIDER_TYPE.S3, S3StorageAuthSettings)
        
#         provider_info = storage_factory.get_provider_info(CONST_STORAGE_PROVIDER_TYPE.S3)
        
#         assert "type" in provider_info
#         assert "supported_features" in provider_info
#         assert provider_info["type"] == CONST_STORAGE_PROVIDER_TYPE.S3

# # Performance tests
# class TestStoragePerformance:
#     @pytest.mark.benchmark
#     def test_cache_performance(self, mock_storage_auth, benchmark):
#         """Benchmark cache operations"""
#         def cache_operation():
#             mock_storage_auth._cache_set("test_key", "test_value")
#             return mock_storage_auth._cache_get("test_key")
            
#         result = benchmark(cache_operation)
#         assert result == "test_value"

#     @pytest.mark.benchmark
#     def test_connection_url_performance(self, mock_storage_auth, benchmark):
#         """Benchmark connection URL generation"""
#         result = benchmark(mock_storage_auth.get_connection_url)
#         assert isinstance(result, str)

# # Error handling tests
# # class TestStorageErrors:
# #     def test_error_propagation(self, mock_storage_auth):
# #         """Test error propagation through the storage stack"""
# #         with pytest.raises(StorageValidationError):
# #             mock_storage_auth.PROVIDER_TYPE = "invalid"
            
# #         with pytest.raises(StorageConfigError):
# #             mock_storage_auth.ENCRYPTION_ENABLED = True
# #             mock_storage_auth._validate_security_config()
            
# #         with pytest.raises(StorageSecurityError):
# #             mock_storage_auth.USE_SSL = True
# #             mock_storage_auth.VERIFY_SSL = True
# #             mock_storage_auth._validate_security_config()

