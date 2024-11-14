#path: mountainash_settings/auth/database/factory.py

from typing import Optional, Union, List, Type, Dict, Any
from upath import UPath

from mountainash_settings import prepare_settings_parameters, get_settings
from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import CONST_DB_PROVIDER_TYPE
from mountainash_settings.auth.database.exceptions import DBAuthConfigError, DBAuthValidationError

class DBAuthFactory:
    """Factory for creating database authentication settings"""
    
    _provider_registry: Dict[str, Type[BaseDBAuthSettings]] = {}
    _instances: Dict[str, BaseDBAuthSettings] = {}
    
    @classmethod
    def register_provider(cls, provider_type: str, provider_class: Type[BaseDBAuthSettings]) -> None:
        """
        Register a database provider
        
        Args:
            provider_type: The type identifier for the provider
            provider_class: The provider class implementation
            
        Raises:
            TypeError: If provider_class doesn't inherit from BaseDBAuthSettings
            ValueError: If provider_type is already registered
        """
        if not issubclass(provider_class, BaseDBAuthSettings):
            raise TypeError(f"Provider class must inherit from BaseDBAuthSettings: {provider_class}")
            
        if provider_type in cls._provider_registry:
            raise ValueError(f"Provider type already registered: {provider_type}")
            
        cls._provider_registry[provider_type] = provider_class
    
    @classmethod
    def unregister_provider(cls, provider_type: str) -> None:
        """
        Unregister a database provider
        
        Args:
            provider_type: The type identifier to unregister
            
        Raises:
            KeyError: If provider_type is not registered
        """
        if provider_type not in cls._provider_registry:
            raise KeyError(f"Provider type not registered: {provider_type}")
            
        del cls._provider_registry[provider_type]
    
    @classmethod
    def get_provider_class(cls, provider_type: str) -> Type[BaseDBAuthSettings]:
        """
        Get the provider class for a given type
        
        Args:
            provider_type: The type identifier
            
        Returns:
            The provider class
            
        Raises:
            DBAuthConfigError: If provider type is unknown or not registered
        """
        if provider_type not in CONST_DB_PROVIDER_TYPE.__dict__:
            raise DBAuthConfigError(
                f"Unknown provider type: {provider_type}",
                provider=provider_type
            )
        
        provider_class = cls._provider_registry.get(provider_type)
        if not provider_class:
            raise DBAuthConfigError(
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
        **kwargs
    ) -> BaseDBAuthSettings:
        """
        Create appropriate auth settings instance
        
        Args:
            provider_type: The type of database provider
            settings_namespace: Namespace for the settings
            config_files: Optional configuration files
            reuse_existing: Whether to reuse existing instances
            **kwargs: Additional settings parameters
            
        Returns:
            Configured database authentication settings
            
        Raises:
            DBAuthConfigError: For configuration errors
            DBAuthValidationError: For validation errors
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
            
            # Validate the settings
            cls._validate_settings(settings)
            
            # Store instance if reuse is enabled
            if reuse_existing:
                cls._instances[instance_key] = settings
            
            return settings
            
        except Exception as e:
            if isinstance(e, (DBAuthConfigError, DBAuthValidationError)):
                raise
            raise DBAuthConfigError(
                f"Failed to create auth settings: {str(e)}",
                provider=provider_type
            )
    
    @classmethod
    def _validate_settings(cls, settings: BaseDBAuthSettings) -> None:
        """
        Validate the created settings instance
        
        Args:
            settings: The settings instance to validate
            
        Raises:
            DBAuthValidationError: If validation fails
        """
        # Check provider type matches
        provider_class = cls._provider_registry.get(settings.PROVIDER_TYPE)
        if not isinstance(settings, provider_class):
            raise DBAuthValidationError(
                f"Settings instance type mismatch. Expected {provider_class}, got {type(settings)}",
                provider=settings.PROVIDER_TYPE,
                validation_type="instance_type"
            )
        
        # Validate connection parameters
        try:
            settings.validate_connection()
        except Exception as e:
            raise DBAuthValidationError(
                f"Connection validation failed: {str(e)}",
                provider=settings.PROVIDER_TYPE,
                validation_type="connection"
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
    def clear_registry(cls) -> None:
        """Clear all registered providers and instances"""
        cls._provider_registry.clear()
        cls._instances.clear()
    
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
                method for method in CONST_DB_PROVIDER_TYPE.__dict__
                if isinstance(method, str) and not method.startswith("_")
            ],
            "required_fields": [
                field_name for field_name, field in provider_class.__fields__.items()
                if field.is_required()
            ]
        }