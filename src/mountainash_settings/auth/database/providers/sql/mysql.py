#path: mountainash_settings/auth/database/providers/sql/mysql.py

from typing import Optional, Dict, Any, List
from pydantic import Field, SecretStr, field_validator
import re

from mountainash_settings.auth.database.base import BaseDBAuthSettings
from mountainash_settings.auth.database.constants import (
    CONST_DB_PROVIDER_TYPE,
    CONST_DB_AUTH_METHOD,
    CONST_DB_SSL_MODE
)
from mountainash_settings.auth.database.exceptions import (
    DBAuthValidationError,
    DBAuthConnectionError,
    DBAuthConfigError
)

class MySQLAuthSettings(BaseDBAuthSettings):
    """MySQL authentication settings"""
    
    PROVIDER_TYPE: str = Field(default=CONST_DB_PROVIDER_TYPE.MYSQL)
    PORT: int = Field(default=3306)
    
    # MySQL-specific Settings
    CHARSET: str = Field(default="utf8mb4")
    COLLATION: str = Field(default="utf8mb4_unicode_ci")
    AUTOCOMMIT: bool = Field(default=True)
    
    # Security Settings
    ALLOW_LOCAL_INFILE: bool = Field(default=False)
    SSL_MODE: str = Field(default=CONST_DB_SSL_MODE.PREFER)
    SSL_CIPHER: Optional[str] = Field(default=None)
    TLS_VERSION: Optional[List[str]] = Field(default=["TLSv1.2", "TLSv1.3"])
    
    # Connection Settings
    CONNECT_TIMEOUT: int = Field(default=10)
    READ_TIMEOUT: Optional[int] = Field(default=None)
    WRITE_TIMEOUT: Optional[int] = Field(default=None)
    MAX_ALLOWED_PACKET: Optional[int] = Field(default=None)
    
    # Compression Settings
    COMPRESSION: bool = Field(default=False)
    COMPRESSION_LEVEL: Optional[int] = Field(default=None)
    
    # Client Settings
    PROGRAM_NAME: Optional[str] = Field(default="MountainAsh")
    CLIENT_FLAG: Optional[int] = Field(default=None)
    
    ## Field Validators ##
    @field_validator("CHARSET")
    def validate_charset(cls, v: str) -> str:
        """Validate MySQL charset"""
        valid_charsets = {
            "utf8mb4", "utf8mb3", "utf8", "latin1", 
            "ascii", "binary", "cp1251", "latin2"
        }
        if v not in valid_charsets:
            raise DBAuthValidationError(
                f"Invalid charset. Must be one of: {valid_charsets}",
                provider=CONST_DB_PROVIDER_TYPE.MYSQL,
                validation_type="charset"
            )
        return v

    @field_validator("SSL_MODE")
    def validate_ssl_mode(cls, v: str) -> str:
        """Validate SSL mode"""
        if v not in CONST_DB_SSL_MODE.__dict__:
            raise DBAuthValidationError(
                f"Invalid SSL mode",
                provider=CONST_DB_PROVIDER_TYPE.MYSQL,
                validation_type="ssl_mode"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        super()._init_provider_specific(reinitialise)
        
        # Validate SSL configuration
        if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
            if self.SSL_MODE in {CONST_DB_SSL_MODE.VERIFY_CA, CONST_DB_SSL_MODE.VERIFY_FULL}:
                if not self.SSL_CA:
                    raise DBAuthConfigError(
                        f"CA certificate required for SSL mode: {self.SSL_MODE}",
                        provider=self.PROVIDER_TYPE
                    )

    def get_connection_string(self) -> str:
        """Generate MySQL connection string"""
        template = "mysql://{username}:{password}@{host}:{port}/{database}"
        
        params = []
        
        # Add charset and collation
        if self.CHARSET:
            params.append(f"charset={self.CHARSET}")
        if self.COLLATION:
            params.append(f"collation={self.COLLATION}")
            
        # Add SSL parameters
        if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
            params.append(f"ssl_mode={self.SSL_MODE}")
            if self.SSL_CA:
                params.append(f"ssl_ca={self.SSL_CA}")
            if self.SSL_CERT:
                params.append(f"ssl_cert={self.SSL_CERT}")
            if self.SSL_KEY:
                params.append(f"ssl_key={self.SSL_KEY}")
            if self.SSL_CIPHER:
                params.append(f"ssl_cipher={self.SSL_CIPHER}")
                
        # Add timeouts
        if self.CONNECT_TIMEOUT:
            params.append(f"connect_timeout={self.CONNECT_TIMEOUT}")
        if self.READ_TIMEOUT:
            params.append(f"read_timeout={self.READ_TIMEOUT}")
        if self.WRITE_TIMEOUT:
            params.append(f"write_timeout={self.WRITE_TIMEOUT}")
            
        # Add other parameters
        if self.ALLOW_LOCAL_INFILE:
            params.append("local_infile=1")
        if self.COMPRESSION:
            params.append("compression=1")
            
        if params:
            template += "?" + "&".join(params)
            
        return self.format_connection_string(template)

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments for MySQL"""
        args = super().get_connection_args()
        
        # Add MySQL-specific arguments
        args.update({
            "charset": self.CHARSET,
            "use_unicode": True,
            "autocommit": self.AUTOCOMMIT,
            "connect_timeout": self.CONNECT_TIMEOUT,
            "program_name": self.PROGRAM_NAME
        })
        
        # Add optional arguments
        if self.READ_TIMEOUT:
            args["read_timeout"] = self.READ_TIMEOUT
        if self.WRITE_TIMEOUT:
            args["write_timeout"] = self.WRITE_TIMEOUT
        if self.MAX_ALLOWED_PACKET:
            args["max_allowed_packet"] = self.MAX_ALLOWED_PACKET
        if self.CLIENT_FLAG:
            args["client_flag"] = self.CLIENT_FLAG
        if self.COMPRESSION:
            args["compression"] = True
            if self.COMPRESSION_LEVEL:
                args["compression_level"] = self.COMPRESSION_LEVEL
                
        # Add SSL configuration
        if self.SSL_MODE != CONST_DB_SSL_MODE.DISABLED:
            args["ssl_mode"] = self.SSL_MODE
            ssl = {}
            if self.SSL_CA:
                ssl["ca"] = self.SSL_CA
            if self.SSL_CERT:
                ssl["cert"] = self.SSL_CERT
            if self.SSL_KEY:
                ssl["key"] = self.SSL_KEY
            if self.SSL_CIPHER:
                ssl["cipher"] = self.SSL_CIPHER
            if self.TLS_VERSION:
                ssl["tls_versions"] = self.TLS_VERSION
            if ssl:
                args["ssl"] = ssl
                
        return args

    # def _test_connection(self) -> bool:
    #     """Test MySQL connection"""
    #     try:
    #         import mysql.connector
            
    #         conn = mysql.connector.connect(**self.get_connection_args())
    #         with conn.cursor() as cursor:
    #             cursor.execute("SELECT VERSION()")
    #             version = cursor.fetchone()[0]
                
    #         conn.close()
    #         return True
            
    #     except Exception as e:
    #         raise DBAuthConnectionError(
    #             f"Failed to connect to MySQL: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )