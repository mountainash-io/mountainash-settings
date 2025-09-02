#!/usr/bin/env python3
"""
Test file that validates decorator and subclass approaches produce identical behavior.

This test file creates identical settings classes using both approaches and verifies
they behave identically with the same SettingsParameters configurations.
"""

import pytest
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

from mountainash_settings import mountainash_settings, SettingsParameters, get_settings
from mountainash_settings.settings.base_settings import MountainAshBaseSettings


# Module-level classes for get_settings testing (needed for dynamic import)
@mountainash_settings(cache=True, templates=True)
class ModuleLevelDecoratorSettings(BaseSettings):
    service: str = Field(default="TestService")
    version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)


class ModuleLevelSubclassSettings(MountainAshBaseSettings):
    service: str = Field(default="TestService")
    version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)


# Dynamic resolution pattern classes
@mountainash_settings(cache=True, templates=True)
class DecoratorDatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="myapp")


class SubclassDatabaseSettings(MountainAshBaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="myapp")


@mountainash_settings(cache=True, templates=True)
class DecoratorRedisSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")


class SubclassRedisSettings(MountainAshBaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")


# Flow pattern classes
@mountainash_settings(cache=True, templates=True)
class DecoratorFlowSettings(BaseSettings):
    app_name: str = Field(default="TestApp")
    environment: str = Field(default="dev")


class SubclassFlowSettings(MountainAshBaseSettings):
    app_name: str = Field(default="TestApp")
    environment: str = Field(default="dev")


# API pattern classes
@mountainash_settings(cache=True, templates=True)
class DecoratorApiSettings(BaseSettings):
    base_url: str = Field(default="https://api.example.com")
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)


class SubclassApiSettings(MountainAshBaseSettings):
    base_url: str = Field(default="https://api.example.com")
    api_key: str = Field(default="dev-key")
    timeout: int = Field(default=30)


# Cache pattern classes
@mountainash_settings(cache=True, templates=True)
class DecoratorCacheSettings(BaseSettings):
    cache_key: str = Field(default="default_key")
    ttl: int = Field(default=3600)


class SubclassCacheSettings(MountainAshBaseSettings):
    cache_key: str = Field(default="default_key")
    ttl: int = Field(default=3600)


# File-based configuration classes
@mountainash_settings(cache=True, templates=True, multi_format=True)
class DecoratorDatabaseConfigSettings(BaseSettings):
    debug: bool = Field(default=True)
    environment: str = Field(default="dev")
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    database: str = Field(default="myapp")
    pool_size: int = Field(default=10)
    ssl_mode: str = Field(default="prefer")
    backup_enabled: bool = Field(default=False)
    monitoring_enabled: bool = Field(default=False)
    log_level: str = Field(default="DEBUG")


class SubclassDatabaseConfigSettings(MountainAshBaseSettings):
    debug: bool = Field(default=True)
    environment: str = Field(default="dev")
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    database: str = Field(default="myapp")
    pool_size: int = Field(default=10)
    ssl_mode: str = Field(default="prefer")
    backup_enabled: bool = Field(default=False)
    monitoring_enabled: bool = Field(default=False)
    log_level: str = Field(default="DEBUG")


@mountainash_settings(cache=True, templates=True, multi_format=True)
class DecoratorRedisConfigSettings(BaseSettings):
    debug: bool = Field(default=True)
    environment: str = Field(default="dev")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")
    db: int = Field(default=0)
    max_connections: int = Field(default=100)
    cluster_mode: bool = Field(default=False)
    cache_ttl: int = Field(default=1800)
    cache_prefix: str = Field(default="dev")
    monitoring_enabled: bool = Field(default=False)


class SubclassRedisConfigSettings(MountainAshBaseSettings):
    debug: bool = Field(default=True)
    environment: str = Field(default="dev")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    password: str = Field(default="")
    db: int = Field(default=0)
    max_connections: int = Field(default=100)
    cluster_mode: bool = Field(default=False)
    cache_ttl: int = Field(default=1800)
    cache_prefix: str = Field(default="dev")
    monitoring_enabled: bool = Field(default=False)


@mountainash_settings(cache=True, templates=True, multi_format=True)
class DecoratorMicroserviceSettings(BaseSettings):
    service_name: str = Field(default="default-service")
    environment: str = Field(default="dev")
    debug: bool = Field(default=True)
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    database: str = Field(default="myapp")
    pool_size: int = Field(default=10)
    secret_key: str = Field(default="dev-secret")
    algorithm: str = Field(default="HS256")
    expiry_minutes: int = Field(default=30)
    rate_limit: int = Field(default=50)
    timeout: int = Field(default=30)
    log_file: str = Field(default="/tmp/{service_name}_{environment}.log")
    config_path: str = Field(default="/tmp/{service_name}_config.yaml")


