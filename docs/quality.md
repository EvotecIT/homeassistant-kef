# Quality qualification

KEF targets the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
through Platinum while remaining a custom integration. Qualification is incomplete.
A manifest label or passing CI does not establish an official HA rating.

The [rule ledger](quality-rules.md) tracks every rule, existing evidence, and the
next acceptance step. Source-verified rows identify proven implementation contracts; release, installed
artifact and device qualification remain separate.

## Reproduce the evidence

Run the existing test environment on Linux, including WSL:

```bash
python -m pip install -e '.[test]'
ruff check .
python -m mypy --strict custom_components/kef
pytest --cov=custom_components.kef --cov-branch --cov-report=term-missing
```

Coverage includes the bundled reusable client. Do not exclude it to improve the
reported percentage. The current suite passes all 430 tests on HA 2025.1.0 and
HA 2026.9.4. Ruff and strict typing pass on the current lane.

The measured production baseline at `03e03c8` contains 430 tests and covers
86.99% of statements (2647/3043) and 70.08% of branches (506/722) on HA 2026.9.4.
The current full-suite config-flow measurement covers all 216 statements and
78 branches (100%). Both supported HA discovery producers supply parsed IP
addresses; the unreachable invalid-address exception handler has been removed.
Above 95% coverage throughout the integration remains a qualification target.

Strict typing is a maintained development/CI gate. Dynamic vendor JSON remains
at the transport boundary; volume reads validate their integer contract before
returning data to entities.

## Verified contracts

- Legacy GET replies and SET acknowledgements can arrive across TCP reads
  without resending the command. GET replies wait for a complete four-byte
  packet at a packet boundary and match the requested query; a value equal to the packet marker
  remains data. The response remains limited to 100 bytes and one request
  deadline. Loopback tests cover incomplete/unrelated replies, combined packets,
  the mute bit, deadline expiry, cancellation, and connection closure.
  Evidence: `tests/test_legacy_transport.py`. Actual legacy model and firmware
  packet behavior still needs separate qualification.

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

- [x] Achieve full config-flow statement and branch coverage.
- [ ] Complete integration/client coverage above the required threshold.
- [x] Enable strict typing across all 24 integration and bundled-client modules
  with mypy 2.4.0 and no broad import or production-code ignores.
- [ ] Audit all applicable HA rules and record evidence or rule-permitted
  exemptions, including discovery updates, reconfiguration, repairs, registry
  cleanup, concurrency, action errors, translated entities, and icons.
- [x] Verify repeated HA reloads preserve entity IDs and cancel/reset each old event listener, including final unload.
- [x] Verify a platform-forwarding failure starts no event listener and recovers with a fresh runtime on reload.
- [x] Verify offline startup enters retry state without publishing runtime data or entities and recovers on reload.
- [x] Verify cleanup after a real sensor platform loads and the remaining setup fails, including recovery with a fresh owner.
- [x] Verify authentication failure starts HA reauthentication without publishing entities or runtime data.
- [ ] Verify installed-artifact lifecycle behavior.
- [x] Run all 430 tests on HA 2025.1.0/Python 3.13 and HA 2026.9.4/Python 3.14.
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
