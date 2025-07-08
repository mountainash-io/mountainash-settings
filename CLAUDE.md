# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mountainash-settings is a Python package for advanced configuration management with support for multiple file formats, authentication providers, and secret management. It provides a unified interface for loading settings from environment variables, configuration files (YAML, TOML, JSON), and various secret management systems.

## Architecture

### Core Components

- **MountainAshBaseSettings**: Extended BaseSettings class with template support, multiple file format handling, and settings caching
- **SettingsParameters**: Dataclass for configuration parameters and validation
- **SettingsManager**: Caching layer for settings instances with namespace support
- **Authentication System**: Modular authentication for databases, storage, and secrets
- **Settings Cache**: Efficient caching with hash-based instance management

### Package Structure

```
src/mountainash_settings/
├── __init__.py                    # Main package exports
├── __version__.py                 # Version information
├── settings/
│   ├── base/
│   │   └── base_settings.py       # MountainAshBaseSettings core class
│   ├── app/
│   │   ├── app_settings.py        # Application-specific settings
│   │   └── app_settings_templates.py  # Template configurations
│   └── auth/                      # Authentication modules
│       ├── database/              # Database authentication
│       ├── encryption/            # GPG encryption support
│       ├── secrets/               # Secret management providers
│       └── storage/               # Storage authentication
├── settings_cache/                # Settings caching system
├── settings_parameters/           # Parameter handling and validation
```


## Build/Test/Lint Commands
- Build: `hatch build`
- Lint: `hatch run ruff:check` or `hatch run ruff:fix` to auto-fix
- Tests: `hatch run test:test` or `hatch run test:cov` for coverage
- Single test: `pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Type check: `hatch run mypy:check`

## Dependencies

### Core Dependencies
- pydantic==2.9.2 - Data validation and settings management
- pydantic-settings==2.6.1 - Settings management with multiple sources
- universal_pathlib==0.2.2 - Universal filesystem path handling
- pyaml - YAML configuration file support

### Authentication Dependencies
- Various cloud provider SDKs (AWS, Azure, GCP) for secret management
- Database drivers for authentication configuration
- Storage provider libraries for file system authentication

### Development Dependencies
- pytest==8.3.5
- pytest-check, pytest-cov, pytest-mock
- ruff==0.3.7
- mypy==1.10.1
- radon==6.0.1

## GitHub Actions Workflows

### Testing
- **python-run-pytest**: Runs comprehensive test suite on pull requests, supports Python 3.12
- **python-run-ruff**: Code linting and formatting checks
- **python-run-radon**: Complexity analysis and code quality metrics

### Release Process
- **build-and-release-package**: Automated release workflow
- **main-release-build-dependencies**: Dependency validation for main branch
- **main-release-branch-validation**: Branch protection and validation
- Supports production, RC, and beta releases
- Generates SBOMs (Software Bill of Materials)
- Creates releases in GitHub and mountainash-wheels repository

### Branch Strategy
- `main`: Production releases (only release/* and hotfix/* branches)
- `develop`: Development and RC releases
- `feature/*`, `bugfix/*`, `hotfix/*`: Feature branches
- Protected branches require code owner approval

## Code Style Guidelines
- Formatting: Uses ruff for formatting and linting
- Imports: Standard lib first, third-party next, project imports last
- Types: Use typing annotations (e.g., `import typing as t`) for all functions
- Naming: CamelCase for classes, snake_case for functions/variables, UPPER_CASE for constants
- Error handling: Use ValueError for validation errors, custom exceptions for specific cases
- Documentation: Use Google-style docstrings for classes and methods
- Organization: Follow modular design with clear separation of concerns
- Testing: Create unit tests with appropriate markers (unit, integration, performance)

## Development Environments

### Hatch Environments
- `default`: Local development
- `test`: Local testing with extended pytest plugins
- `test_github`: GitHub Actions testing
- `build_github`: GitHub Actions building
- `ruff`: Linting and formatting
- `radon`: Complexity analysis
- `mypy`: Type checking

## Testing Structure

### Test Organization
```
tests/
├── secrets/                       # Secret management tests
│   ├── test_aws.py               # AWS Secrets Manager tests
│   ├── test_azure.py             # Azure Key Vault tests
│   ├── test_gcp.py               # GCP Secret Manager tests
│   └── test_hashicorp.py         # HashiCorp Vault tests
├── storage/                      # Storage authentication tests
│   ├── test_auth_storage_base.py # Base storage auth tests
│   └── test_auth_storage_s3.py   # S3 storage auth tests
├── test_base_settings.py         # Core settings functionality
├── test_config_files.py          # Configuration file handling
├── test_settings_manager.py      # Settings caching and management
└── test_settings_utils.py        # Utility functions
```

### Configuration Files
- Environment files for testing different configurations
- Supports prefix-based environment variable testing
- Integration tests for various auth providers

## Documentation

### Available Documentation
- `docs/database-auth-architecture.md` - Database authentication architecture
- `docs/database-auth-requirements.md` - Database authentication requirements
- `docs/storage-auth-spec.md` - Storage authentication specification
- `docs/secrets-implementation-comparison.md` - Secret management comparison
- `README.md` - Package overview and usage
- `CONTRIBUTING.md` - Contribution guidelines
- `TESTING.md` - Testing guidelines and procedures

### Configuration Examples
- `config/` directory contains example configurations for:
  - Database authentication (BigQuery, Redshift, Snowflake, PostgreSQL, MySQL, etc.)
  - Storage authentication (S3, Azure Blob, GCS, MinIO, etc.)
  - Network storage (FTP, SFTP, NFS, SMB)

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License
