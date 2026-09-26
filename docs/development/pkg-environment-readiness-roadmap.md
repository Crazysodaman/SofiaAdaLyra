# PKG-ENVIRONMENT | shared time, location and environmental context

**Implementation candidate update 2026-09-25. Status:** `feature/pkg-environment` now contains the offline ENV-0/ENV-1 core, provider-neutral snapshot/freshness model, deterministic direct queries, Home Assistant provider bridge, bounded cognition projection, runtime composition, and AVATAR environment adapter. The implementation also requires an explicit standing `environment.home_assistant.read` grant before HA environment reads, does not refresh remote providers on unrelated turns, preserves location subjects/precision, and fails closed on missing provider timestamps. Tests are authored on the branch; this document does **not** claim they have executed or passed until Windows/package/full-suite evidence is recorded. Direct internet weather/geocoding remains intentionally unimplemented behind the later NET/web gate.

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

This stage waits for the separately authorized general-web/network gate unless an already-approved narrow provider route is explicitly granted earlier.

- Current conditions, feels-like, precipitation, wind, humidity and bounded forecast.
- Exact destination allowlist, credentials handling, timeout/retry/rate limits, cache TTL and provider attribution.
- No arbitrary browsing/search capability bundled with the weather client.

**Exit:** live provider test at a pinned revision plus wrong-destination, expired/stale, outage, credential and revocation negatives.

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
- [x] Deterministic direct answers cover time/date, user vs runtime location, timezone, weather, forecast, season, daylight/sunrise/sunset and indoor state.
- [x] AVATAR can consume the shared season/current-weather snapshot without fetching weather itself.
- [x] DST, hemisphere/polar daylight, stale/future evidence, provider outage, subject isolation, precision and import-boundary tests are represented in the branch test suite.
- [ ] Sync project dependencies in the active venv (`python -m pip install -e .`) before Windows acceptance. PKG-ENVIRONMENT adds the declared `tzdata` dependency because Windows does not normally ship an IANA ZoneInfo database.
- [x] Focused ENVIRONMENT gate passed on Windows 2026-09-26: **79 passed in 216.44s** after dependency sync and the import/provider/location/relevance fixes.
- [x] Touched regression gate passed on Windows 2026-09-26: **61 passed in 13.91s** (`runtime_clock`, configuration, cognitive context/assembler, emotional conversation integration, default provider boundary).
- [x] Current-branch full pytest suite passed on Windows 2026-09-26. Exact aggregate count was not captured in chat evidence, so no synthetic count is recorded.
- [ ] Supervised live Ollama checks for direct environment answers and relevant/unrelated prompt behavior.
- [ ] Live Home Assistant canary only after explicit `environment.home_assistant.read` grant and configured entity IDs.
- [ ] Direct internet weather/geocoding remains a later separately authorized NET/web stage.

**This implementation candidate does not itself grant general geolocation, browser/search access, background polling, proactive alerts, or direct internet weather. Home Assistant data is available only when explicitly configured and separately granted.**
