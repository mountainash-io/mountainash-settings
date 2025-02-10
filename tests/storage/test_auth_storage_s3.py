# # path: tests/auth/storage/providers/cloud/test_s3_storage_auth.py

# path: tests/auth/storage/providers/cloud/test_s3_storage_auth.py

import time
from mountainash_settings.settings_paramaters import settings_parameters
import pytest
from typing import Dict, Any, List, Type
import re
import yaml
from upath import UPath

from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
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

from mountainash_settings import get_settings, MountainAshBaseSettings, SettingsParameters, SettingsManager, get_settings_manager, SettingsUtils
from dotenv import dotenv_values, load_dotenv

from test_auth_storage_base import BaseStorageAuthTests

class TestS3StorageAuth(BaseStorageAuthTests):
    """
    Test cases for S3 storage authentication.
    Inherits common test cases from BaseStorageAuthTests.
    """
    
    # provider_class = S3StorageAuthSettings
    provider_type = CONST_STORAGE_PROVIDER_TYPE.S3.value
    # settings_namespace = "TestS3StorageAuth"

    @pytest.fixture
    def config_file_path(self) -> UPath:
        """Get path to S3 config file"""
        return UPath(__file__).parent.parent.parent / "config" / "auth" / "storage" / "cloud" / "s3.env"

    @pytest.fixture
    def base_config(self, config_file_path) -> Dict[str, Any]:
        """Load base configuration from YAML file"""
        # with config_file_path.open() as f:
        #     return yaml.safe_load(f)
        return dotenv_values(config_file_path)


    # def base_env_config(config_env_path) -> Dict[str, Any]:
    #     """Load base configuration from .env file"""
    #     # Using python-dotenv's dotenv_values which returns a dict without modifying os.environ
    #     return dotenv_values(config_env_path)

    # @pytest.fixture
    # def settings_manager() -> SettingsManager:
    #     settings_manager: SettingsManager = get_settings_manager()
    #     # settings_manager: SettingsManager = SettingsManager()
    #     return settings_manager
    @pytest.fixture
    def provider_class(self) -> Type[S3StorageAuthSettings]:
        return S3StorageAuthSettings



    @pytest.fixture
    def settings_namespace(self) -> str:
        return "TestS3StorageAuth"


    @pytest.fixture
    def settings_parameters(self, provider_class, config_file_path, settings_namespace) -> SettingsParameters:
        
        # config_files: List[Any] = str(config_file_path)
        kwargs = {}
        
        settings_parameters = SettingsParameters.create(settings_class=provider_class, 
                                                        namespace=settings_namespace, 
                                                        config_files=config_file_path, 
                                                        kwargs=kwargs)
        print(f"settings_parameters: {settings_parameters}")

        return settings_parameters



    @pytest.fixture
    def storage_auth(self, settings_parameters, provider_class, settings_namespace, config_file_path) -> S3StorageAuthSettings:
        """Create instance of storage auth class with config file settings"""

        settings_namespace  = f"{settings_namespace}.{time.time_ns()}"

        storage_auth: Any = get_settings(settings_parameters=settings_parameters, 
                                        settings_namespace=settings_namespace
                                        )
        
        print(storage_auth)
        return storage_auth
        # return self.provider_class(**base_config)


    ### Config File Tests ###
    def test_config_file_structure(self, base_config):
        """Verify the structure of the config file"""
        required_keys = {
            "PROVIDER_TYPE",
            "REGION",
            "BUCKET",
            "AUTH_METHOD"
        }
        assert all(key in base_config for key in required_keys)
        assert base_config["PROVIDER_TYPE"] == "s3"

    # def test_config_file_defaults(self, base_config):
    #     """Test default values from config file"""

    #     # Check security defaults
    #     assert base_config.get("USE_SSL", False)
    #     assert base_config.get("VERIFY_SSL", False)
        
    #     # Check transfer settings
    #     assert base_config.get("MAX_POOL_CONNECTIONS", 10) > 0
    #     assert base_config.get("MULTIPART_THRESHOLD", 8 * 1024 * 1024) >= 5 * 1024 * 1024
        
    #     # Check addressing style
    #     assert base_config.get("ADDRESSING_STYLE", "auto") in ["auto", "path", "virtual"]


    ### S3 Auth Tests ###

    # def test_region_validation(self, storage_auth: S3StorageAuthSettings):
    #     """Test S3-specific region validation"""
    #     region = storage_auth.REGION
    #     assert re.match(r'^[a-z]{2}-[a-z]+-\d{1}$', region)
        
    #     # Test invalid regions
    #     invalid_regions = ["invalid", "us_west_2", "EU-WEST-1"]
    #     for invalid_region in invalid_regions:
    #         with pytest.raises(StorageValidationError) as exc_info:
    #             storage_auth.REGION = invalid_region
    #         assert "Invalid AWS region format" in str(exc_info.value)

    # def test_bucket_validation(self, storage_auth: S3StorageAuthSettings):
    #     """Test S3-specific bucket name validation"""
    #     bucket = storage_auth.BUCKET
    #     assert 3 <= len(bucket) <= 63
    #     assert re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket)
        
    #     # Test invalid bucket names
    #     invalid_buckets = [
    #         "My-Bucket",  # uppercase not allowed
    #         "bucket!",    # invalid character
    #         "ab",        # too short
    #         "b" * 64,    # too long
    #         "-bucket",   # cannot start with hyphen
    #         "bucket-",   # cannot end with hyphen
    #         "192.168.1.1"  # IP address format not allowed
    #     ]
    #     for invalid_bucket in invalid_buckets:
    #         with pytest.raises(StorageValidationError) as exc_info:
    #             storage_auth.BUCKET = invalid_bucket
    #         assert "Invalid bucket name" in str(exc_info.value)

    def test_endpoint_configuration(self, storage_auth: S3StorageAuthSettings, base_config):
        """Test endpoint configuration from config file"""
        if "ENDPOINT_URL" in storage_auth:
            endpoint = storage_auth.ENDPOINT_URL
            assert endpoint.startswith(("http://", "https://"))
            assert len(endpoint.split(".")) >= 2

    # def test_security_configuration(self, storage_auth: S3StorageAuthSettings, base_config):
    #     """Test security settings from config file"""
    #     # Check SSL settings
    #     # assert storage_auth.USE_SSL == base_config.get("USE_SSL", True)
    #     # assert storage_auth.VERIFY_SSL == base_config.get("VERIFY_SSL", True)
        
    #     # Check if CA bundle is properly configured when specified
    #     if "CA_BUNDLE" in base_config:
    #         assert storage_auth.CA_BUNDLE == base_config["CA_BUNDLE"]

    # def test_transfer_settings(self, storage_auth: S3StorageAuthSettings, base_config):
    #     """Test transfer settings from config file"""
    #     # Check multipart settings
    #     threshold = int(base_config.get("MULTIPART_THRESHOLD", 8 * 1024 * 1024))
    #     assert threshold >= 5 * 1024 * 1024  # At least 5 MB
    #     assert storage_auth.MULTIPART_THRESHOLD == threshold
        
    #     chunksize = int(base_config.get("MULTIPART_CHUNKSIZE", 8 * 1024 * 1024))
    #     assert chunksize >= 5 * 1024 * 1024  # At least 5 MB
    #     assert storage_auth.MULTIPART_CHUNKSIZE == chunksize

    # def test_authentication_methods(self, base_config, provider_class):
    #     """Test different authentication methods from config"""
    #     # Test IAM role authentication
    #     iam_config = base_config.copy()
    #     iam_config.update({
    #         "AUTH_METHOD": CONST_STORAGE_AUTH_METHOD.IAM.value,
    #         "ROLE_ARN": "arn:aws:iam::123456789012:role/S3Access"
    #     })
    #     iam_auth = provider_class(**iam_config)
    #     assert iam_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.IAM
        
    #     # Test key authentication
    #     key_config = base_config.copy()
    #     key_config.update({
    #         "AUTH_METHOD": CONST_STORAGE_AUTH_METHOD.KEY.value,
    #         "ACCESS_KEY_ID": "test_key",
    #         "SECRET_ACCESS_KEY": "test_secret"
    #     })
    #     key_auth = provider_class(**key_config)
    #     assert key_auth.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY.value

    # def test_acceleration_settings(self, storage_auth: S3StorageAuthSettings, base_config):
    #     """Test S3 transfer acceleration settings"""
    #     accelerate = bool(base_config.get("ACCELERATE_ENDPOINT", False))
    #     assert storage_auth.ACCELERATE_ENDPOINT == accelerate
        
    #     if accelerate:
    #         assert not storage_auth.PATH_STYLE  # Cannot use path style with acceleration
    #         url = storage_auth.get_connection_url()
    #         assert "s3-accelerate" in url

    def test_connection_url_generation(self, storage_auth: S3StorageAuthSettings, base_config):
        """Test URL generation based on config settings"""
        url = storage_auth.get_connection_url()
        
        # Basic URL validation
        assert url.startswith("https://" if base_config.get("USE_SSL", True) else "http://")
        assert storage_auth.REGION in url
        
        # Check addressing style impact
        addressing_style = base_config.get("ADDRESSING_STYLE", "auto")
        if addressing_style == "path":
            assert f"/{storage_auth.BUCKET}" in url
        elif addressing_style == "virtual":
            assert f"{storage_auth.BUCKET}." in url

    def test_s3_connection_args(self, storage_auth: S3StorageAuthSettings, base_config):

        """Test connection arguments from config"""
        args = storage_auth.get_connection_args()
      
        print(f"test_s3_connection_args: {args}")

        # Check basic args
        assert args["region_name"] == base_config["REGION"]
        assert args["bucket"] == base_config["BUCKET"]
        
        # Check config section
        config = args.get("config", {}).get("s3", {})
        # assert config.get("addressing_style") == base_config.get("ADDRESSING_STYLE", "auto")
        # assert config.get("max_pool_connections") == base_config.get("MAX_POOL_CONNECTIONS", 10)

    # def test_permission_validation(self, storage_auth: S3StorageAuthSettings):
    #     """Test S3-specific permission validation"""
    #     permissions_map = {
    #         CONST_STORAGE_ACCESS_TYPE.READ_ONLY.value: {"s3:GetObject", "s3:ListBucket"},
    #         CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY.value: {"s3:PutObject", "s3:DeleteObject"},
    #         CONST_STORAGE_ACCESS_TYPE.READ_WRITE.value: {
    #             "s3:GetObject", "s3:ListBucket",
    #             "s3:PutObject", "s3:DeleteObject"
    #         },
    #         CONST_STORAGE_ACCESS_TYPE.ADMIN.value: {"s3:*"}
    #     }
        
    #     for access_type, required_perms in permissions_map.items():
    #         storage_auth.ACCESS_TYPE = access_type
    #         storage_auth.REQUIRED_PERMISSIONS = required_perms
    #         storage_auth._validate_permissions()

    # @pytest.mark.parametrize("encoding,expected", [
    #     ("utf-8", "utf-8"),
    #     ("ascii", "ascii"),
    #     ("latin1", "latin1")
    # ])
    # def test_encoding_settings(self, base_config, encoding, expected):
    #     """Test encoding settings configuration"""
    #     config = base_config.copy()
    #     config["ENCODING"] = encoding
    #     auth = self.provider_class(**config)
    #     assert auth.ENCODING == expected

    # def test_timeout_settings(self, storage_auth, base_config):

    #     """Test timeout settings from config"""
    #     timeout = float(base_config.get("CONNECT_TIMEOUT", 30.0))
    #     assert storage_auth.CONNECT_TIMEOUT == timeout
        
    #     read_timeout = float(base_config.get("READ_TIMEOUT", 60.0))
    #     assert storage_auth.READ_TIMEOUT == read_timeout


