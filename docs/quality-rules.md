# Integration rule ledger

This is KEF's self-assessment against the [Home Assistant rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/),
checked on 2026-10-05. It is an implementation checklist, not an official rating.
The current index contains 54 rules. Every row stays open until the complete
applicable contract has evidence; a source pointer alone is not a pass.

`Partial` identifies existing implementation or focused proof. `Gap` identifies
known missing work. `Review` requires an applicability or contract audit. An
exemption needs the rule's permitted reason and product-specific evidence.

## Bronze

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-setup | Partial | Setup registration and invalid target tests in `test_services.py`; audit every action failure path. |
| appropriate-polling | Partial | Coordinator and scan/retry options exist; document and measure normal/offline request budgets. |
| brands | Partial | Local `brand/` assets exist; verify rendered HACS/HA assets and applicable custom-integration requirements. |
| common-modules | Partial | `entity.py`, `coordinator.py`, and `kef_client/` own shared behaviour; inspect remaining adapter duplication. |
| config-flow-test-coverage | Gap | `test_config_flow.py` exists; reach full measured flow coverage without excluding error paths. |
| config-flow | Partial | Manual and discovered setup exist; prove the installed artifact's UI flow. |
| dependency-transparency | Review | Document bundled client ownership, transport, and requirements from the shipped manifest. |
| docs-actions | Partial | `services.yaml` and automation guide exist; exercise each documented action example. |
| docs-triggers | Review | Audit custom trigger support and document supported automation usage or applicability. |
| docs-conditions | Review | Audit custom condition support and document supported automation usage or applicability. |
| docs-high-level-description | Partial | README describes speaker control; reconcile it with verified model support. |
| docs-installation-instructions | Partial | README installation path exists; install the actual HACS artifact. |
| docs-removal-instructions | Review | Verify entry removal and HACS uninstall guidance, including retained data. |
| entity-event-setup | Partial | Coordinator cancellation tests exist; audit every entity listener's registration and removal. |
| entity-unique-id | Partial | Entity base supplies identity; verify uniqueness and persistence across migration/reconfiguration. |
| has-entity-name | Partial | Entity base enables entity names; audit primary and child entity naming. |
| runtime-data | Partial | Entry owns coordinator in `runtime_data`; verify partial-setup and unload ownership. |
| test-before-configure | Partial | Config flow validates the host; cover all supported transports and failure classes. |
| test-before-setup | Partial | Setup refreshes the coordinator; verify retry/authentication failure behaviour. |
| unique-config-entry | Partial | Flow duplicate checks exist; test discovered/manual and changed-address combinations. |

## Silver

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-exceptions | Partial | Invalid firmware target regression exists; audit validation and transport errors across actions. |
| config-entry-unloading | Partial | Failed unload preserves event listener; successful unload stops it. Prove repeated reload and setup-failure cleanup. |
| docs-configuration-parameters | Partial | Configuration guide exists; reconcile all options, defaults, ranges, and effects. |
| docs-installation-parameters | Partial | Configuration guide exists; reconcile setup fields, credentials, and network prerequisites. |
| entity-unavailable | Partial | Coordinator drives availability; verify offline startup, disconnect, recovery, and dependent entities. |
| integration-owner | Partial | Manifest names maintainers and issue tracker; confirm support and security-reporting paths. |
| log-when-unavailable | Review | Exercise one disconnect/reconnect cycle and inspect logs for useful, non-repeating messages. |
| parallel-updates | Gap | Platform concurrency limits are not explicitly declared; select and test limits against client serialization. |
| reauthentication-flow | Partial | Reauth steps exist; prove credentials are replaced only after successful validation. |
| test-coverage | Gap | Current measured integration/client coverage is 82%; all applicable modules must meet the rule. |

## Gold

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| devices | Partial | Entity device metadata exists; verify identifiers and registry grouping on each supported backend. |
| diagnostics | Partial | Privacy and nonmutation tests pass; inspect the downloaded artifact and all supported model payloads. |
| discovery-update-info | Partial | Zeroconf update handling exists; verify address changes preserve identity and credentials. |
| discovery | Partial | Manifest advertises AirPlay discovery; verify supported model matching and unrelated-device rejection. |
| docs-data-update | Review | Describe polling, event updates, retry timing, and expected state delays. |
| docs-examples | Partial | Automation guide exists; validate examples against current entities/actions. |
| docs-known-limitations | Partial | Model notes exist; reconcile protocol and feature restrictions with evidence. |
| docs-supported-devices | Partial | Device support guide exists; distinguish tested hardware from protocol-based expectations. |
| docs-supported-functions | Partial | Feature checklist exists; reconcile platforms and per-model capability gating. |
| docs-troubleshooting | Review | Cover connection, authentication, discovery, diagnostics, and recovery with actionable steps. |
| docs-use-cases | Partial | Automation examples exist; verify complete user workflows. |
| dynamic-devices | Review | Determine applicability for one-speaker-per-entry ownership and document the rule-permitted exemption if appropriate. |
| entity-category | Partial | Entity metadata exists; audit configuration and diagnostic categories across platforms. |
| entity-device-class | Partial | Sensor metadata exists; audit classes, units, and state classes across models. |
| entity-disabled-by-default | Partial | Diagnostic feature gating exists; audit noisy or rarely useful entities and user opt-in behaviour. |
| entity-translations | Gap | Complete translated entity names and verify fallback behaviour in the HA host. |
| exception-translations | Review | Audit user-facing action exceptions and translation keys. |
| icon-translations | Gap | Add applicable state-aware icon definitions and verify them against entity states. |
| reconfiguration-flow | Partial | Reconfigure step exists; verify identity checks, address changes, and retained settings. |
| repair-issues | Review | Identify failures requiring user intervention and implement applicable repairs without log-only dead ends. |
| stale-devices | Review | Audit registry removal and applicability for the single-device entry model. |

## Platinum

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| async-dependency | Partial | Bundled client uses async transports; inspect blocking calls, cancellation, and resource lifetime. |
| inject-websession | Partial | Config flow uses HA's session; verify injection and ownership in every HTTP client creation path. |
| strict-typing | Partial | mypy 2.4.0 strict checking passes all 25 production modules, including the bundled client, on HA 2026.9.3. CI enforces it; minimum-version and release-scoped proof remain open. |

## Qualification beyond the rule ledger

- [ ] Test the declared minimum and current stable HA versions with the same candidate.
- [ ] Install the published artifact and upgrade from the previous stable release.
- [ ] Verify real model/firmware behaviour, resource use, reconnection, and supported actions.
- [ ] Record release version, commit, artifact identity, environment, and evidence date.

The [quality overview](quality.md) describes the current focused proof. A completed
row must link the relevant test, artifact, or runtime evidence and state its limits.
