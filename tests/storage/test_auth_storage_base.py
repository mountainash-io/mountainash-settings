# path: tests/auth/storage/base/test_auth_storage_base.py

import pytest
from datetime import datetime
import tempfile
import os
from upath import UPath
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
    
    @pytest.fixture
    def storage_auth(self):

        """Create instance of storage auth class with valid config"""
        if not self.provider_class or not self.provider_type:
            pytest.skip("Test class not properly configured")
            
        config = self.valid_config.copy()
        config["PROVIDER_TYPE"] = self.provider_type
        return self.provider_class(**config)

    # @pytest.fixture
    # def temp_key_file(self):
    #     """Create a temporary encryption key file"""
    #     with tempfile.NamedTemporaryFile(delete=False) as f:
    #         f.write(b"test-encryption-key")
    #         return f.name

    # def test_basic_initialization(self, storage_auth: StorageAuthBase):
    #     """Test basic initialization with valid config"""
    #     assert storage_auth.PROVIDER_TYPE == self.provider_type
    #     assert storage_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY.value
    #     assert storage_auth.ACCESS_KEY_ID == "test_key"
    #     assert storage_auth.SECRET_KEY.get_secret_value() == "test_secret"

    # def test_provider_type_validation(self):
    #     """Test validation of provider type"""

    #     if not self.provider_class or not self.provider_type:
    #         pytest.skip("Test class not properly configured")

    #     config = self.valid_config.copy()
    #     config["PROVIDER_TYPE"] = "invalid_provider"
        
    #     with pytest.raises(StorageValidationError) as exc_info:
    #         self.provider_class(**config)
    #     assert "Invalid provider type" in str(exc_info.value)

    # def test_auth_method_validation(self, storage_auth: StorageAuthBase):
    #     """Test validation of authentication method"""
    #     with pytest.raises(StorageValidationError) as exc_info:
    #         storage_auth.AUTH_METHOD = "invalid_method"
    #     assert "Invalid authentication method" in str(exc_info.value)

    # def test_access_type_validation(self, storage_auth: StorageAuthBase):
    #     """Test validation of access type"""
    #     # Valid access types
    #     for access_type in [
    #         CONST_STORAGE_ACCESS_TYPE.READ_ONLY.value,
    #         CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY.value,
    #         CONST_STORAGE_ACCESS_TYPE.READ_WRITE.value,
    #         CONST_STORAGE_ACCESS_TYPE.ADMIN.value
    #     ]:
    #         storage_auth.ACCESS_TYPE = access_type
    #         assert storage_auth.ACCESS_TYPE == access_type
        
    #     # Invalid access type
    #     with pytest.raises(StorageValidationError) as exc_info:
    #         storage_auth.ACCESS_TYPE = "invalid_access"
    #     assert "Invalid access type" in str(exc_info.value)

    # @pytest.mark.parametrize("timeout", [-1, 0, 3601])
    # def test_timeout_validation(self, storage_auth, timeout):
    #     """Test validation of timeout values"""
    #     with pytest.raises(StorageValidationError) as exc_info:
    #         storage_auth.TIMEOUT = timeout
    #     assert "Invalid timeout value" in str(exc_info.value)

    # def test_encryption_validation(self, storage_auth):
    #     """Test validation of encryption settings"""
    #     # Test with encryption enabled but no key
    #     storage_auth.ENCRYPTION_ENABLED = True
    #     with pytest.raises(StorageSecurityError) as exc_info:
    #         storage_auth._validate_security_config()
    #     assert "Encryption enabled but no encryption key provided" in str(exc_info.value)

    # def test_encryption_key_file(self, storage_auth, temp_key_file):

    #     """Test encryption key file handling"""
    #     storage_auth.ENCRYPTION_ENABLED = True
    #     storage_auth.ENCRYPTION_KEY_FILE = temp_key_file
        
    #     # Should not raise exception
    #     storage_auth._validate_security_config()
        
    #     # Test with non-existent key file
    #     storage_auth.ENCRYPTION_KEY_FILE = "/nonexistent/path"
    #     with pytest.raises(StorageSecurityError) as exc_info:
    #         storage_auth._validate_security_config()
    #     assert "Encryption key file not found" in str(exc_info.value)

    # def test_ssl_validation(self, storage_auth):

    #     """Test SSL configuration validation"""
    #     storage_auth.USE_SSL = True
    #     storage_auth.VERIFY_SSL = True
        
    #     # Should raise error when no CA cert provided
    #     with pytest.raises(StorageSecurityError) as exc_info:
    #         storage_auth._validate_security_config()
    #     assert "SSL verification enabled but no CA certificate provided" in str(exc_info.value)


    def test_connection_url(self, storage_auth: StorageAuthBase):
        """Test connection URL generation"""
        url = storage_auth.get_connection_url()
        assert isinstance(url, str)
        assert url  # URL should not be empty

    # def test_connection_args(self, storage_auth: StorageAuthBase):
    #     """Test connection arguments generation"""
    #     args = storage_auth.get_connection_args()
    #     assert isinstance(args, dict)
        
    #     # Check credential handling
    #     if storage_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY.value:
    #         assert "access_key" in args

    # def test_permission_validation(self, storage_auth):
    #     """Test permission validation"""
    #     # Set up test permissions for read-only access
    #     storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_ONLY.value
    #     storage_auth.REQUIRED_PERMISSIONS = {"read"}
        
    #     # Should pass validation
    #     storage_auth._validate_permissions()
        
    #     # Test insufficient permissions
    #     storage_auth.ACCESS_TYPE = CONST_STORAGE_ACCESS_TYPE.READ_WRITE.value
    #     with pytest.raises(StorageValidationError) as exc_info:
    #         storage_auth._validate_permissions()
    #     assert "Missing required permissions" in str(exc_info.value)

    # @pytest.mark.parametrize("access_type,required_perms", [
    #     (CONST_STORAGE_ACCESS_TYPE.READ_ONLY, {"read"}),
    #     (CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY, {"write"}),
    #     (CONST_STORAGE_ACCESS_TYPE.READ_WRITE, {"read", "write"}),
    #     (CONST_STORAGE_ACCESS_TYPE.ADMIN, {"read", "write", "admin"})
    # ])
    # def test_access_type_permissions(self, storage_auth, access_type, required_perms):
    #     """Test permission requirements for different access types"""
    #     storage_auth.ACCESS_TYPE = access_type
    #     storage_auth.REQUIRED_PERMISSIONS = required_perms
    #     storage_auth._validate_permissions()

    # def test_required_fields(self, storage_auth: StorageAuthBase):
    #     """Test validation of required fields"""
    #     # Try to create instance with minimal config

    #     if not self.provider_class or not self.provider_type:
    #         pytest.skip("Test class not properly configured")

    #     minimal_config = {"PROVIDER_TYPE": self.provider_type}
    #     with pytest.raises(StorageConfigError) as exc_info:
    #         self.provider_class(**minimal_config)
    #     assert "Required field" in str(exc_info.value)

    # @pytest.mark.benchmark
    # def test_performance_url(self, storage_auth, benchmark):
    #     """Benchmark connection URL generation"""
    #     result = benchmark(storage_auth.get_connection_url)
    #     assert isinstance(result, str)