# import pytest
# from typing import Dict, Any

# from mountainash_settings.auth.storage.providers.cloud.s3 import S3StorageAuthSettings
# from mountainash_settings.auth.storage.constants import (
#     CONST_STORAGE_PROVIDER_TYPE,
#     CONST_STORAGE_AUTH_METHOD
# )
# from mountainash_settings.auth.storage.exceptions import StorageValidationError

# from test_storage_auth import BaseStorageAuthTests

# class TestS3StorageAuth(BaseStorageAuthTests):
#     """
#     Test cases for S3 storage authentication.
#     Inherits common test cases from BaseStorageAuthTests.
#     """
    
#     provider_class = S3StorageAuthSettings
#     provider_type = CONST_STORAGE_PROVIDER_TYPE.S3
    
#     # Override valid config for S3
#     valid_config: Dict[str, Any] = {
#         "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.S3,
#         "AUTH_METHOD": CONST_STORAGE_AUTH_METHOD.KEY,
#         "REGION": "us-west-2",
#         "BUCKET": "test-bucket",
#         "ACCESS_KEY_ID": "test-key",
#         "SECRET_ACCESS_KEY": "test-secret"
#     }

#     def test_region_validation(self, storage_auth):
#         """Test S3-specific region validation"""
#         # Valid regions
#         valid_regions = ["us-west-2", "eu-central-1", "ap-southeast-1"]
#         for region in valid_regions:
#             storage_auth.REGION = region
#             assert storage_auth.REGION == region
        
#         # Invalid regions
#         invalid_regions = ["invalid", "us_west_2", "EU-WEST-1"]
#         for region in invalid_regions:
#             with pytest.raises(StorageValidationError) as exc_info:
#                 storage_auth.REGION = region
#             assert "Invalid AWS region format" in str(exc_info.value)

#     def test_bucket_validation(self, storage_auth):
#         """Test S3-specific bucket name validation"""
#         # Valid bucket names
#         valid_buckets = ["my-bucket", "test-bucket-123", "my.bucket.name"]
#         for bucket in valid_buckets:
#             storage_auth.BUCKET = bucket
#             assert storage_auth.BUCKET == bucket
        
#         # Invalid bucket names
#         invalid_buckets = [
#             "My-Bucket",  # uppercase not allowed
#             "bucket!",    # invalid character
#             "ab",        # too short
#             "b" * 64,    # too long
#             "-bucket",   # cannot start with hyphen
#             "bucket-"    # cannot end with hyphen
#         ]
#         for bucket in invalid_buckets:
#             with pytest.raises(StorageValidationError) as exc_info:
#                 storage_auth.BUCKET = bucket
#             assert "Invalid bucket name" in str(exc_info.value)

#     def test_endpoint_validation(self, storage_auth):
#         """Test S3-specific endpoint validation"""
#         # Valid endpoints
#         valid_endpoints = [
#             "s3.amazonaws.com",
#             "s3.us-west-2.amazonaws.com",
#             "my-custom-endpoint.com"
#         ]
#         for endpoint in valid_endpoints:
#             storage_auth.ENDPOINT_URL = f"https://{endpoint}"
#             assert storage_auth.ENDPOINT_URL.startswith("https://")
        
