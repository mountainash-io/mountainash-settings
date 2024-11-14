#path: mountainash_settings/auth/database/providers/file/duckdb.py

from typing import Optional, Dict, Any, List
from pathlib import Path
import os
from pydantic import Field, field_validator

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import (
    CONST_DB_PROVIDER_TYPE,
    CONST_DB_AUTH_METHOD
)
from mountainash_settings.auth.database.exceptions import (
    DBAuthValidationError,
    DBAuthConnectionError,
    DBAuthConfigError
)

class DuckDBAuthSettings(BaseDBAuthSettings):
    """DuckDB authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.DUCKDB)
    AUTH_METHOD: str = Field(default="none")  # DuckDB uses file-based authentication
    
    # File Settings
    DATABASE_PATH: Optional[str] = Field(default=None)  # None for in-memory
    READ_ONLY: bool = Field(default=False)
    MEMORY: bool = Field(default=False)
    
    # Configuration Settings
    THREADS: Optional[int] = Field(default=None)
    MEMORY_LIMIT: Optional[str] = Field(default=None)  # e.g., "4GB"
    TEMP_DIRECTORY: Optional[str] = Field(default=None)
    
    # Extension Settings
    EXTENSIONS: List[str] = Field(default_factory=list)
    ALLOW_UNSIGNED_EXTENSIONS: bool = Field(default=False)
    
    # Performance Settings
    PAGE_SIZE: Optional[int] = Field(default=None)  # in bytes
    COMPRESSION: Optional[str] = Field(default="auto")
    ACCESS_MODE: Optional[str] = Field(default=None)  # "AUTOMATIC", "DIRECT_IO"
    
    ## Field Validators ##
    @field_validator("MEMORY_LIMIT")
    def validate_memory_limit(cls, v: Optional[str]) -> Optional[str]:
        """Validate memory limit format"""
        if v is not None:
            # Check format: number + unit (KB, MB, GB)
            import re
            if not re.match(r'^\d+[KMG]B$', v):
                raise DBAuthValidationError(
                    "Invalid memory limit format. Must be like: 4GB, 512MB, etc.",
                    provider=CONST_DB_PROVIDER_TYPE.DUCKDB,
                    validation_type="memory_limit"
                )
        return v

    @field_validator("DATABASE_PATH")
    def validate_database_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate database path if provided"""
        if v is None or v == ":memory:":
            return v
            
        try:
            path = Path(v)
            parent = path.parent
            
            # Check if parent directory exists
            if not parent.exists() and str(parent) != ".":
                raise DBAuthValidationError(
                    f"Parent directory does not exist: {parent}",
                    provider=CONST_DB_PROVIDER_TYPE.DUCKDB,
                    validation_type="database_path"
                )
            
            # Check if path is absolute
            if not path.is_absolute():
                return str(path.resolve())
                
            return v
            
        except Exception as e:
            if isinstance(e, DBAuthValidationError):
                raise
            raise DBAuthValidationError(
                f"Invalid database path: {str(e)}",
                provider=CONST_DB_PROVIDER_TYPE.DUCKDB,
                validation_type="database_path"
            )

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate memory settings
        if self.MEMORY and self.DATABASE_PATH:
            raise DBAuthConfigError(
                "Cannot specify both MEMORY and DATABASE_PATH",
                provider=self.PROVIDER_TYPE
            )
            
        # Validate read-only requirements
        if self.READ_ONLY and self.DATABASE_PATH:
            if not os.path.exists(self.DATABASE_PATH):
                raise DBAuthConfigError(
                    f"Database file does not exist for read-only mode: {self.DATABASE_PATH}",
                    provider=self.PROVIDER_TYPE
                )
                
        # Validate temp directory
        if self.TEMP_DIRECTORY and not os.path.exists(self.TEMP_DIRECTORY):
            raise DBAuthConfigError(
                f"Temporary directory does not exist: {self.TEMP_DIRECTORY}",
                provider=self.PROVIDER_TYPE
            )

    def get_connection_string(self) -> str:
        """Generate DuckDB connection string"""
        if self.MEMORY:
            return "duckdb://:memory:"
        elif self.DATABASE_PATH:
            params = []
            if self.READ_ONLY:
                params.append("read_only=true")
            if params:
                return f"duckdb://{self.DATABASE_PATH}?{'&'.join(params)}"
            return f"duckdb://{self.DATABASE_PATH}"
        else:
            return "duckdb://"  # Default in-memory database

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for DuckDB"""
        args = {
            "read_only": self.READ_ONLY
        }
        
        if not self.MEMORY:
            args["database"] = self.DATABASE_PATH
            
        config = {}
        
        if self.THREADS:
            config["threads"] = self.THREADS
        if self.MEMORY_LIMIT:
            config["memory_limit"] = self.MEMORY_LIMIT
        if self.TEMP_DIRECTORY:
            config["temp_directory"] = self.TEMP_DIRECTORY
        if self.PAGE_SIZE:
            config["page_size"] = self.PAGE_SIZE
        if self.COMPRESSION:
            config["compression"] = self.COMPRESSION
        if self.ACCESS_MODE:
            config["access_mode"] = self.ACCESS_MODE
            
        if config:
            args["config"] = config
            
        return {k: v for k, v in args.items() if v is not None}

    # def _test_connection(self) -> bool:
    #     """Test DuckDB connection"""
    #     try:
    #         import duckdb
            
    #         conn_args = self.get_connection_args()
    #         config = conn_args.pop("config", {})
            
    #         # Set configuration
    #         for key, value in config.items():
    #             duckdb.default_connection.execute(f"SET {key}={value}")
            
    #         # Attempt connection
    #         conn = duckdb.connect(**conn_args)
            
    #         # Load extensions
    #         for extension in self.EXTENSIONS:
    #             conn.load_extension(extension, allow_unsigned=self.ALLOW_UNSIGNED_EXTENSIONS)
                
    #         # Test query
    #         conn.execute("SELECT 1").fetchall()
            
    #         conn.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to DuckDB: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )