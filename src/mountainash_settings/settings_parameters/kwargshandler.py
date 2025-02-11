from typing import Optional, Tuple, Dict, Any


class SettingsKwargsHandler:
    """Handles validation and separation of configuration files by type"""
    
    @classmethod
    def format_kwargs_dict(cls, 
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any] = None
                            ) -> Optional[Dict[str,Any]]:
        
        """
        Ensures the kwargs are formatted as a dictionary.

        Args:
            p_kwargs (dict): The keyword arguments.

        Returns:
            dict: The keyword arguments as a dictionary, or None if not provided.
        """

        if p_kwargs is None:
            return None
        
        if isinstance(p_kwargs, dict):
            p_kwargs = p_kwargs.get("kwargs", p_kwargs)
            return p_kwargs
        
        if isinstance(p_kwargs, tuple):
            p_kwargs = dict(p_kwargs)
            p_kwargs = p_kwargs.get("kwargs", p_kwargs)
            return p_kwargs
        
        raise ValueError(f"Invalid p_kwargs: {p_kwargs}")


    @classmethod
    def format_kwargs_tuple(cls, 
                            p_kwargs: None | Dict[str,Any] | Tuple[Any,Any]  = None
                            ) -> Optional[Tuple[Any,Any]]:
        
        """
        Forces the kwargs to be formatted as a tuple for immutability in the parameters.

        Args:
            p_kwargs (dict): The keyword arguments.

        Returns:
            dict: The keyword arguments as a dictionary, or None if not provided.
        """

        if p_kwargs is None:
            return tuple()
        
        if isinstance(p_kwargs, dict):
            return tuple(sorted(p_kwargs.items()))
        
        if isinstance(p_kwargs, tuple):
            return p_kwargs
        
        raise ValueError(f"Invalid p_kwargs: {p_kwargs}")

    @staticmethod
    def merge_kwargs(kwargs1: Optional[Dict[str, Any]] = None,
                     kwargs2: Optional[Dict[str, Any]] = None) -> Optional[Dict[str,Any]]: #Optional[Tuple[Tuple[str, Any], ...]]:
        
        if kwargs1 is None and kwargs2 is None:
            return None

        #TODO: Test the precedence of kwargs
        resolved_kwargs = dict(kwargs1 or ()) | dict(kwargs2 or ())

        resolved_kwargs = resolved_kwargs.get("kwargs", resolved_kwargs)

        return resolved_kwargs
        # return tuple(sorted(merged.items()))
