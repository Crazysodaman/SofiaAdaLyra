# PKG-ENVIRONMENT | shared time, location and environmental context

**Accepted implementation update 2026-09-26. Status:** PR #110 merged the shared PKG-ENVIRONMENT foundation to `main` at `766bf21e0714c8e6b3a21d3f770f633cb4ff8b15`; PR #111 merged the narrow NWS weather/forecast provider plus durable per-machine HOST location at `2b753fdb0b6bccf3449a923fbd48cb5496d1dece`. The accepted system now includes the provider-neutral `EnvironmentSnapshot`, deterministic time/date/location/timezone/season/daylight/weather/forecast/indoor/provenance queries, explicit configured-vs-current USER/SITE/HOST semantics, persistent HOST configuration in `state/machine-locations.json` keyed by stable machine identity, bounded cognition projection, Home Assistant bridge behind `environment.home_assistant.read`, NWS transport pinned to HTTPS `api.weather.gov` behind `environment.nws.read`, runtime composition, and AVATAR consumption. Evidence includes the original **79 focused / 61 touched-regression / 27 provenance-regression** gates, reported green full suites, supervised live Ollama acceptance, later **85 NWS-focused** tests, a supervised live NWS canary against `nws:KGKY`, **96 persistence-focused** tests, and a final reported green full suite. The optional live Home Assistant canary remains pending; general browsing/search and arbitrary geocoding remain outside this acceptance.

PKG-ENVIRONMENT is package **20** in the canonical roadmap. Existing package numbers 1–19 remain unchanged.

## Ownership boundary

**ENVIRONMENT owns:** one typed, provenance-aware view of external context that other packages may consume:

- current UTC and authoritative runtime observation time,
- user/site-local timezone when explicitly configured or independently evidenced,
- configured/home location and separately modeled current location,
- hemisphere-aware season,
- sunrise/sunset and daylight state,
- current outdoor weather and forecast when a trusted provider is available,
- optional indoor environmental observations from trusted integrations such as Home Assistant,
- freshness/TTL, source, precision, confidence/quality and observation timestamp for every environmental field.

**ENVIRONMENT does not own:**

- network transport or arbitrary HTTP access: **NET** owns transport and network grants,
- Home Assistant/JMRI/service adapters: **INTEGRATE** owns adapters,
- wardrobe or avatar presentation: **AVATAR** consumes environment evidence,
- emotion/personality: **CORE/REL/INTERACT** may use environment as context but weather never deterministically creates an emotion,
- reminders/outreach: **ACT** may consume authorized environment events but ENVIRONMENT does not send messages,
- host lifecycle or polling schedules: **RUN** owns recurring execution/supervision,
- physical sensors/actuators: **BODY** owns Gaia hardware and may publish independently verified sensor observations into ENVIRONMENT,
- privacy/authorization: **SOCIAL/SAFE** scope access to location and environment evidence,
- truth certification: **VERIFY** owns acceptance evidence.

No consumer may bypass ENVIRONMENT by independently inventing, scraping, geolocating or caching its own competing "current weather/location" truth.

## Canonical model

The implementation should converge on a provider-neutral immutable projection similar to:

```python
EnvironmentSnapshot(
    observed_at=...,
    utc_time=...,
    local_time=...,
    timezone=...,
    location=...,
    season=...,
    daylight=...,
    outdoor_weather=...,
    forecast=...,
    indoor_environment=...,
    provenance=...,
    expires_at=...,
)
```

Each optional field must preserve its own source and observation time. Missing/stale data stays unknown rather than being guessed from memory, IP address, hostname, season stereotypes or model knowledge.

## Source and trust rules

1. **Clock:** existing runtime clock is the initial authoritative observation source. Host-local time is machine evidence and must not silently become the user's timezone.
2. **Configured location:** an explicit user-approved/home/site location can provide a stable coarse location and timezone anchor. It is configuration, not proof that a person/device is physically there now.
3. **Current location:** only independently evidenced device/GPS/trusted-integration data may be labeled current. IP geolocation is coarse, fallible and never silently upgraded to precise location.
4. **Season/daylight:** derive only from a known location/timezone and date using deterministic rules. Do not infer hemisphere from language or account metadata.
5. **Home Assistant:** an authorized local HA adapter may supply indoor sensors, weather entities, presence/site metadata or outdoor observations through INTEGRATE without granting Sofía general browser/search authority.
6. **Direct weather provider:** remote weather/geocoding APIs require the later separately authorized NET/web capability, explicit destination/tool scope, provider credentials where needed, bounded requests, provenance and revocation.
7. **Memory:** MEM may retain approved stable preferences/configuration and provenance, but stale weather or old location observations must never be projected as current state.

## Consumer integration matrix

