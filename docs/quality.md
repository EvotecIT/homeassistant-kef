# Quality qualification

KEF targets the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
through Platinum while remaining a custom integration. Qualification is incomplete.
A manifest label or passing CI does not establish an official HA rating.

The [rule ledger](quality-rules.md) tracks every rule, existing evidence, and the
next acceptance step. All rows remain open until their full contract is proven.

## Reproduce the evidence

Run the existing test environment on Linux, including WSL:

```bash
python -m pip install -e '.[test]'
ruff check .
python -m mypy --strict custom_components/kef
pytest --cov=custom_components.kef --cov-report=term-missing
```

Coverage includes the bundled reusable client. Do not exclude it to improve the
reported percentage. The current 383-test suite covers 85.5% of statements and
67.4% of branches; config flow covers 99.1% of statements and 96.2% of branches.
Full config-flow coverage and above 95% coverage throughout
the integration remain qualification targets; the current suite does not meet them.

Strict typing is a maintained development/CI gate. Dynamic vendor JSON remains
at the transport boundary; volume reads validate their integer contract before
returning data to entities.

## Verified contracts

- Actions are registered during integration setup before a speaker entry is
  ready. Invalid firmware targets raise an error without uploading a file.
  Evidence: `tests/components/kef/test_services.py`.
- An unsuccessful platform unload retains the entry's event listener. Successful
  platform unloading stops it. Evidence: `tests/components/kef/test_init.py` and
  event-loop cancellation tests in `test_coordinator.py`.
- Diagnostics redact device/discovery identifiers, private names, location,
  media metadata and artwork URLs, credentials, and opaque Wi-Fi/EQ payloads.
  Parsed model, codec, and operating-state fields remain available. Redaction
  does not mutate the coordinator snapshot or config entry.
  Evidence: `tests/components/kef/test_diagnostics.py`.
- Child entities use HA translation keys, including placeholders for per-input
  startup volumes. English labels retain their existing prefixes. HA-host tests
  cover LSX II and XIO, English fallback for an untranslated language, and existing
  entity IDs and custom names. This proves backend name resolution; installed
  frontend and upgrade qualification remain separate.
  Evidence: `tests/components/kef/test_entity_translations.py`.

These tests establish the listed contracts, not complete qualification of the
corresponding HA rules or physical speaker behavior.

## Remaining qualification

- [ ] Complete measured config-flow and integration/client coverage.
- [x] Enable strict typing across all 24 integration and bundled-client modules
  with mypy 2.4.0 and no broad import or production-code ignores.
- [ ] Audit all applicable HA rules and record evidence or rule-permitted
  exemptions, including discovery updates, reconfiguration, repairs, registry
  cleanup, concurrency, action errors, translated entities, and icons.
- [ ] Verify partial setup failures and repeated unload/reload release resources.
- [x] Run all 383 tests on HA 2025.1.0/Python 3.13 and HA 2026.9.4/Python 3.14.
- [ ] Install the published HACS artifact and upgrade from the previous stable
  version while retaining user names, entity IDs, and automation bindings.
- [ ] Record model/firmware-specific offline startup, reconnection, authentication,
  and supported-command evidence using actual devices.
- [ ] Record request rates, idle behavior, cancellation, and retained-resource
  measurements against documented budgets.

Keep model and hardware evidence in [device support](device-support.md) and
[model notes](model-notes.md). Source tests, published packages, and installed
runtime proof are separate evidence boundaries.

## Compatibility environments

CI pins HA 2025.1.0 and 2026.9.4 with matching fixture releases. Reproduce the
minimum lane with `python -m pip install -r requirements-test-minimum.txt` in a
Python 3.13 environment. The older fixture needs its compatible josepy and pycares
versions; zeroconf is installed for the legacy discovery test type.

Strict typing runs against current stable HA. The minimum lane exercises runtime
compatibility; its old discovery type lives in a different HA module. Production
imports that type only for static annotations. Beta HA versions are outside these
stable qualification lanes and require separate compatibility work.
