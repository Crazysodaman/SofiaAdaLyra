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

Configure the host independently:

```powershell
$env:SOFIA_ENVIRONMENT_HOST_LOCATION_LABEL="Artemis"
$env:SOFIA_ENVIRONMENT_HOST_TIMEZONE="America/Chicago"
$env:SOFIA_ENVIRONMENT_HOST_LATITUDE="<server/site latitude>"
$env:SOFIA_ENVIRONMENT_HOST_LONGITUDE="<server/site longitude>"
```

`Where am I?` remains a USER-location question.

`Where are you?` may use the separate HOST configuration and must not reuse the USER location as evidence for the runtime host.

Environment configuration is loaded when Sofía starts. To update a server location, change that host's `SOFIA_ENVIRONMENT_HOST_*` values and restart the Sofía process/service. A future OPS/RUN integration may populate host/site evidence from enrolled fleet metadata, but this candidate does not infer location from hostname, IP address, network range, or account metadata.

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

```powershell
$env:SOFIA_ENVIRONMENT_HOST_LOCATION_LABEL="Artemis"
$env:SOFIA_ENVIRONMENT_HOST_TIMEZONE="America/Chicago"
$env:SOFIA_ENVIRONMENT_HOST_LATITUDE="<LAT>"
$env:SOFIA_ENVIRONMENT_HOST_LONGITUDE="<LON>"

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
- automatic host movement/location inference,
- NWS alert-to-ACT delivery,
- background polling beyond the existing ENVIRONMENT refresh behavior,
- replacing Home Assistant indoor sensors.

Home Assistant and NWS may coexist. Provider arbitration remains freshness-based rather than registration-order based.