#         # Invalid endpoints
#         invalid_endpoints = [
#             "not-a-url",
#             "ftp://s3.amazonaws.com",
#             "http://bucket.s3.amazonaws.com"  # path-style not allowed
#         ]
#         for endpoint in invalid_endpoints:
#             with pytest.raises(StorageValidationError) as exc_info:
#                 storage_auth.ENDPOINT_URL = endpoint
#             assert "Invalid endpoint" in str(exc_info.value)

#     def test_addressing_style(self, storage_auth):
#         """Test S3 addressing style configuration"""
#         # Valid styles
#         valid_styles = ["auto", "path", "virtual"]
#         for style in valid_styles:
#             storage_auth.ADDRESSING_STYLE = style
#             assert storage_auth.ADDRESSING_STYLE == style
        
#         # Invalid styles
#         with pytest.raises(StorageValidationError) as exc_info:
#             storage_auth.ADDRESSING_STYLE = "invalid"
#         assert "Invalid addressing style" in str(exc_info.value)

#     def test_s3_connection_url(self, storage_auth):
#         """Test S3-specific connection URL generation"""
#         url = storage_auth.get_connection_url()
        
#         # Basic URL validation
#         assert url.startswith("https://")
#         assert "amazonaws.com" in url
#         assert storage_auth.BUCKET in url
#         assert storage_auth.REGION in url

#     # def test_s3_connection_args(self, storage_auth):
#     #     """Test S3-specific connection arguments"""
#     #     args = storage_auth.get_connection_args()
        
#     #     # Check required S3 args
#     #     assert "region_name" in args
#     #     assert "bucket" in args
#     #     assert args["region_name"] == storage_auth.REGION
#     #     assert args["bucket"] == storage_auth.BUCKET
        
#         #