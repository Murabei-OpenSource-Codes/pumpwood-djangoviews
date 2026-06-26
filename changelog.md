# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.11-b.0] - 2026-06-26

### Added
- Build package metadata through ``pyproject_template.toml`` and Poetry.

### Changed
- ``build.sh`` uses ``poetry build`` instead of setuptools ``setup.py``.
- Correct ``pyproject`` name, dependencies, and package path for
  ``pumpwood-djangoviews`` (previously copied from
  ``pumpwood-communication``).

### Removed
- ``setup.py`` and ``setup_template.py`` build templates.

## [1.5.10] - 2026-06-26

### Added
- ``fill_options`` and ``cls_fields_options`` expose a ``default`` key
  per field, mapped to pumpwood-communication sentinel markers
  (``**missing**``, ``**autoincrement**``, ``**now**``, ``**today**``).
- README section documenting fill_options default behaviour.

### Changed
- ``AuxFillOptions`` resolves Django model and DRF serializer defaults,
  including ``auto_now``, ``auto_now_add``, and callable defaults such as
  ``timezone.now``.

### Removed
- No Removes

## [1.5.9] - 2026-02-19

### Added
- ``AuxFillOptions`` module for fill_options end-point metadata.
- Serializers split into ``serializers/`` package with local and
  microservice field modules.

### Changed
- Use pumpwood types for correct serialization of fill_options.

### Removed
- Monolithic ``serializers.py`` and ``views.py`` modules (replaced by
  packages).

## [1.5.8] - 2026-02-14

### Added
- ``ActionReturnFile`` support for action end-points that return files.
- ``openpyxl>=3.1.5`` dependency.
- ``views/`` package: ``simple.py``, ``data.py``, and ``aux/`` modules.

### Changed
- Refactor action return type extraction for file and list annotations.

### Removed
- No Removes

## [1.5.7] - 2026-01-13

### Added
- No adds.

### Changed
- Remove debug ``print`` from save view.

### Removed
- No Removes

## [1.5.6] - 2026-01-13

### Added
- No adds.

### Changed
- Treat ``exclude_dict=None`` as empty dict on list end-point.
- Avoid mutable default arguments in ``filter_by_dict``.

### Removed
- No Removes

## [1.5.5] - 2025-11-28

### Added
- No adds.

### Changed
- Remove debug ``print`` calls from fill_options microservice loop.

### Removed
- No Removes

## [1.5.4] - 2025-11-27

### Added
- ``is_superuser`` as a valid action permission role.
- ``help_text`` in ``MicroserviceRelatedField`` fill_options metadata.

### Changed
- No changes.

### Removed
- No Removes

## [1.5.3] - 2025-09-16

### Added
- Add cache to foreign key fields.

### Changed
- No changes.

### Removed
- No Removes

## [1.5.2] - 2025-02-24

### Added
- Use orjson for loading and dumping at rest end-point using
  `PumpwoodJSONRenderer` and `PumpwoodJSONParser`.

### Changed
- No changes.

### Removed
- No Removes

## [1.5.X] - 2025-02-24

### Added
- Allow pass the Django request as argument of actions.

### Changed
- No changes.

### Removed
- No Removes

## [1.4.2] - 2025-02-24

### Added
- No adds.

### Changed
- Fix: add context to serializer at save view.

### Removed
- No Removes

## [1.4.1] - 2025-02-24

### Added
- Cache data at MicroserviceRelatedField, reducing in request serialization
  time for same object.

### Changed
- No changes.

### Removed

- No Removes

## [1.3.1] - 2025-02-13

### Added

- No adds.

### Changed
- Bug fix, aggregate was not using base_query.

### Removed

- No Removes


## [1.3.0] - 2025-02-13

### Added

- No adds.

### Changed
- Aggregation end-point: Permit use of aggregate end-points without passing
  group by columns. This results in aggregation of the role table, permitting
  count the number of all table rows.

### Removed

- No Removes
