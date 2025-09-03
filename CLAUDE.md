# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mountainash-settings is a Python package for advanced configuration management with support for multiple file formats, authentication providers, and secret management. It provides a unified interface for loading settings from environment variables, configuration files (YAML, TOML, JSON), and various secret management systems.

## Architecture

### Core Components

- **MountainAshBaseSettings**: Extended BaseSettings class with template support, multiple file format handling, and settings caching
- **SettingsParameters**: Dataclass for configuration parameters, validation, and smart caching with runtime override support
- **SettingsManager**: Caching layer for settings instances with namespace support and hash-based instance management
- **Authentication System**: Modular authentication for databases, storage, and secrets
- **Settings Cache**: Efficient caching with LRU cache integration and structural parameter differentiation

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
├── settings_cache/                # Settings caching system with get_settings function
├── settings_parameters/           # Parameter handling, validation, and smart merging
```

## MountainAshBaseSettings Architecture

### Primary Interface

MountainAshBaseSettings is the primary interface for using mountainash-settings. It extends standard Pydantic BaseSettings with advanced configuration management features.

#### Basic Usage Pattern
```python
from pydantic import Field
from mountainash_settings import MountainAshBaseSettings

class AppSettings(MountainAshBaseSettings):
    debug: bool = Field(default=False)
    app_name: str = Field(default="MyApp")
    log_file: str = Field(default="logs/{app_name}.log")  # Template support
```

#### Core Features
- **Template Support**: Dynamic field substitution using other field values
- **Multi-Format Configuration**: Support for YAML, TOML, JSON configuration files
- **Smart Caching**: Efficient instance caching with hash-based invalidation
- **Authentication Integration**: Built-in support for database, storage, and secret management authentication
- **Runtime Override Support**: Apply runtime parameters without affecting cache

#### Advanced Configuration
```python
from mountainash_settings import SettingsParameters, get_settings

# Create parameters for complex configurations
params = SettingsParameters.create(
    namespace="production",
    config_files=["config.yaml"],
    settings_class=AppSettings,
    host="prod-server.com"
)

# Use with get_settings function for dynamic resolution
settings = get_settings(settings_parameters=params)
```

### Key Architectural Benefits

1. **SettingsParameters Integration**: Comprehensive parameter handling and validation
2. **Smart Caching**: Hash-based caching with structural vs runtime parameter separation
3. **Template Resolution**: Dynamic template processing with field substitution
4. **Authentication System**: Modular authentication for various providers
5. **Multi-Source Configuration**: Environment variables, configuration files, and secret management
6. **Namespace Support**: Isolation and organization of different configuration contexts

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
├── config/                       # Test configuration files
│   ├── simple_base.yaml         # Base configuration for file-based tests
│   └── simple_production.yaml   # Production configuration for file-based tests
├── test_base_settings.py         # Core MountainAshBaseSettings functionality
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
- `README.md` - Package overview and usage
- `CONTRIBUTING.md` - Contribution guidelines
- `TESTING.md` - Testing guidelines and procedures

### Configuration Examples
- `config/` directory contains example configurations for:
  - Database authentication (BigQuery, Redshift, Snowflake, PostgreSQL, MySQL, etc.)
  - Storage authentication (S3, Azure Blob, GCS, MinIO, etc.)
  - Network storage (FTP, SFTP, NFS, SMB)

### Code Examples
- `examples/` directory contains comprehensive usage examples:
  - Basic MountainAshBaseSettings usage with all features
  - SettingsParameters merging patterns
  - Runtime type resolution patterns
  - Enterprise configuration scenarios

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License
