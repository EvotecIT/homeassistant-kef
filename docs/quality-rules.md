# Integration rule ledger

This is KEF's self-assessment against the [Home Assistant rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/),
checked on 2026-10-07. It is an implementation checklist, not an official rating.
The current index contains 54 rules. `Source verified` means the applicable
implementation contract has source and test evidence at this candidate. It does
not certify a published release or replace the artifact and hardware gates below.

`Partial` identifies incomplete implementation or focused proof. `Gap` identifies
known missing work. `Review` requires an applicability or contract audit. An
exemption needs the rule's permitted reason and product-specific evidence.

## Bronze

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-setup | Source verified | The only custom action is registered in `async_setup`. [Service tests](../tests/components/kef/test_services.py) prove registration without entries, validation errors for missing targets/unavailable runtime, successful dispatch and authentication failure handling. [Source](../custom_components/kef/__init__.py). |
| appropriate-polling | Partial | Coordinator and scan/retry options exist; document and measure normal/offline request budgets. |
| brands | Partial | Local `brand/` assets exist; verify rendered HACS/HA assets and applicable custom-integration requirements. |
| common-modules | Partial | `entity.py`, `coordinator.py`, and `kef_client/` own shared behaviour; inspect remaining adapter duplication. |
| config-flow-test-coverage | Partial | 217/219 statements (99.1%) and 78/78 branches (100%) in the full-suite coverage report. Real HA flows cover authentication/connection failures, identity mismatch, sparse discovery, IPv6-only discovery and DNS aliases. The invalid discovery-address handler remains uncovered; full flow coverage is not achieved. |
| config-flow | Partial | Manual and discovered setup exist; prove the installed artifact's UI flow. |
| dependency-transparency | Source verified | [Dependency evidence](development.md#runtime-dependencies) records bundled ownership and the OSI licenses, public PyPI releases, corresponding tags, public build/publish workflows and PyPI publisher provenance for aiohttp 3.11.11/3.14.3 and cryptography 44.0.0/48.0.1 in the minimum/current environments. Reassess when supported dependencies change; installed-artifact qualification remains separate. |
| docs-actions | Partial | `services.yaml` and automation guide exist; exercise each documented action example. |
| docs-triggers | Source verified | No custom triggers are registered. The [automation guide](automations.md#triggers-and-conditions) documents standard HA triggers and distinguishes them from the internal event queue. Source audit: manifest, integration setup and platform files. This is a documented interface, not a rule exemption. |
| docs-conditions | Source verified | No custom conditions are registered. The [automation guide](automations.md#triggers-and-conditions) explains standard HA conditions and supplies a time-trigger/template-condition example. Source audit: manifest, integration setup and platform files. This is a documented interface, not a rule exemption. |
| docs-high-level-description | Partial | README describes speaker control; reconcile it with verified model support. |
| docs-installation-instructions | Partial | README installation path exists; install the actual HACS artifact. |
| docs-removal-instructions | Source verified | [Removal instructions](configuration.md#remove-the-integration) cover entry deletion, HACS/manual uninstall, retained history/exports/backups, and unchanged device settings. Source audit found no integration-owned persistent speaker store; [unload tests](../tests/components/kef/test_init.py) cover listener cleanup. Installed removal proof remains a separate lifecycle gate. |
| entity-event-setup | Partial | Coordinator cancellation tests exist; audit every entity listener's registration and removal. |
| entity-unique-id | Partial | Entity base supplies identity; verify uniqueness and persistence across migration/reconfiguration. |
| has-entity-name | Partial | Entity base enables entity names; audit primary and child entity naming. |
| runtime-data | Source verified | The coordinator is stored in typed `KefConfigEntry.runtime_data`; all eight platforms, diagnostics and unload access that owner. [Coordinator](../custom_components/kef/coordinator.py), [setup/unload tests](../tests/components/kef/test_init.py) and [HA action tests](../tests/components/kef/test_configuration_actions.py). Setup-failure qualification remains tracked under `config-entry-unloading`. |
| test-before-configure | Partial | Config flow validates the host; cover all supported transports and failure classes. |
| test-before-setup | Partial | Real HA setup with a connection failure enters retry state without runtime data, entities, or event-listener startup. Reload after connection recovery creates entities and a successful runtime. Authentication failure starts HA reauthentication for the entry without publishing runtime data, entities, or the event listener. Recovery reload succeeds after restoring the client connection; installed-device qualification remains separate. |
| unique-config-entry | Partial | Flow duplicate checks exist; test discovered/manual and changed-address combinations. |

## Silver

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| action-exceptions | Partial | Invalid firmware target regression exists; audit validation and transport errors across actions. |
| config-entry-unloading | Partial | Failed unload preserves the event listener; successful unload stops it. Real HA tests verify two reloads preserve entity IDs, replace runtime owners, cancel old event tasks, and reset their queues. A forwarding failure enters HA setup-error state without starting the event listener; a later reload replaces the runtime owner and succeeds. A failure after the real sensor platform loads removes its registered coordinator listeners before recovery; reload uses a fresh owner. Installed-artifact qualification remains open. |
| docs-configuration-parameters | Source verified | [Options](configuration.md#options) documents all four fields, defaults, numeric ranges and entry reload behavior. Reconciled with KefOptionsFlow and const.py; [flow tests](../tests/components/kef/test_config_flow.py) cover persisted values. Installed dialog proof remains separate. |
| docs-installation-parameters | Source verified | [Setup fields](configuration.md#connect-a-speaker) documents required host, conditional password, address families, local API ports, discovery and hostname prerequisites. Reconciled with config_flow.py and the canonical client defaults. Installed onboarding remains separate. |
| entity-unavailable | Partial | Coordinator drives availability; verify offline startup, disconnect, recovery, and dependent entities. |
| integration-owner | Partial | Manifest names maintainers and issue tracker; confirm support and security-reporting paths. |
| log-when-unavailable | Review | Exercise one disconnect/reconnect cycle and inspect logs for useful, non-repeating messages. |
| parallel-updates | Source verified | All eight platforms explicitly set limits: coordinator-only sensors use 0 and writable platforms use 1. [HA multi-entity action test](../tests/components/kef/test_parallel_actions.py) verifies serialized switch writes. These are per-platform limits; minimum HA bypasses them for separate single-entity calls. Physical request-budget measurements remain a separate qualification gate. |
| reauthentication-flow | Partial | Reauth steps exist; prove credentials are replaced only after successful validation. |
| test-coverage | Gap | The measured 36cd65b baseline including the bundled client has 85.6% statement and 68.4% branch coverage. Later 401-test runs did not remeasure coverage. Several modules remain below the required threshold; tests and exclusions must reflect supported behaviour. |

## Gold

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| devices | Partial | Entity device metadata exists; verify identifiers and registry grouping on each supported backend. |
| diagnostics | Partial | Privacy and nonmutation tests pass; inspect the downloaded artifact and all supported model payloads. |
| discovery-update-info | Partial | Zeroconf update handling exists; verify address changes preserve identity and credentials. |
| discovery | Partial | Manifest advertises AirPlay discovery; verify supported model matching and unrelated-device rejection. |
| docs-data-update | Source verified | [Data updates](configuration.md#data-updates) describes polling defaults/ranges, modern event-triggered refresh, legacy polling, failure tolerance, setup retry and discovery recovery. Reconciled with coordinator.py and [coordinator tests](../tests/components/kef/test_coordinator.py). Per-model request budgets remain unmeasured. |
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
| entity-translations | Partial | Child entity translation keys and dynamic source placeholders resolve in minimum/current HA, including English fallback for French and preserved custom names/IDs on LSX II and XIO fixtures. English is the provided language; installed frontend qualification remains open. |
| exception-translations | Review | Audit user-facing action exceptions and translation keys. |
| icon-translations | Gap | Add applicable state-aware icon definitions and verify them against entity states. |
| reconfiguration-flow | Partial | Reconfigure step exists; verify identity checks, address changes, and retained settings. |
| repair-issues | Review | Identify failures requiring user intervention and implement applicable repairs without log-only dead ends. |
| stale-devices | Review | Audit registry removal and applicability for the single-device entry model. |

## Platinum

| Rule | State | Evidence and next acceptance step |
| --- | --- | --- |
| async-dependency | Partial | Bundled client uses async transports; inspect blocking calls, cancellation, and resource lifetime. |
| inject-websession | Partial | Config flow and setup inject HA's session. Loopback HTTP tests verify caller ownership, authentication error classification for reads/uploads, and decoded JSON even when session defaults differ. Remaining artifact/path qualification stays open. |
| strict-typing | Partial | mypy 2.4.0 strict checking passes all 24 production modules, including the bundled client, on HA 2026.9.4 and is enforced by CI. The standalone package includes PEP 561 markers and thin stubs re-exporting the canonical client types. An isolated wheel consumer passes strict checking and rejects an invalid argument without Home Assistant installed. CI checks this installed contract in both compatibility lanes; published-release evidence remains outstanding. |

## Qualification beyond the rule ledger

- [x] 401 tests pass on HA 2025.1.0 and HA 2026.9.4 with the same source.
- [ ] Install the published artifact and upgrade from the previous stable release.
- [ ] Verify real model/firmware behaviour, resource use, reconnection, and supported actions.
- [ ] Record release version, commit, artifact identity, environment, and evidence date.

The [quality overview](quality.md) describes the current focused proof. A completed
row must link the relevant test, artifact, or runtime evidence and state its limits.
