#factory.py

from typing import Optional, Union, List, Type, Dict, Any, Set
from upath import UPath

from mountainash_settings import prepare_settings_parameters, get_settings
from mountainash_settings.auth.storage.base import StorageAuthBase
from mountainash_settings.auth.storage.constants import (
    CONST_STORAGE_PROVIDER_TYPE,
    CONST_STORAGE_AUTH_METHOD
)
from mountainash_settings.auth.storage.exceptions import (
    StorageConfigError,
    StorageValidationError,
    StorageAuthError
)

class StorageAuthFactory:
    """Factory for creating storage authentication settings"""
    
    _provider_registry: Dict[str, Type[StorageAuthBase]] = {}
    _instances: Dict[str, StorageAuthBase] = {}
    
    @classmethod
    def register_provider(cls, provider_type: str, provider_class: Type[StorageAuthBase]) -> None:
        """
        Register a storage provider
        
        Args:
            provider_type: The type identifier for the provider
            provider_class: The provider class implementation
            
        Raises:
            TypeError: If provider_class doesn't inherit from StorageAuthBase
            ValueError: If provider_type is already registered
        """
        if not issubclass(provider_class, StorageAuthBase):
            raise TypeError(f"Provider class must inherit from StorageAuthBase: {provider_class}")
            
        if provider_type in cls._provider_registry:
            raise ValueError(f"Provider type already registered: {provider_type}")
            
        cls._provider_registry[provider_type] = provider_class
    
    @classmethod
    def unregister_provider(cls, provider_type: str) -> None:
        """
        Unregister a storage provider
        
        Args:
            provider_type: The type identifier to unregister
            
        Raises:
            KeyError: If provider_type is not registered
        """
        if provider_type not in cls._provider_registry:
            raise KeyError(f"Provider type not registered: {provider_type}")
            
        del cls._provider_registry[provider_type]
        
        # Clean up any instances of this provider
        instance_keys = [
            key for key in cls._instances.keys() 
            if key.startswith(f"{provider_type}:")
        ]
        for key in instance_keys:
            del cls._instances[key]
    
    @classmethod
    def get_provider_class(cls, provider_type: str) -> Type[StorageAuthBase]:
        """
        Get the provider class for a given type
        
        Args:
            provider_type: The type identifier
            
        Returns:
            The provider class
            
        Raises:
            StorageConfigError: If provider type is unknown or not registered
        """
        if provider_type not in CONST_STORAGE_PROVIDER_TYPE.__dict__:
            raise StorageConfigError(
                f"Unknown provider type: {provider_type}",
                provider=provider_type
            )
        
        provider_class = cls._provider_registry.get(provider_type)
        if not provider_class:
            raise StorageConfigError(
                f"No provider registered for type: {provider_type}",
                provider=provider_type
            )
            
        return provider_class
    
    @classmethod
    def create_auth_settings(
        cls,
        provider_type: str,
        settings_namespace: str,
        config_files: Optional[Union[UPath, str, List[UPath|str]]] = None,
        reuse_existing: bool = True,
        validate: bool = True,
        **kwargs
    ) -> StorageAuthBase:
        """
        Create appropriate auth settings instance
        
        Args:
            provider_type: The type of storage provider
            settings_namespace: Namespace for the settings
            config_files: Optional configuration files
            reuse_existing: Whether to reuse existing instances
            validate: Whether to validate the settings after creation
            **kwargs: Additional settings parameters
            
        Returns:
            Configured storage authentication settings
            
        Raises:
            StorageConfigError: For configuration errors
            StorageValidationError: For validation errors
        """
        # Generate instance key
        instance_key = f"{provider_type}:{settings_namespace}"
        
        # Check for existing instance
        if reuse_existing and instance_key in cls._instances:
            existing_instance = cls._instances[instance_key]
            if kwargs:
                # Update existing instance with new kwargs
                existing_instance.update_settings_from_dict(kwargs)
            return existing_instance
        
        try:
            # Get provider class
            provider_class = cls.get_provider_class(provider_type)
            
            # Prepare settings parameters
            settings_parameters = prepare_settings_parameters(
                settings_namespace=settings_namespace,
                settings_class=provider_class,
                config_files=config_files,
                **kwargs
            )
            
            # Create settings instance
            settings = get_settings(settings_parameters=settings_parameters)
            
            # Validate the settings if required
            if validate:
                cls._validate_settings(settings)
            
            # Store instance if reuse is enabled
            if reuse_existing:
                cls._instances[instance_key] = settings
            
            return settings
            
        except Exception as e:
            if isinstance(e, (StorageConfigError, StorageValidationError)):
                raise
            raise StorageConfigError(
                f"Failed to create auth settings: {str(e)}",
                provider=provider_type
            )
    
    @classmethod
    def _validate_settings(cls, settings: StorageAuthBase) -> None:
        """
        Validate the created settings instance
        
        Args:
            settings: The settings instance to validate
            
        Raises:
            StorageValidationError: If validation fails
        """
        try:
            # Check provider type matches
            provider_class = cls._provider_registry.get(settings.PROVIDER_TYPE)
            if not isinstance(settings, provider_class):
                raise StorageValidationError(
                    f"Settings instance type mismatch. Expected {provider_class}, got {type(settings)}",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="instance_type"
                )
            
            # Validate credentials based on auth method
            cls._validate_credentials(settings)
            
            # Validate connection parameters
            if not settings.validate_connection():
                raise StorageValidationError(
                    "Connection validation failed",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="connection"
                )
                
            # Validate permissions
            if not settings.validate_permissions():
                raise StorageValidationError(
                    "Permission validation failed",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="permissions"
                )
                
        except Exception as e:
            if isinstance(e, StorageValidationError):
                raise
            raise StorageValidationError(
                f"Validation failed: {str(e)}",
                provider=settings.PROVIDER_TYPE,
                validation_type="general"
            )
    
    @classmethod
    def _validate_credentials(cls, settings: StorageAuthBase) -> None:
        """
        Validate credentials based on auth method
        
        Args:
            settings: The settings instance to validate
            
        Raises:
            StorageValidationError: If credential validation fails
        """
        auth_method = settings.AUTH_METHOD
        
        if auth_method == CONST_STORAGE_AUTH_METHOD.KEY:
            if not (settings.ACCESS_KEY and settings.SECRET_KEY):
                raise StorageValidationError(
                    "Access key and secret key required for key authentication",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="credentials"
                )
                
        elif auth_method == CONST_STORAGE_AUTH_METHOD.PASSWORD:
            if not (settings.USERNAME and settings.PASSWORD):
                raise StorageValidationError(
                    "Username and password required for password authentication",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="credentials"
                )
                
        elif auth_method == CONST_STORAGE_AUTH_METHOD.TOKEN:
            if not settings.TOKEN:
                raise StorageValidationError(
                    "Token required for token authentication",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="credentials"
                )
                
        elif auth_method == CONST_STORAGE_AUTH_METHOD.CERTIFICATE:
            if not settings.SSL_CERT:
                raise StorageValidationError(
                    "Certificate required for certificate authentication",
                    provider=settings.PROVIDER_TYPE,
                    validation_type="credentials"
                )
    
    @classmethod
    def get_registered_providers(cls) -> List[str]:
        """
        Get list of registered provider types
        
        Returns:
            List of registered provider type identifiers
        """
        return list(cls._provider_registry.keys())
    
    @classmethod
    def get_provider_info(cls, provider_type: str) -> Dict[str, Any]:
        """
        Get information about a registered provider
        
        Args:
            provider_type: The provider type identifier
            
        Returns:
            Dictionary containing provider information
            
        Raises:
            KeyError: If provider is not registered
        """
        provider_class = cls.get_provider_class(provider_type)
        
        return {
            "type": provider_type,
            "class": provider_class.__name__,
            "module": provider_class.__module__,
            "auth_methods": [
                method for method in CONST_STORAGE_AUTH_METHOD.__dict__
                if isinstance(method, str) and not method.startswith("_")
            ],
            "required_fields": [
                field_name for field_name, field in provider_class.__fields__.items()
                if field.is_required()
            ],
            "supported_features": cls._get_provider_features(provider_class)
        }
    
    @classmethod
    def _get_provider_features(cls, provider_class: Type[StorageAuthBase]) -> Set[str]:
        """
        Get supported features for a provider class
        
        Args:
            provider_class: The provider class to check
            
        Returns:
            Set of supported feature names
        """
        features = set()
        
        # Check basic capabilities
        if hasattr(provider_class, "validate_permissions"):
            features.add("permissions")
        if hasattr(provider_class, "get_connection_url"):
            features.add("connection_url")
        if hasattr(provider_class, "get_pool_config"):
            features.add("connection_pooling")
            
        # Check encryption support
        if provider_class.__fields__.get("ENCRYPTION_ENABLED"):
            features.add("encryption")
            
        # Check authentication methods
        auth_field = provider_class.__fields__.get("AUTH_METHOD")
        if auth_field and auth_field.default:
            features.add(f"auth_{auth_field.default}")
            
        return features
    
    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered providers and instances"""
        cls._provider_registry.clear()
        cls._instances.clear()