| Consumer | How ENVIRONMENT helps | Boundary |
| --- | --- | --- |
| **CORE** | Current time/location/environment grounding in cognition | Evidence only; no invented current state |
| **INTERACT** | Contextual virtual-lab and conversational reactions | Environment does not imply physical sensing |
| **MEM** | Stable location/preferences and provenance | Current observations expire; no stale-current reuse |
| **SOCIAL** | Person/audience-scoped location/environment access | Precise/private location defaults restricted |
| **NET** | Transport for approved external providers | Connectivity never equals provider authorization |
| **UI** | Optional display of current environment/age/source | UI does not create truth |
| **RUN** | Refresh cadence, expiry and event scheduling | Scheduler does not reinterpret evidence |
| **OPS** | Site/timezone context for fleet nodes | Machine site is not automatically user location |
| **ACT** | Opt-in severe-weather/contextual notices | Quiet/stop/dedupe and recipient scope still apply |
| **REL / emotion** | Time-of-day/season/weather as soft conversational context | No hard-coded “rain = sad” causal rule |
| **AVATAR** | Outfit/presentation choice from time, season, temperature and conditions | AVATAR consumes snapshot; never fetches weather itself |
| **BODY** | Optional trusted physical environmental sensors | Hardware authority remains BODY/SAFE |
| **EVOLVE** | Reviewed environment preferences/config revisions | No self-approved protected location changes |
| **KNOW** | Provider/schema documentation and provenance support | Documentation is not live observation |
| **INTEGRATE** | Home Assistant and future provider adapters | Adapter outputs normalize into ENVIRONMENT |
| **SAFE** | Location privacy, provider secrets, revocation and retention policy | Precise location is sensitive operational data |
| **VERIFY** | Freshness, timezone, privacy, failover and provider-negative tests | No “current” claim without current evidence |

## Delivery stages

### ENV-0 | existing clock consolidation

- Keep `runtime_clock_snapshot()` as read-only machine-clock evidence.
- Project clock through one ENVIRONMENT interface rather than letting consumers create independent clocks.
- Preserve the existing rule that host-local time is not automatically the user's timezone.

**Exit:** deterministic tests prove UTC/local instant consistency, timezone awareness and live cognition projection with no guessed user timezone.

### ENV-1 | location, timezone, season and daylight

- Add typed configured-location and current-location evidence with source/precision metadata.
- Resolve timezone only from explicit/trusted evidence.
- Add deterministic hemisphere-aware season and sunrise/sunset/daylight calculation.
- Keep exact/current location optional and unknown by default.

**Exit:** offline tests cover northern/southern hemispheres, DST transitions, unknown location, stale evidence and configured-home-vs-current-location distinction.

### ENV-2 | provider abstraction and Home Assistant bridge

- Define provider-neutral weather/environment records.
- Normalize trusted Home Assistant weather/temperature/humidity/site evidence through INTEGRATE.
- Add refresh TTL/error states without treating provider failure as clear weather.

**Exit:** fake/local provider tests prove source identity, freshness, stale fallback labeling and no network authority escalation.

### ENV-3 | direct weather/forecast provider

A narrow NWS provider route was explicitly authorized by Sparks on 2026-09-26 without opening the general web/search gate and was accepted/merged via PR #111. It is scoped to HTTPS `api.weather.gov` and the explicit standing capability `environment.nws.read`.

- Current station conditions, feels-like, precipitation, wind, humidity and bounded forecast.
- Exact destination/redirect pinning to `api.weather.gov`, required NWS User-Agent, timeout, existing ENVIRONMENT cache TTL and provider attribution.
- Configurable weather target subject: USER, SITE, or HOST, using only explicitly configured coordinates.
- Independent configured HOST/server location so runtime location never overwrites Sparks' USER/home location.
- Preferred persistent HOST configuration is stored in Sofía's machine-location registry keyed by stable machine identity; process-local HOST environment variables remain an explicit override.
- No arbitrary browsing/search capability bundled with the weather client.
- NWS alerts remain a later ACT/ENVIRONMENT extension; this slice does not send proactive alerts.

**Exit:** focused provider/config/query/import tests, full-suite pass, and supervised live NWS canary at a pinned revision; wrong-destination, stale/outage, capability-denial and USER-vs-HOST isolation must fail safely.

### ENV-4 | shared cognition and package consumers

Project one bounded environment snapshot into cognition when relevant. Wire AVATAR, INTERACT, ACT, RUN, OPS and optional REL/emotion consumers through the shared interface. Keep environment out of unrelated turns when context budget/relevance says it is unnecessary.

**Exit:** supervised real-model tests show correct time/location/weather answers and contextual use without hallucinating unavailable fields or turning weather into fixed emotion/personality behavior.

### ENV-5 | live acceptance

Verify current environment state across restart, provider outage, timezone/DST change, stale cache, changed configured location, Home Assistant disconnection and any eventual runtime/fleet movement. Environment context must remain source-labeled and must not silently follow a process to another host as if machine location equaled user location.

## AVATAR / wardrobe contract

Wardrobe and mutable presentation may use:

- time of day,
- season/daylight,
- outdoor temperature/feels-like,
- precipitation/wind,
- indoor environment,
- current activity/context,
- Sofía's modeled presentation preferences and emotions.

Environment is **advisory evidence**, not a mandatory outfit table. Established presentation preferences, audience/privacy, renderer capability and explicit context remain higher-level constraints. Emotion may influence style but neither weather nor emotion owns AVATAR state.

## Safety and privacy

