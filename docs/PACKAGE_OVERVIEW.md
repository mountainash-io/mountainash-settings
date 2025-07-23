# mountainash-settings Package Overview

## Purpose
Advanced configuration management package providing unified interface for loading settings from environment variables, configuration files (YAML, TOML, JSON), and secret management systems with authentication support for databases and storage providers.

## Architecture
The package follows a modular architecture with core base settings functionality, parameter handling, caching layer, and specialized authentication modules organized by provider type (database, storage, secrets, encryption).

## Directory + File Structure
```
src/mountainash_settings/
├── __init__.py                               # Main package exports and API
├── __version__.py                            # Version information
├── settings/
│   ├── __init__.py
│   ├── base/
│   │   ├── __init__.py
│   │   └── base_settings.py                 # MountainAshBaseSettings core class
│   ├── app/
│   │   ├── __init__.py
│   │   ├── app_settings.py                  # Application-specific settings
│   │   └── app_settings_templates.py        # Template configurations
│   └── auth/                                # Authentication modules
│       ├── __init__.py
│       ├── database/                        # Database authentication providers
│       │   ├── __init__.py
│       │   ├── base.py                      # Base database authentication
│       │   ├── constants.py                 # Database constants and enums
│       │   ├── exceptions.py                # Database-specific exceptions
│       │   ├── factory.py                   # Database provider factory
│       │   ├── templates.py                 # Database configuration templates
│       │   ├── bigquery.py                  # Google BigQuery authentication
│       │   ├── duckdb.py                    # DuckDB authentication
│       │   ├── motherduck.py                # MotherDuck authentication
│       │   ├── mssql.py                     # Microsoft SQL Server authentication
│       │   ├── mysql.py                     # MySQL authentication
│       │   ├── postgresql.py                # PostgreSQL authentication
│       │   ├── pyiceberg_rest.py            # PyIceberg REST authentication
│       │   ├── pyspark.py                   # PySpark authentication
│       │   ├── redshift.py                  # Amazon Redshift authentication
│       │   ├── snowflake.py                 # Snowflake authentication
│       │   ├── sqlite.py                    # SQLite authentication
│       │   ├── trino.py                     # Trino authentication
│       │   └── integration/
│       │       ├── __init__.py
│       │       ├── secrets.py               # Secrets integration for databases
│       │       └── security.py             # Security utilities for databases
│       ├── encryption/                      # Encryption support
│       │   ├── __init__.py
│       │   └── gpg.py                       # GPG encryption support
│       ├── secrets/                         # Secret management providers
│       │   ├── __init__.py
│       │   ├── base.py                      # Base secrets functionality
│       │   ├── constants.py                 # Secrets constants
│       │   ├── exceptions.py                # Secrets-specific exceptions
│       │   ├── secrets_functions.py         # Secrets utility functions
│       │   ├── templates.py                 # Secrets configuration templates
│       │   └── providers/
│       │       ├── __init__.py
│       │       ├── aws_secrets.py           # AWS Secrets Manager
│       │       ├── azure_keyvault.py        # Azure Key Vault
│       │       ├── gcp_secrets.py           # Google Cloud Secret Manager
│       │       ├── hashicorp_vault.py       # HashiCorp Vault
│       │       └── local_secrets.py         # Local secrets handling
│       └── storage/                         # Storage authentication providers
│           ├── __init__.py
│           ├── base.py                      # Base storage authentication
│           ├── constants.py                 # Storage constants
│           ├── exceptions.py                # Storage-specific exceptions
│           ├── templates.py                 # Storage configuration templates
│           ├── providers/
│           │   ├── __init__.py
│           │   ├── azure_blob.py            # Azure Blob Storage
│           │   ├── azure_files.py           # Azure Files
│           │   ├── b2.py                    # Backblaze B2
│           │   ├── ftp.py                   # FTP storage
│           │   ├── gcs.py                   # Google Cloud Storage
│           │   ├── github.py                # GitHub storage
│           │   ├── local.py                 # Local filesystem
│           │   ├── minio.py                 # MinIO object storage
│           │   ├── nfs.py                   # Network File System
│           │   ├── r2.py                    # Cloudflare R2
│           │   ├── s3.py                    # Amazon S3
│           │   ├── s3_express.py            # Amazon S3 Express One Zone
│           │   ├── sftp.py                  # SFTP storage
│           │   ├── smb.py                   # SMB/CIFS storage
│           │   └── ssh.py                   # SSH storage
│           └── utils/
│               ├── __init__.py
│               ├── connection.py            # Connection utilities
│               ├── security.py              # Security utilities
│               └── validation.py            # Validation utilities
├── settings_cache/                          # Settings caching system
│   ├── __init__.py
│   ├── settings_functions.py                # Caching utility functions
│   └── settings_manager.py                 # Settings instance manager with caching
└── settings_parameters/                     # Parameter handling and validation
    ├── __init__.py
    ├── filehandler.py                       # File handling utilities
    ├── kwargshandler.py                     # Keyword argument processing
    ├── settings_parameters.py               # Core parameter handling
    └── utils.py                             # Parameter utility functions
```

## Key Components

### mountainash_settings
Core package providing advanced configuration management with support for multiple file formats, authentication providers, and secret management systems.

**Main Classes:**
- `MountainAshBaseSettings`: Extended BaseSettings class with template support and multi-format configuration loading
- `SettingsParameters`: Configuration parameter validation and handling
- `SettingsManager`: Caching layer for settings instances with namespace support
- `SettingsUtils`: Utility functions for settings operations

**Key Features:**
- Multi-format configuration file support (YAML, TOML, JSON, environment files)
- Template-based configuration with variable substitution
- Comprehensive authentication system for databases, storage, and secrets
- Settings caching with hash-based instance management
- Modular provider architecture for extensibility

## Usage Patterns
- Loading application settings from multiple configuration sources
- Authenticating with various database systems (BigQuery, Snowflake, PostgreSQL, etc.)
- Managing secrets from cloud providers (AWS, Azure, GCP) and HashiCorp Vault
- Authenticating with storage systems (S3, Azure Blob, GCS, MinIO, etc.)
- Caching settings instances for performance optimization
- Template-based configuration management with environment-specific overrides

## Dependencies

**Runtime: 4 packages**

**Local Dependencies:**
None - this is a standalone package

**External Dependencies:**
- `pydantic==2.9.2` - Data validation and settings management
- `pydantic-settings==2.6.1` - Settings management with multiple sources  
- `universal_pathlib==0.2.2` - Universal filesystem path handling
- `pyaml` - YAML configuration file support

**Optional Provider Dependencies:**
- Various cloud provider SDKs (AWS, Azure, GCP) for secret management
- Database drivers for authentication configuration  
- Storage provider libraries for filesystem authentication

## Integration
This package serves as a foundational configuration management system that integrates with:
- Cloud infrastructure providers (AWS, Azure, GCP) for secrets and storage
- Database systems across multiple vendors and platforms
- Container orchestration and deployment systems through environment variable support
- CI/CD pipelines through configuration file and template management
- Other Mountain Ash ecosystem packages requiring unified configuration management