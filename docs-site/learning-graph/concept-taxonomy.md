# Concept Taxonomy

This taxonomy organizes the 110 mountainash-settings concepts into 10 categories.

## Categories

### FOUND -- Foundation Concepts
Prerequisites: Pydantic BaseModel/BaseSettings, field validators, model config, file formats (YAML, TOML, JSON, .env), environment variables, decorators, discriminated unions, SecretStr.

### BASE -- Base Settings
MountainAshBaseSettings class, post_init lifecycle, source customization, validate_assignment invariant, multi-format file loading.

### PARAM -- Settings Parameters
SettingsParameters with structural/runtime split, custom hash/eq, merge framework with three strategies, FileHandler, KwargsHandler.

### TEMPL -- Field Templating
{FIELD_NAME} template syntax, resolution during post_init, UPath path derivation, priority rules.

### SECRT -- Secrets Resolution
Secrets registry, pluggable providers (Vault, SSM, Key Vault), two-pass resolution pipeline, frozen model rebuild.

### PROF -- Connection Profiles
ProfileDescriptor, ParameterSpec with tiers/defaults/transforms/validators, MISSING sentinel, DescriptorProfile dynamic field installation.

### REG -- Profile Registry
Name-keyed store, @decorator registration, duplicate prevention, descriptor invariants, invariant test generator.

### AUTH -- Auth System
AuthSpec base with kind literal, 10+ concrete auth modes as discriminated union, dispatch function, driver kwargs mapping.

### CACHE -- Caching
LRU cache on _get_settings, structural cache key, runtime override application via model_copy, SettingsManager named lookup.

### APP -- App Settings
AppSettings convenience class, defaults, templates, integration with caching.

## Taxonomy Summary Table

| TaxonomyID | Category Name | Concept Range | Count |
|------------|---------------|---------------|-------|
| FOUND | Foundation Concepts | 1-12 | 12 |
| BASE | Base Settings | 13-22 | 10 |
| PARAM | Settings Parameters | 23-36 | 14 |
| TEMPL | Field Templating | 37-43 | 7 |
| SECRT | Secrets Resolution | 44-55 | 12 |
| PROF | Connection Profiles | 56-70 | 15 |
| REG | Profile Registry | 71-79 | 9 |
| AUTH | Auth System | 80-98 | 19 |
| CACHE | Caching | 99-106 | 8 |
| APP | App Settings | 107-110 | 4 |