class SubclassMicroserviceSettings(MountainAshBaseSettings):
    service_name: str = Field(default="default-service")
    environment: str = Field(default="dev")
    debug: bool = Field(default=True)
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    username: str = Field(default="user")
    database: str = Field(default="myapp")
    pool_size: int = Field(default=10)
    secret_key: str = Field(default="dev-secret")
    algorithm: str = Field(default="HS256")
    expiry_minutes: int = Field(default=30)
    rate_limit: int = Field(default=50)
    timeout: int = Field(default=30)
    log_file: str = Field(default="/tmp/{service_name}_{environment}.log")
    config_path: str = Field(default="/tmp/{service_name}_config.yaml")


class TestDecoratorVsSubclassParity:
    """Test suite comparing decorator and subclass approaches for identical behavior."""
    
    def test_basic_settings_parity(self):
        """Test that basic settings creation produces identical results."""
        
        # Define decorator-based class
        @mountainash_settings(cache=False, templates=True, multi_format=True)
        class DecoratorSettings(BaseSettings):
            app_name: str = Field(default="TestApp")
            debug: bool = Field(default=False)
            port: int = Field(default=8000)
            timeout: float = Field(default=30.0)
        
        # Define subclass-based class
        class SubclassSettings(MountainAshBaseSettings):
            app_name: str = Field(default="TestApp")
            debug: bool = Field(default=False)
            port: int = Field(default=8000)
            timeout: float = Field(default=30.0)
        
        # Create identical SettingsParameters (different instances)
        decorator_params = SettingsParameters.create(
            namespace="test_basic",
            settings_class=DecoratorSettings,
            env_prefix="TEST",
            app_name="ParityApp",
            debug=True,
            port=9000
        )
        
        subclass_params = SettingsParameters.create(
            namespace="test_basic", 
            settings_class=SubclassSettings,
            env_prefix="TEST",
            app_name="ParityApp",
            debug=True,
            port=9000
        )
        
        # Create settings instances
        decorator_settings = DecoratorSettings(settings_parameters=decorator_params)
        subclass_settings = SubclassSettings(settings_parameters=subclass_params)
        
        # Verify identical behavior
        assert decorator_settings.app_name == subclass_settings.app_name == "ParityApp"
        assert decorator_settings.debug == subclass_settings.debug == True
        assert decorator_settings.port == subclass_settings.port == 9000
        assert decorator_settings.timeout == subclass_settings.timeout == 30.0
        
        # Verify metadata tracking
        assert decorator_settings.SETTINGS_NAMESPACE == subclass_settings.SETTINGS_NAMESPACE == "test_basic"
        assert decorator_settings.SETTINGS_CLASS_NAME == "DecoratorSettings"
        assert subclass_settings.SETTINGS_CLASS_NAME == "SubclassSettings"
        assert decorator_settings.SETTINGS_SOURCE_ENV_PREFIX == subclass_settings.SETTINGS_SOURCE_ENV_PREFIX == "TEST"
    
    def test_namespace_handling_parity(self):
        """Test that namespace handling works correctly for both approaches."""
        
        # Test with decorator that has no default namespace (should behave like subclass)
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            service_name: str = Field(default="Service")
        
        class SubclassSettings(MountainAshBaseSettings):
            service_name: str = Field(default="Service")
        
        # Test 1: No namespace provided (both should use None)
        decorator_settings_1 = DecoratorSettings()
        subclass_settings_1 = SubclassSettings()
        
        # Both should use None when no namespace is provided
        assert decorator_settings_1.SETTINGS_NAMESPACE is None
        assert subclass_settings_1.SETTINGS_NAMESPACE is None
        
        # Test 2: Explicit namespace provided via SettingsParameters
        decorator_params = SettingsParameters.create(
            namespace="explicit_namespace",
            settings_class=DecoratorSettings,
            service_name="ExplicitService"
        )
        
        subclass_params = SettingsParameters.create(
            namespace="explicit_namespace",
            settings_class=SubclassSettings,
            service_name="ExplicitService"
        )
        
        decorator_settings_2 = DecoratorSettings(settings_parameters=decorator_params)
        subclass_settings_2 = SubclassSettings(settings_parameters=subclass_params)
        
        # Both should use the explicit namespace
        assert decorator_settings_2.SETTINGS_NAMESPACE == subclass_settings_2.SETTINGS_NAMESPACE == "explicit_namespace"
        assert decorator_settings_2.service_name == subclass_settings_2.service_name == "ExplicitService"
        
        # Test 3: None namespace explicitly provided
        decorator_settings_3 = DecoratorSettings(namespace=None)
        subclass_settings_3 = SubclassSettings(namespace=None)
        
        # Both should handle None namespace identically
        assert decorator_settings_3.SETTINGS_NAMESPACE == subclass_settings_3.SETTINGS_NAMESPACE is None
    
    def test_template_methods_parity(self):
        """Test that template methods work identically between approaches."""
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            app_name: str = Field(default="MyApp")
            log_file: str = Field(default="logs/{app_name}.log")
            config_path: str = Field(default="config/{app_name}/settings.yaml")
        
        class SubclassSettings(MountainAshBaseSettings):
            app_name: str = Field(default="MyApp")
            log_file: str = Field(default="logs/{app_name}.log")
            config_path: str = Field(default="config/{app_name}/settings.yaml")
        
        # Create with identical parameters
        decorator_params = SettingsParameters.create(
            namespace="template_test",
            settings_class=DecoratorSettings,
            app_name="TemplateApp"
        )
        
        subclass_params = SettingsParameters.create(
            namespace="template_test",
            settings_class=SubclassSettings,
            app_name="TemplateApp"
        )
        
        decorator_settings = DecoratorSettings(settings_parameters=decorator_params)
        subclass_settings = SubclassSettings(settings_parameters=subclass_params)
        
        # Test template methods exist and work identically
        assert hasattr(decorator_settings, 'format_template_from_settings')
        assert hasattr(subclass_settings, 'format_template_from_settings')
        
        # Test template formatting
        decorator_log = decorator_settings.format_template_from_settings("logs/{app_name}_debug.log")
        subclass_log = subclass_settings.format_template_from_settings("logs/{app_name}_debug.log")
        
        assert decorator_log == subclass_log == "logs/TemplateApp_debug.log"
        
        # Test init_setting_from_template method
        assert hasattr(decorator_settings, 'init_setting_from_template')
        assert hasattr(subclass_settings, 'init_setting_from_template')
        
        decorator_init = decorator_settings.init_setting_from_template("data/{app_name}/input.csv")
        subclass_init = subclass_settings.init_setting_from_template("data/{app_name}/input.csv")
        
        assert decorator_init == subclass_init == "data/TemplateApp/input.csv"
    
    def test_parameter_extraction_parity(self):
        """Test that parameter extraction works identically between approaches."""
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            database_url: str = Field(default="sqlite:///app.db")
            redis_url: str = Field(default="redis://localhost:6379")
            secret_key: str = Field(default="default-secret")
        
        class SubclassSettings(MountainAshBaseSettings):
            database_url: str = Field(default="sqlite:///app.db")
            redis_url: str = Field(default="redis://localhost:6379")
            secret_key: str = Field(default="default-secret")
        
        # Create with identical parameters
        decorator_params = SettingsParameters.create(
            namespace="extraction_test",
            settings_class=DecoratorSettings,
            env_prefix="EXTRACT",
            database_url="postgresql://localhost/test",
            redis_url="redis://cache:6379",
            secret_key="test-secret-key"
        )
        
        subclass_params = SettingsParameters.create(
            namespace="extraction_test",
            settings_class=SubclassSettings,
            env_prefix="EXTRACT",
            database_url="postgresql://localhost/test",
            redis_url="redis://cache:6379",
            secret_key="test-secret-key"
        )
        
        decorator_settings = DecoratorSettings(settings_parameters=decorator_params)
        subclass_settings = SubclassSettings(settings_parameters=subclass_params)
        
        # Extract parameters from both
        decorator_extracted = decorator_settings.extract_settings_parameters()
        subclass_extracted = subclass_settings.extract_settings_parameters()
        
        # Verify extracted parameters are identical (except for settings_class)
        assert decorator_extracted.namespace == subclass_extracted.namespace == "extraction_test"
        assert decorator_extracted.env_prefix == subclass_extracted.env_prefix == "EXTRACT"
        assert decorator_extracted.kwargs == subclass_extracted.kwargs
        
        # Settings classes should be different but names should match original
        assert decorator_extracted.settings_class == DecoratorSettings
        assert subclass_extracted.settings_class == SubclassSettings
    
    def test_update_settings_from_dict_parity(self):
        """Test that settings dictionary updates work identically."""
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=8000)
            workers: int = Field(default=1)
        
        class SubclassSettings(MountainAshBaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=8000)
            workers: int = Field(default=1)
        
        decorator_settings = DecoratorSettings()
        subclass_settings = SubclassSettings()
        
        # Test updating with dictionary
        update_dict = {
            "host": "0.0.0.0",
            "port": 9000,
            "workers": 4
        }
        
        decorator_settings.update_settings_from_dict(update_dict)
        subclass_settings.update_settings_from_dict(update_dict)
        
        # Verify identical updates
        assert decorator_settings.host == subclass_settings.host == "0.0.0.0"
        assert decorator_settings.port == subclass_settings.port == 9000
        assert decorator_settings.workers == subclass_settings.workers == 4
        
        # Verify SETTINGS_SOURCE_KWARGS is set identically
        assert decorator_settings.SETTINGS_SOURCE_KWARGS == subclass_settings.SETTINGS_SOURCE_KWARGS == update_dict
    
    def test_post_init_behavior_parity(self):
        """Test that post_init behavior is identical between approaches."""
        
        post_init_calls = {"decorator": 0, "subclass": 0}
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            app_name: str = Field(default="TestApp")
            
            def post_init(self, reinitialise: bool = False):
                post_init_calls["decorator"] += 1
        
        class SubclassSettings(MountainAshBaseSettings):
            app_name: str = Field(default="TestApp")
            
            def post_init(self, reinitialise: bool = False):
                post_init_calls["subclass"] += 1
                super().post_init(reinitialise)
        
        # Create instances - post_init should be called automatically
        decorator_settings = DecoratorSettings()
        subclass_settings = SubclassSettings()
        
        # Both should have called post_init once during initialization
        assert post_init_calls["decorator"] == 1
        assert post_init_calls["subclass"] == 1
        
        # Test manual post_init calls
        decorator_settings.post_init()
        subclass_settings.post_init()
        
        assert post_init_calls["decorator"] == 2
        assert post_init_calls["subclass"] == 2
    
    def test_multi_format_configuration_parity(self):
        """Test that multi-format configuration support is identical."""
        
        @mountainash_settings(cache=False, templates=False, multi_format=True)
        class DecoratorSettings(BaseSettings):
            database_host: str = Field(default="localhost")
            database_port: int = Field(default=5432)
            api_key: str = Field(default="default-key")
        
        class SubclassSettings(MountainAshBaseSettings):
            database_host: str = Field(default="localhost")
            database_port: int = Field(default=5432)
            api_key: str = Field(default="default-key")
        
        # Both should have custom settings sources
        assert hasattr(DecoratorSettings, 'settings_customise_sources')
        assert hasattr(SubclassSettings, 'settings_customise_sources')
        
        # Create instances
        decorator_settings = DecoratorSettings()
        subclass_settings = SubclassSettings()
        
        # Verify default values are identical
        assert decorator_settings.database_host == subclass_settings.database_host == "localhost"
        assert decorator_settings.database_port == subclass_settings.database_port == 5432
        assert decorator_settings.api_key == subclass_settings.api_key == "default-key"
    
    def test_get_settings_classmethod_parity(self):
        """Test that get_settings classmethod behaves identically."""
        
        # Use module-level classes to avoid import issues
        # Test get_settings with kwargs
        decorator_settings = ModuleLevelDecoratorSettings.get_settings(
            settings_namespace="classmethod_test",
            service="ClassmethodService",
            version="2.0.0",
            debug=True
        )
        
        subclass_settings = ModuleLevelSubclassSettings.get_settings(
            settings_namespace="classmethod_test",
            service="ClassmethodService", 
            version="2.0.0",
            debug=True
        )
        
        # Verify identical results
        assert decorator_settings.service == subclass_settings.service == "ClassmethodService"
        assert decorator_settings.version == subclass_settings.version == "2.0.0"
        assert decorator_settings.debug == subclass_settings.debug == True
        assert decorator_settings.SETTINGS_NAMESPACE == subclass_settings.SETTINGS_NAMESPACE == "classmethod_test"
        
        # Test get_settings with SettingsParameters
        decorator_params = SettingsParameters.create(
            namespace="params_test",
            settings_class=ModuleLevelDecoratorSettings,
            service="ParamsService",
            version="3.0.0"
        )
        
        subclass_params = SettingsParameters.create(
            namespace="params_test",
            settings_class=ModuleLevelSubclassSettings,
            service="ParamsService",
            version="3.0.0"
        )
        
        decorator_settings_2 = ModuleLevelDecoratorSettings.get_settings(settings_parameters=decorator_params)
        subclass_settings_2 = ModuleLevelSubclassSettings.get_settings(settings_parameters=subclass_params)
        
        assert decorator_settings_2.service == subclass_settings_2.service == "ParamsService"
        assert decorator_settings_2.version == subclass_settings_2.version == "3.0.0"
        assert decorator_settings_2.SETTINGS_NAMESPACE == subclass_settings_2.SETTINGS_NAMESPACE == "params_test"
    
    def test_runtime_override_parity(self):
        """Test that runtime parameter overrides work identically."""
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=8000)
            ssl_enabled: bool = Field(default=False)
        
        class SubclassSettings(MountainAshBaseSettings):
            host: str = Field(default="localhost")  
            port: int = Field(default=8000)
            ssl_enabled: bool = Field(default=False)
        
        # Create base parameters
        decorator_params = SettingsParameters.create(
            namespace="override_test",
            settings_class=DecoratorSettings,
            host="prod-server",
            port=8080
        )
        
        subclass_params = SettingsParameters.create(
            namespace="override_test",
            settings_class=SubclassSettings,
            host="prod-server", 
            port=8080
        )
        
        # Create settings with runtime overrides
        decorator_settings = DecoratorSettings(
            settings_parameters=decorator_params,
            port=9000,  # Override port
            ssl_enabled=True  # Override ssl_enabled
        )
        
        subclass_settings = SubclassSettings(
            settings_parameters=subclass_params,
            port=9000,  # Override port  
            ssl_enabled=True  # Override ssl_enabled
        )
        
        # Verify runtime overrides work identically
        assert decorator_settings.host == subclass_settings.host == "prod-server"  # From params
        assert decorator_settings.port == subclass_settings.port == 9000  # Runtime override
        assert decorator_settings.ssl_enabled == subclass_settings.ssl_enabled == True  # Runtime override
        
        # Verify metadata is identical
        assert decorator_settings.SETTINGS_NAMESPACE == subclass_settings.SETTINGS_NAMESPACE == "override_test"
    
    def test_feature_flag_combinations_parity(self):
        """Test that different feature flag combinations work identically."""
        
        # Test all combinations of feature flags
        feature_combinations = [
            {"cache": True, "templates": True, "multi_format": True},
            {"cache": True, "templates": True, "multi_format": False},
            {"cache": True, "templates": False, "multi_format": True},
            {"cache": True, "templates": False, "multi_format": False},
            {"cache": False, "templates": True, "multi_format": True},
            {"cache": False, "templates": True, "multi_format": False},
            {"cache": False, "templates": False, "multi_format": True},
            {"cache": False, "templates": False, "multi_format": False},
        ]
        
        for i, flags in enumerate(feature_combinations):
            # Create decorator class with these flags
            @mountainash_settings(**flags)
            class DecoratorSettings(BaseSettings):
                test_field: str = Field(default=f"test_{i}")
                value: int = Field(default=i)
            
            # Subclass always has all features enabled
            class SubclassSettings(MountainAshBaseSettings):
                test_field: str = Field(default=f"test_{i}")
                value: int = Field(default=i)
            
            # Create instances
            decorator_settings = DecoratorSettings()
            subclass_settings = SubclassSettings()
            
            # Basic functionality should always work
            assert decorator_settings.test_field == subclass_settings.test_field == f"test_{i}"
            assert decorator_settings.value == subclass_settings.value == i
            
            # Check feature flags are set correctly on decorator
            assert DecoratorSettings._mountainash_cache_enabled == flags["cache"]
            assert DecoratorSettings._mountainash_templates_enabled == flags["templates"]
            assert DecoratorSettings._mountainash_multi_format_enabled == flags["multi_format"]
            
            # Template methods should exist only when templates=True
            if flags["templates"]:
                assert hasattr(decorator_settings, 'format_template_from_settings')
                assert hasattr(decorator_settings, 'SETTINGS_NAMESPACE')
            
            # Multi-format should exist only when multi_format=True
            if flags["multi_format"]:
                assert hasattr(DecoratorSettings, 'settings_customise_sources')
            
            # Subclass always has all methods
            assert hasattr(subclass_settings, 'format_template_from_settings')
            assert hasattr(subclass_settings, 'SETTINGS_NAMESPACE')
            assert hasattr(SubclassSettings, 'settings_customise_sources')


    def test_smart_merging_pattern_parity(self):
        """Test that smart SettingsParameters merging works identically for both approaches."""
        
        @mountainash_settings(cache=False, templates=True)
        class DecoratorSettings(BaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=5432)
            database: str = Field(default="myapp")
            timeout: int = Field(default=30)
        
        class SubclassSettings(MountainAshBaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=5432)
            database: str = Field(default="myapp")
            timeout: int = Field(default=30)
        
        # Test smart merging - no settings_class needed for decorator
        decorator_params = SettingsParameters.create(
            namespace="smart_merging_test",
            # settings_class intentionally omitted for decorator
            host="prod-db.example.com",
            port=5433,
            database="production_db",
            timeout=60
        )
        
        # Subclass needs explicit settings_class
        subclass_params = SettingsParameters.create(
            namespace="smart_merging_test",
            settings_class=SubclassSettings,
            host="prod-db.example.com",
            port=5433,
            database="production_db", 
            timeout=60
        )
        
        # Both should work and produce identical results
        decorator_settings = DecoratorSettings(settings_parameters=decorator_params)
        subclass_settings = SubclassSettings(settings_parameters=subclass_params)
        
        # Verify identical behavior
        assert decorator_settings.host == subclass_settings.host == "prod-db.example.com"
        assert decorator_settings.port == subclass_settings.port == 5433
        assert decorator_settings.database == subclass_settings.database == "production_db"
        assert decorator_settings.timeout == subclass_settings.timeout == 60
        assert decorator_settings.SETTINGS_NAMESPACE == subclass_settings.SETTINGS_NAMESPACE == "smart_merging_test"
        
        # Verify final SettingsParameters are equivalent
        decorator_extracted = decorator_settings.extract_settings_parameters()
        subclass_extracted = subclass_settings.extract_settings_parameters()
        
        assert decorator_extracted.namespace == subclass_extracted.namespace
        assert decorator_extracted.kwargs == subclass_extracted.kwargs
        assert decorator_extracted.settings_class == DecoratorSettings
        assert subclass_extracted.settings_class == SubclassSettings
    
    def test_dynamic_resolution_pattern_parity(self):
        """Test that dynamic settings class resolution works identically for both approaches."""
        
        # Use module-level classes for get_settings compatibility
        # Create SettingsParameters with embedded class information
        decorator_db_params = SettingsParameters.create(
            namespace="dynamic_db_test",
            settings_class=DecoratorDatabaseSettings,
            host="prod-db.example.com",
            port=5432,
            database="production"
        )
        
        decorator_redis_params = SettingsParameters.create(
            namespace="dynamic_redis_test",
            settings_class=DecoratorRedisSettings,
            host="redis.example.com",
            port=6379,
            password="secret"
        )
        
        subclass_db_params = SettingsParameters.create(
            namespace="dynamic_db_test", 
            settings_class=SubclassDatabaseSettings,
            host="prod-db.example.com",
            port=5432,
            database="production"
        )
        
        subclass_redis_params = SettingsParameters.create(
            namespace="dynamic_redis_test",
            settings_class=SubclassRedisSettings,
            host="redis.example.com",
            port=6379,
            password="secret"
        )
        
        # Test dynamic resolution using get_settings - should work identically
        decorator_db = get_settings(settings_parameters=decorator_db_params)
        decorator_redis = get_settings(settings_parameters=decorator_redis_params)
        subclass_db = get_settings(settings_parameters=subclass_db_params)
        subclass_redis = get_settings(settings_parameters=subclass_redis_params)
        
        # Verify correct types were resolved
        assert isinstance(decorator_db, DecoratorDatabaseSettings)
        assert isinstance(decorator_redis, DecoratorRedisSettings)
        assert isinstance(subclass_db, SubclassDatabaseSettings)
        assert isinstance(subclass_redis, SubclassRedisSettings)
        
        # Verify identical field values
        assert decorator_db.host == subclass_db.host == "prod-db.example.com"
        assert decorator_db.database == subclass_db.database == "production"
        assert decorator_redis.host == subclass_redis.host == "redis.example.com"
        assert decorator_redis.password == subclass_redis.password == "secret"
        
        # Verify namespace preservation
        assert decorator_db.SETTINGS_NAMESPACE == subclass_db.SETTINGS_NAMESPACE == "dynamic_db_test"
        assert decorator_redis.SETTINGS_NAMESPACE == subclass_redis.SETTINGS_NAMESPACE == "dynamic_redis_test"
    
    def test_generic_resolver_pattern_parity(self):
        """Test that generic settings resolvers work identically for both approaches."""
        
        # Use module-level classes for get_settings compatibility
        # Generic resolver function that works with any settings type
        def resolve_service_settings(service_configs: dict, service_name: str) -> BaseSettings:
            """Generic resolver - doesn't know what settings class it will get!"""
            if service_name not in service_configs:
                raise ValueError(f"Unknown service: {service_name}")
            
            params = service_configs[service_name]
            return get_settings(settings_parameters=params)
        
        # Service registries for both decorator and subclass approaches
        decorator_configs = {
            "api": SettingsParameters.create(
                namespace="generic_api_test",
                settings_class=DecoratorApiSettings,
                base_url="https://api.production.com",
                api_key="prod-key-123",
                timeout=60
            )
        }
        
        subclass_configs = {
            "api": SettingsParameters.create(
                namespace="generic_api_test",
                settings_class=SubclassApiSettings, 
                base_url="https://api.production.com",
                api_key="prod-key-123",
                timeout=60
            )
        }
        
        # Generic resolution should work identically
        decorator_api = resolve_service_settings(decorator_configs, "api")
        subclass_api = resolve_service_settings(subclass_configs, "api")
        
        # Verify correct types and identical behavior
        assert isinstance(decorator_api, DecoratorApiSettings)
        assert isinstance(subclass_api, SubclassApiSettings)
        assert decorator_api.base_url == subclass_api.base_url == "https://api.production.com"
        assert decorator_api.api_key == subclass_api.api_key == "prod-key-123"
        assert decorator_api.timeout == subclass_api.timeout == 60
        assert decorator_api.SETTINGS_NAMESPACE == subclass_api.SETTINGS_NAMESPACE == "generic_api_test"
    
    def test_caching_behavior_across_patterns_parity(self):
        """Test that caching works consistently across both patterns and approaches."""
        
        # Use module-level classes for get_settings compatibility
        # Test smart merging caching (decorator only)
        smart_params = SettingsParameters.create(
            namespace="cache_test",
            cache_key="production_key",
            ttl=7200
        )
        
        # Multiple instantiations should use cache when applicable
        dec_smart_1 = DecoratorCacheSettings(settings_parameters=smart_params)
        dec_smart_2 = DecoratorCacheSettings(settings_parameters=smart_params)
        
        # Test dynamic resolution caching (both approaches)
        decorator_params = SettingsParameters.create(
            namespace="cache_test",
            settings_class=DecoratorCacheSettings,
            cache_key="production_key", 
            ttl=7200
        )
        
        subclass_params = SettingsParameters.create(
            namespace="cache_test",
            settings_class=SubclassCacheSettings,
            cache_key="production_key",
            ttl=7200
        )
        
        # Dynamic resolution should cache consistently
        dec_dynamic_1 = get_settings(settings_parameters=decorator_params)
        dec_dynamic_2 = get_settings(settings_parameters=decorator_params)
        sub_dynamic_1 = get_settings(settings_parameters=subclass_params)
        sub_dynamic_2 = get_settings(settings_parameters=subclass_params)
        
        # Verify caching behavior
        # Note: Cache behavior may vary based on implementation details
        # The key is that both approaches behave consistently
        
        # Dynamic resolution should definitely cache
        assert dec_dynamic_1 is dec_dynamic_2  # Same decorator instance
        assert sub_dynamic_1 is sub_dynamic_2  # Same subclass instance
        
        # Different approaches should create different instances
        assert dec_dynamic_1 is not sub_dynamic_1  # Different classes
        
        # Verify all instances have correct values regardless of caching
        all_settings = [dec_smart_1, dec_smart_2, dec_dynamic_1, dec_dynamic_2, sub_dynamic_1, sub_dynamic_2]
        for settings in all_settings:
            assert settings.cache_key == "production_key"
            assert settings.ttl == 7200
            assert settings.SETTINGS_NAMESPACE == "cache_test"
    
    def test_parameter_flow_pattern_parity(self):
        """Test that SettingsParameters flow through application layers identically."""
        
        # Use module-level classes for get_settings compatibility  
        # Simulate application layers passing parameters around
        def create_service_config(service_name: str, env: str, use_decorator: bool):
            """Factory function that creates configuration."""
            target_class = DecoratorFlowSettings if use_decorator else SubclassFlowSettings
            
            return SettingsParameters.create(
                namespace=f"{service_name}_{env}",
                settings_class=target_class,
                app_name=service_name,
                environment=env
            )
        
        def business_logic_layer(params: SettingsParameters):
            """Business logic that processes settings parameters."""
            # Extract metadata from parameters
            metadata = {
                "namespace": params.namespace,
                "app_name": params.kwargs.get("app_name"),
                "environment": params.kwargs.get("environment"),
                "target_class": params.settings_class.__name__
            }
            return metadata, get_settings(settings_parameters=params)
        
        # Test parameter flow for both approaches
        decorator_params = create_service_config("user_service", "production", use_decorator=True)
        subclass_params = create_service_config("user_service", "production", use_decorator=False)
        
        # Flow through business logic
        dec_metadata, dec_settings = business_logic_layer(decorator_params)
        sub_metadata, sub_settings = business_logic_layer(subclass_params)
        
        # Verify identical parameter flow
        assert dec_metadata["namespace"] == sub_metadata["namespace"] == "user_service_production"
        assert dec_metadata["app_name"] == sub_metadata["app_name"] == "user_service"
        assert dec_metadata["environment"] == sub_metadata["environment"] == "production"
        
        # Verify settings resolution
        assert dec_settings.app_name == sub_settings.app_name == "user_service"
        assert dec_settings.environment == sub_settings.environment == "production"
        assert dec_settings.SETTINGS_NAMESPACE == sub_settings.SETTINGS_NAMESPACE == "user_service_production"
        
        # Verify identical types were resolved
        assert isinstance(dec_settings, DecoratorFlowSettings)
        assert isinstance(sub_settings, SubclassFlowSettings)
    
    def test_file_based_smart_merging_pattern_parity(self):
        """Test smart merging pattern with configuration files loaded from disk."""
        import os
        
        test_config_dir = os.path.join(os.path.dirname(__file__), "config")
        
        # Test smart merging - no settings_class needed!
        decorator_params = SettingsParameters.create(
            namespace="file_smart_test",
            config_files=[
                os.path.join(test_config_dir, "simple_base.yaml"),
                os.path.join(test_config_dir, "simple_production.yaml")
            ],
            # No settings_class - decorator will handle it automatically!
            port=9999  # Runtime override
        )
        
        # Traditional approach with settings_class 
        subclass_params = SettingsParameters.create(
            namespace="file_smart_test",
            settings_class=SubclassDatabaseSettings,
            config_files=[
                os.path.join(test_config_dir, "simple_base.yaml"),
                os.path.join(test_config_dir, "simple_production.yaml")
            ],
            port=9999  # Same runtime override
        )
        
        # Smart merging: Direct instantiation
        dec_settings = DecoratorDatabaseSettings(settings_parameters=decorator_params)
        sub_settings = SubclassDatabaseSettings(settings_parameters=subclass_params)
        
        # Verify both loaded from files identically
        assert dec_settings.host == sub_settings.host == "prod-db.example.com"  # From production file
        assert dec_settings.database == sub_settings.database == "production_db"  # From production file
        
        # Verify runtime override applied
        assert dec_settings.port == sub_settings.port == 9999
        
        # Verify namespace and file tracking
        assert dec_settings.SETTINGS_NAMESPACE == sub_settings.SETTINGS_NAMESPACE == "file_smart_test"
        assert len(dec_settings.SETTINGS_SOURCE_YAML_FILES) == 2
    
    def test_file_based_dynamic_resolution_pattern_parity(self):
        """Test dynamic resolution pattern with configuration files."""
        import os
        
        test_config_dir = os.path.join(os.path.dirname(__file__), "config")
        
        # Service registry with file-based configurations
        decorator_registry = {
            "database": SettingsParameters.create(
                namespace="file_dynamic_db",
                settings_class=DecoratorDatabaseSettings,
                config_files=[os.path.join(test_config_dir, "simple_production.yaml")],
                host="runtime-override.example.com"  # Runtime override
            )
        }
        
        subclass_registry = {
            "database": SettingsParameters.create(
                namespace="file_dynamic_db",
                settings_class=SubclassDatabaseSettings,
                config_files=[os.path.join(test_config_dir, "simple_production.yaml")],
                host="runtime-override.example.com"  # Same override
            )
        }
        
        # Generic resolver function
        def resolve_config(service: str, registry: dict):
            return get_settings(settings_parameters=registry[service])
        
        # Dynamic resolution
        dec_db = resolve_config("database", decorator_registry)
        sub_db = resolve_config("database", subclass_registry)
        
        # Verify correct types resolved
        assert isinstance(dec_db, DecoratorDatabaseSettings)
        assert isinstance(sub_db, SubclassDatabaseSettings)
        
        # Verify file config loaded
        assert dec_db.database == sub_db.database == "production_db"     # From file
        
        # Verify runtime override applied  
        assert dec_db.host == sub_db.host == "runtime-override.example.com"
        
        # Verify namespace
        assert dec_db.SETTINGS_NAMESPACE == sub_db.SETTINGS_NAMESPACE == "file_dynamic_db"
    
    def test_env_prefix_parameter_functionality(self):
        """Test that env_prefix parameter is correctly set and tracked."""
        import uuid
        
        # Use unique namespace to avoid cache contamination
        unique_namespace = f"env_prefix_test_{uuid.uuid4().hex[:8]}"
        
        # Load configurations with cache disabled to avoid contamination
        @mountainash_settings(cache=False)  # Disable cache for this test
        class TestDecoratorDatabaseSettings(BaseSettings):
            host: str = Field(default="localhost")
            port: int = Field(default=5432)
            database: str = Field(default="myapp")
        
        class TestSubclassDatabaseSettings(MountainAshBaseSettings):
            host: str = Field(default="localhost") 
            port: int = Field(default=5432)
            database: str = Field(default="myapp")
        
        # Simple test to verify env_prefix parameter functionality
        decorator_params = SettingsParameters.create(
            namespace=unique_namespace,
            env_prefix="TEST"  # Just verify the parameter is accepted and tracked
        )
        
        subclass_params = SettingsParameters.create(
            namespace=unique_namespace,
            settings_class=TestSubclassDatabaseSettings,  # Use the local test class
            env_prefix="TEST"
        )
        
        dec_settings = TestDecoratorDatabaseSettings(settings_parameters=decorator_params)
        sub_settings = TestSubclassDatabaseSettings(settings_parameters=subclass_params)
        
        # Verify env_prefix is tracked correctly
        assert dec_settings.SETTINGS_SOURCE_ENV_PREFIX == sub_settings.SETTINGS_SOURCE_ENV_PREFIX == "TEST"
        
        # Both should use defaults since no config files provided
        assert dec_settings.host == sub_settings.host == "localhost"
        assert dec_settings.port == sub_settings.port == 5432
        assert dec_settings.database == sub_settings.database == "myapp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])