- Treat precise/current location as sensitive person/site data.
- Keep provider credentials out of model context and logs.
- Do not infer current location from remembered addresses, network ranges or machine names.
- A remote fleet host's timezone/location does not become Sparks' location.
- Public/shared outputs should default to the least precise location needed.
- Expired/stale weather must be labeled stale or unavailable rather than silently reused.
- External weather alerts or proactive messages require ACT policy and recipient/audience checks.

## Roadmap relationship

ENVIRONMENT may begin **now** with ENV-0/ENV-1 and local provider contracts. It does not change the primary release gate:

**Discord accepted → real OPS/RUN 24/7 acceptance → separately authorized general web/search.**

A trusted local Home Assistant environment source may be used before general web because it is an INTEGRATE capability, not a browser/search grant. Direct internet weather remains separately authorized.

## Implementation acceptance checklist

- [x] Existing runtime clock consolidated through ENVIRONMENT cognition projection.
- [x] Typed configured/current location with explicit subject, source, coordinates kept out of model context, optional precision, and freshness.
- [x] ZoneInfo user/site time and deterministic hemisphere-aware season/daylight.
- [x] Provider-neutral weather, forecast and indoor observations with TTL/freshness and degraded provider status.
- [x] Explicit Home Assistant entity mapping and unit normalization.
- [x] HA current-location subject is explicit/inherited, never guessed as USER.
- [x] HA observation timestamps are source-backed; missing timestamps never become "now".
- [x] HA environment reads require explicit standing capability plus credentials.
- [x] Provider arbitration prefers fresher/newer evidence instead of registration order.
- [x] Unrelated turns keep the trusted clock but omit detailed environment data and avoid provider refresh.
- [x] Deterministic direct answers cover time/date, user vs runtime location, timezone, weather, forecast, season, daylight/sunrise/sunset, indoor state, and bounded environment-source provenance.
- [x] AVATAR can consume the shared season/current-weather snapshot without fetching weather itself.
- [x] DST, hemisphere/polar daylight, stale/future evidence, provider outage, subject isolation, precision and import-boundary tests are represented in the branch test suite.
- [x] Windows acceptance venv synchronized with `python -m pip install -e .`; `tzdata 2026.4` installed and `ZoneInfo('America/Chicago')` resolved successfully on 2026-09-26.
- [x] Focused ENVIRONMENT gate passed on Windows 2026-09-26: **79 passed in 216.44s** after dependency sync and the import/provider/location/relevance fixes.
- [x] Touched regression gate passed on Windows 2026-09-26: **61 passed in 13.91s** (`runtime_clock`, configuration, cognitive context/assembler, emotional conversation integration, default provider boundary).
- [x] Current-branch full pytest suite passed on Windows 2026-09-26. Exact aggregate count was not captured in chat evidence, so no synthetic count is recorded.
- [x] Post-provenance-repair full pytest suite passed on Windows 2026-09-26. Exact aggregate count was not captured in chat evidence, so no synthetic count is recorded.
- [x] Targeted provenance regression gate passed on Windows 2026-09-26: **27 passed in 242.18s** across environment query/runtime projection/prompt tests after deterministic provenance routing repair.
- [x] Supervised live Ollama gate passed on Windows 2026-09-26: time, configured-vs-current location, season, sunrise, sunset, daylight, unavailable-weather, unrelated-prompt behavior, and deterministic environment-source provenance all behaved as intended. Provenance remained bounded and did not expose coordinates or provider credentials.
- [ ] Live Home Assistant canary only after explicit `environment.home_assistant.read` grant and configured entity IDs.
- [x] Narrow NWS focused Windows gate passed 2026-09-26: **85 passed in 249.58s** across environment config, NWS provider, factory, model, service, Home Assistant, query, prompt, runtime projection and import-boundary tests.
- [x] Post-NWS full repository `pytest -q` suite passed on Windows 2026-09-26. Exact aggregate count was not supplied in chat, so no synthetic total is recorded.
- [x] Initial supervised live NWS canary passed on Windows 2026-09-26 using an explicit temporary HOST override: runtime location answered as configured-not-current, current weather came from `nws:KGKY`, bounded forecast returned NWS periods, and provenance withheld coordinates/credentials.
- [x] Final persistence-focused Windows gate passed 2026-09-26: **96 passed in 257.76s** across durable machine-location registry/CLI/inventory projection, persistent HOST injection, ENV config/NWS/factory/model/service/Home Assistant/query/prompt/runtime projection, and import-boundary tests.
- [x] Final persistence-enabled full repository `pytest -q` suite passed on Windows 2026-09-26. Exact aggregate count was not supplied in chat, so no synthetic total is recorded.
- [ ] General web/search and arbitrary geocoding remain a later separately authorized NET/web stage.

**The accepted PR #110 + PR #111 implementation does not grant general geolocation, browser/search access, background polling, proactive alerts, or arbitrary network authority. PR #111 adds only the separately authorized narrow `api.weather.gov` weather/forecast route when `SOFIA_ENVIRONMENT_NWS_ENABLED` and `environment.nws.read` are both present. Home Assistant remains separately configured/granted.**
