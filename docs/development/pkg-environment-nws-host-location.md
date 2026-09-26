# PKG-ENVIRONMENT | NWS weather and runtime-host location

**Status:** implementation candidate on `feature/pkg-environment-nws-host-location`. Do not treat this document as acceptance evidence until the Windows focused/full-suite and supervised live canary gates pass.

## Purpose

This extension keeps three concepts separate:

1. **User/home location**: stable configured context for Sparks. It is not proof of current physical location.
2. **Runtime-host location**: stable configured context for the machine currently running Sofía, such as Artemis. It is not proof the machine is physically there now.
3. **Weather target**: the configured USER, SITE, or HOST location whose coordinates PKG-ENVIRONMENT sends to the narrow National Weather Service provider.

Moving Sofía to another host must never silently move Sparks. Updating a host's location must never overwrite the configured user location.

## User/home location

```powershell
$env:SOFIA_ENVIRONMENT_LOCATION_LABEL="Home"
$env:SOFIA_ENVIRONMENT_TIMEZONE="America/Chicago"
$env:SOFIA_ENVIRONMENT_LATITUDE="<coarse latitude>"
$env:SOFIA_ENVIRONMENT_LONGITUDE="<coarse longitude>"
$env:SOFIA_ENVIRONMENT_LOCATION_SUBJECT="user"
```

Coordinates are internal evidence and are withheld from model-facing environment prompts.

## Runtime-host/server location

The preferred persistent path stores host location inside Sofía's machine state, keyed by the machine's stable discovered ID:

```powershell
python -m sofia.machine.location_cli set-local \
  --label "Home Lab" \
  --timezone "America/Chicago" \
  --latitude <LAT> \
  --longitude <LON>
```

This writes `state/machine-locations.json`. On the next Sofía start, composition discovers the current machine identity and injects that record into PKG-ENVIRONMENT as HOST configuration.

A known remote machine can be configured from an inventory-bearing installation:

```powershell
python -m sofia.machine.location_cli set-known \
  --hostname "Artemis" \
  --label "Home Lab" \
  --timezone "America/Chicago" \
  --latitude <LAT> \
  --longitude <LON>
```

Use `--machine-id` when a hostname is ambiguous. `python -m sofia.machine.location_cli list` lists configured machine labels/timezones without coordinates.

`Where am I?` remains a USER-location question.

`Where are you?` may use the separate HOST configuration and must not reuse the USER location as evidence for the runtime host.

Environment configuration is loaded when Sofía starts, so restart the Sofía process/service after changing a machine location. The machine-location registry is stable configuration, not proof of current physical presence.

For testing/emergency override only, process-local `SOFIA_ENVIRONMENT_HOST_LOCATION_LABEL/TIMEZONE/LATITUDE/LONGITUDE` variables still work and take precedence over the persistent machine record.

This candidate does not infer location from hostname, IP address, network range, or account metadata. A later OPS/RUN fleet layer may replicate/manage this same machine configuration across hosts.

## NWS weather

The provider is explicitly enabled:

```powershell
$env:SOFIA_ENVIRONMENT_NWS_ENABLED="true"
$env:SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT="user"
$env:SOFIA_ENVIRONMENT_NWS_USER_AGENT="SofiaAdaLyra/1.0"
```

Set `SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT` to `host` if outdoor weather should follow the configured runtime-host/server coordinates instead.

NWS requires coordinates for the selected subject.

### Explicit capability

NWS network access is not a general browser/search grant. It requires:

```text
environment.nws.read
```

For a PowerShell session:

```powershell
$caps = @(
    $env:SOFIA_ALLOWED_CAPABILITIES -split ',' |
    Where-Object { $_.Trim() }
)
if ($caps -notcontains "environment.nws.read") {
    $caps += "environment.nws.read"
}
$env:SOFIA_ALLOWED_CAPABILITIES = $caps -join ","
```

The NWS client is pinned to HTTPS `api.weather.gov`. Off-host URLs and off-host redirects are rejected.

No NWS API key is used. The provider sends the required application User-Agent.

## Data flow

```text
configured USER or HOST coordinates
            |
            v
      api.weather.gov
            |
            v
NwsEnvironmentProvider
            |
            v
 EnvironmentSnapshot
       |      |
       |      +--> bounded forecast
       +---------> current station weather
            |
            v
CORE / INTERACT / AVATAR / later ACT-RUN consumers
```

The provider obtains the NWS point metadata, the point's forecast endpoint, and nearby observation stations. It prefers a current station observation and otherwise preserves stale evidence as stale rather than relabeling it current.

A forecast endpoint outage does not erase an otherwise valid current station observation.

## Example: Artemis weather

First persist Artemis' location in Sofía's machine registry (run locally on Artemis with `set-local`, or use `set-known` from a state instance that already knows Artemis). Then enable the narrow NWS route:

```powershell
$env:SOFIA_ENVIRONMENT_NWS_ENABLED="true"
$env:SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT="host"
$env:SOFIA_ENVIRONMENT_NWS_USER_AGENT="SofiaAdaLyra/1.0"

$caps = @(
    $env:SOFIA_ALLOWED_CAPABILITIES -split ',' |
    Where-Object { $_.Trim() }
)
if ($caps -notcontains "environment.nws.read") {
    $caps += "environment.nws.read"
}
$env:SOFIA_ALLOWED_CAPABILITIES = $caps -join ","

python -m sofia
```

Expected checks:

```text
Where are you?
What's the weather?
What's the forecast?
Explain your current environment context sources.
```

The location answer must label Artemis as configured runtime-host location, not current physical proof. Weather/forecast must identify an `nws:<station>` source when current NWS station evidence is available.

## Not included in this slice

- arbitrary web browsing/search,
- IP geolocation,
- automatic host movement/location inference beyond stable machine-ID lookup,
- NWS alert-to-ACT delivery,
- background polling beyond the existing ENVIRONMENT refresh behavior,
- replacing Home Assistant indoor sensors.

Home Assistant and NWS may coexist. Provider arbitration remains freshness-based rather than registration-order based.
