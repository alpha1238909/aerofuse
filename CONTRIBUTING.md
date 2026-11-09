# Contributing to AeroFuse

Thank you for helping make student hardware data more useful.

## Good first contributions

- Add a documented CSV mapping for a real, publicly shareable device log.
- Contribute a synthetic test case for a telemetry failure mode.
- Improve a unit convention or explain an assumption more clearly.

## Before opening a pull request

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Keep the public API small. A new feature should either normalize real telemetry, improve a state estimate, or make uncertainty/failure more visible. Please include a test and avoid adding a dependency unless it changes what the core can genuinely do.

## Data policy

Do not upload logs containing personal location information, private keys, or credentials. Use synthetic or permissioned data for examples and tests.
