# Change Log

## [Unreleased]

---

## [0.0.2] - 2023-08-11

### Changed
- `Loader` and `Unloader` now have a second generic argument for the type(s) that they deal with. Can be `Any`.
 
### Fixed
- Datetime parsing in Python 3.10
- Type checking for `JsonScalarConverter`
- `DictConverter` is annotated as only converting dictionaries with string keys

## [0.0.1] - 2023-03-03

Initial release