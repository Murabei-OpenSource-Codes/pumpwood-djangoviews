# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
