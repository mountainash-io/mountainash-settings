"""
Simplified merge framework for eliminating duplicate merge patterns.

Provides simple merge utilities that handle prioritization logic 
while maintaining identical functionality to the original complex implementation.
"""

from typing import Optional, Union, List, Any, Tuple, Dict
from upath import UPath
from .settings_parameters import SettingsParameters


class ValidationError(Exception):
    """Exception for validation failures in merge operations."""
    pass


def _merge_simple(first: Any, second: Any, first_wins: bool = False) -> Any:
    """Merge two simple values based on priority."""
    if first_wins:
        return first or second
    return second or first


def _merge_config_files(first: Optional[Tuple], second: Optional[Tuple], first_wins: bool = False) -> Optional[Tuple]:
    """Merge configuration file tuples with deduplication."""
    if first is None and second is None:
        return None
    
    if first_wins:
        return first or second
    
    # Default behavior: combine and deduplicate  
    merged = set(first or ()) | set(second or ())
    return tuple(sorted(merged)) if merged else None


def _merge_kwargs(first: Optional[Dict], second: Optional[Dict], first_wins: bool = False) -> Optional[Dict]:
    """Merge keyword argument dictionaries."""
    if first is None and second is None:
        return None
    
    if first_wins:
        return first or second
    
    # Default behavior: merge with second taking precedence
    merged = dict(first or {}) | dict(second or {})
    # Handle special kwargs nesting
    merged = merged.get("kwargs", merged)
    return merged if merged else None


def _merge_settings_class(first: Optional[type], second: Optional[type], first_wins: bool = False) -> Optional[type]:
    """Merge settings classes with compatibility validation."""
    if first is None and second is None:
        return None
    
    # Validate compatibility if both are provided
    if first is not None and second is not None and first != second:
        raise ValidationError(f"Settings class must match for merging. first: {first} != second: {second}")
    
    if first_wins:
        return first or second
    return second or first


class SettingsParameterMerger:
    """Simplified merger for SettingsParameters objects."""
    
    def merge_with_object(self, 
                         base: SettingsParameters,
                         other: SettingsParameters,
                         prioritise_base: bool = False) -> SettingsParameters:
        """Merge two SettingsParameters objects."""
        if base is None:
            raise ValidationError("Base SettingsParameters cannot be None")
        
        if other is None:
            return base
        
        # Simple field-by-field merging
        # For namespace, don't apply _init_namespace fallback until after merge
        resolved_namespace = _merge_simple(
            base.namespace,
            other.namespace,
            prioritise_base
        )
        # Apply the DEFAULT fallback only if result is None
        if resolved_namespace is None:
            resolved_namespace = base._init_namespace(None)
        
        resolved_config_files = _merge_config_files(
            base.config_files, other.config_files, prioritise_base
        )
        
        resolved_kwargs = _merge_kwargs(
            base.kwargs, other.kwargs, prioritise_base
        )
        
        resolved_env_prefix = _merge_simple(
            base.env_prefix, other.env_prefix, prioritise_base
        )
        
        resolved_settings_class = _merge_settings_class(
            base.settings_class, other.settings_class, prioritise_base
        )
        
        resolved_secrets_dir = _merge_simple(
            base.secrets_dir, other.secrets_dir, prioritise_base
        )
        
        return SettingsParameters.create(
            settings_class=resolved_settings_class,
            namespace=resolved_namespace,
            config_files=resolved_config_files,
            env_prefix=resolved_env_prefix,
            secrets_dir=resolved_secrets_dir,
            **(resolved_kwargs or {})
        )
    
    def merge_with_params(self,
                         base: SettingsParameters,
                         namespace: Optional[str] = None,
                         config_files: Optional[Union[UPath, str, List[Union[UPath, str]]]] = None,
                         kwargs: Optional[Dict[str, Any]] = None,
                         env_prefix: Optional[str] = None,
                         secrets_dir: Optional[str] = None,
                         prioritise_base: bool = False) -> SettingsParameters:
        """Merge SettingsParameters with individual parameters."""
        if base is None:
            raise ValidationError("Base SettingsParameters cannot be None")
        
        # Convert config_files to proper format
        from .filehandler import SettingsFileHandler
        formatted_config_files = SettingsFileHandler.format_config_file_tuple(config_files)
        
        # Simple field-by-field merging
        # For namespace, don't apply _init_namespace fallback until after merge
        resolved_namespace = _merge_simple(
            base.namespace,
            namespace,
            prioritise_base
        )
        # Apply the DEFAULT fallback only if result is None
        if resolved_namespace is None:
            resolved_namespace = base._init_namespace(None)
        
        resolved_config_files = _merge_config_files(
            base.config_files, formatted_config_files, prioritise_base
        )
        
        resolved_kwargs = _merge_kwargs(
            base.kwargs, kwargs, prioritise_base
        )
        
        resolved_env_prefix = _merge_simple(
            base.env_prefix, env_prefix, prioritise_base
        )
        
        resolved_secrets_dir = _merge_simple(
            base.secrets_dir, secrets_dir, prioritise_base
        )
        
        return SettingsParameters.create(
            settings_class=base.settings_class,
            namespace=resolved_namespace,
            config_files=resolved_config_files,
            env_prefix=resolved_env_prefix,
            secrets_dir=resolved_secrets_dir,
            **(resolved_kwargs or {})
        )


class FieldMergeUtils:
    """Simple utility functions for merging specific field types."""
    
    @staticmethod
    def merge_namespaces(first: Optional[str] = None, second: Optional[str] = None) -> str:
        """Merge namespace strings with default fallback."""
        return first or second or "DEFAULT"
    
    @staticmethod  
    def merge_env_prefixes(first: Optional[str] = None, second: Optional[str] = None) -> Optional[str]:
        """Merge environment prefix strings."""
        return first or second
    
    @staticmethod
    def merge_config_files_simple(first: Optional[Tuple] = None, second: Optional[Tuple] = None) -> Optional[Tuple]:
        """Simple config file merge with deduplication."""
        return _merge_config_files(first, second, first_wins=False)
    
    @staticmethod
    def merge_kwargs_simple(first: Optional[Dict] = None, second: Optional[Dict] = None) -> Optional[Dict]:
        """Simple kwargs merge with second taking precedence."""
        return _merge_kwargs(first, second, first_wins=False)


# Global merger instance for easy access
_global_merger = SettingsParameterMerger()


def get_merger() -> SettingsParameterMerger:
    """Get the global merger instance."""
    return _global_merger


# Legacy compatibility exports (unused but maintain API)
class MergePriority:
    """Legacy enum compatibility."""
    FIRST_WINS = "first_wins"
    SECOND_WINS = "second_wins" 
    COMBINE = "combine"


class GenericMerger:
    """Legacy compatibility class."""
    def __init__(self):
        self._merger = _global_merger
    
    def merge_field(self, field_name: str, first_value: Any, second_value: Any, 
                   strategy_name: str = 'simple', prioritise_first: bool = False) -> Any:
        """Legacy compatibility method."""
        return _merge_simple(first_value, second_value, prioritise_first)
    
    def merge_fields(self, field_specs: Dict, prioritise_first: bool = False) -> Dict:
        """Legacy compatibility method."""
        results = {}
        for field_name, spec in field_specs.items():
            results[field_name] = _merge_simple(spec['first'], spec['second'], prioritise_first)
        return results