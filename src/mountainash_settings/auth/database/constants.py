#path: mountainash_settings/auth/database/constants.py

from mountainash_constants import BaseConstant

class CONST_DB_PROVIDER_TYPE(BaseConstant):
    """Database provider types"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    SQLITE = "sqlite"
    DUCKDB = "duckdb"

class CONST_DB_AUTH_METHOD(BaseConstant):
    """Authentication methods"""
    PASSWORD = "password"
    IAM = "iam"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    WINDOWS = "windows"
    MANAGED_IDENTITY = "managed_identity"

class CONST_DB_SSL_MODE(BaseConstant):
    """SSL modes for database connections"""
    DISABLED = "disabled"
    PREFER = "prefer"
    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"

class CONST_DB_CONNECTION_STATUS(BaseConstant):
    """Database connection status"""
    UNTESTED = "untested"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"

class CONST_DB_POOL_MODE(BaseConstant):
    """Connection pool modes"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    NONE = "none"