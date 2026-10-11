# Sofía Android companion

This app is an authenticated mobile interface to the same Sofía runtime used by
the desktop and Discord clients. It provides chat, current mood/expression, and
individually controlled read-only phone observations. It also receives
policy-approved proactive outreach without Home Assistant. It does not create
a second identity or grant Sofía control of the phone.

## Privacy and adult/private mode

- Every phone must be individually enrolled by the host operator. Its high-entropy `sm1_` credential is stored encrypted in Android Keystore-backed app settings; only its SHA-256 verifier is persisted in canonical `sofia.db`. A credential is valid only for the matching device ID.
- **Private mode** creates an authenticated private-owner audience. When it is
  off, the host projects a safe-for-shared-screen audience and adult/private
  content fails closed.
- Adult chat and adult avatar presentation also require their durable host
  permissions in the tray settings. The phone toggle cannot grant them.
- Sensor sharing is off by default. Location, movement/steps, and ambient
  sensors have separate switches. Disabled categories are not collected.
- Raw accelerometer samples never leave the phone. They are reduced locally to
  a bounded `stationary`/`moving` observation.
- Coordinates may be stored as fresh location evidence on the host, but are
  deliberately omitted from model prompts. Sensor evidence never establishes
  identity, intent, consent, emotion, or action authority.
- Proactive notifications follow ACT quiet hours, quotas, mute/stop state,
  recipient checks, and evidence requirements. They are acknowledged only
  after Android accepts the notification for display; an interrupted claim is
  retried. The app stores unopened message bodies encrypted.
- Lock-screen previews are generic unless Private Mode and the host's separate
  adult/private external-delivery permission are both enabled. Android still
  marks the notification itself private.

## Host configuration

The endpoint starts with the desktop/tray worker when these environment
variables are present:

```text
SOFIA_MOBILE_ENABLED=true
SOFIA_MOBILE_HOST=0.0.0.0
SOFIA_MOBILE_PORT=8766
SOFIA_MOBILE_TLS_CERT=C:\path\to\fullchain.pem
SOFIA_MOBILE_TLS_KEY=C:\path\to\privkey.pem
# No SOFIA_MOBILE_TOKEN: the old shared token is retired.
```

A non-loopback binding is refused unless a TLS certificate and private key are
configured. Use a certificate for the hostname entered in the Android app and
issued by a CA the phone trusts. Do not commit credentials or TLS private keys.

### Operator-controlled per-device pairing

Install the updated Android client first. It shows **Device ID for operator
pairing** on the setup screen. On the selected canonical writer host, run the
following commands locally with owner-controlled access to the canonical
`sofia.db`. **Do not select or relocate the writer host just to pair a phone.**

```powershell
python -m sofia.mobile.pairing --state-path "C:\\path\\to\\canonical\\sofia.db" enroll --device-id "android-DEVICE_ID_FROM_APP" --owner-approved
python -m sofia.mobile.pairing --state-path "C:\\path\\to\\canonical\\sofia.db" list
python -m sofia.mobile.pairing --state-path "C:\\path\\to\\canonical\\sofia.db" revoke --device-id "android-DEVICE_ID_FROM_APP" --owner-approved
# To re-pair, issue a fresh secret. The prior secret is invalidated:
python -m sofia.mobile.pairing --state-path "C:\\path\\to\\canonical\\sofia.db" enroll --device-id "android-DEVICE_ID_FROM_APP" --rotate --owner-approved
```

Enrollment prints the new token **only once** at the operator console. Transfer
it privately to the exact device and enter it in the app's pairing-token field.
The previous shared `SOFIA_MOBILE_TOKEN` and protected `mobile-api-token`
are not accepted by the updated server. Remove old environment credentials
during approved deployment. No pairing endpoint is exposed over HTTP and an
HTTP bearer cannot enroll itself or revoke another device. Revocation takes
effect on the next authenticated HTTP request without rebooting the server.
The enrolled token is a revocable bearer, not hardware attestation: anyone
who steals it can act as that enrolled phone until revoked. Avoid copying
it into logs, screenshots, or chats. Use HTTPS and protect canonical DB ACLs.

### Recommended remote access: Cloudflare named tunnel

Keep the mobile listener on loopback and let an already-provisioned named
Cloudflare Tunnel supply public TLS:

```text
SOFIA_MOBILE_ENABLED=true
SOFIA_MOBILE_HOST=127.0.0.1
SOFIA_MOBILE_PORT=8766
# Legacy shared mobile token is NOT used.
SOFIA_CLOUDFLARE_TUNNEL_ENABLED=true
SOFIA_CLOUDFLARE_CONFIG=C:\\ProgramData\\cloudflared\\config.yml
SOFIA_CLOUDFLARE_TUNNEL=sofia-mobile
SOFIA_CLOUDFLARE_PUBLIC_URL=https://sofia.example.com
```

Configure the tunnel ingress to proxy that hostname to
`http://127.0.0.1:8766`. The public hostname goes in the Android endpoint field.
The tunnel never replaces per-device bearer authentication, private-mode policy, quiet
hours, notification controls, or adult/private delivery authority. Sofía
supervises only this fixed named tunnel; tunnel creation, DNS ownership, Access
policy, and credential provisioning remain host/operator setup.

In Sofía's tray settings, enable **private chat** and whichever adult chat or
avatar permissions you want. These permissions remain host-owned and
revocable. Adult external delivery is separate and is not enabled by the app.
Select **mobile** as the ACT delivery channel to send proactive outreach to the
phone. The app's **Allow proactive notifications** toggle is enabled by
default and works independently of sensor sharing.

## Build and install

Open `mobile/android` in Android Studio, or run:

```text
./gradlew testDebugUnitTest assembleDebug
```

The debug APK is written to
`app/build/outputs/apk/debug/app-debug.apk`. Install it on the phone, enter the
HTTPS endpoint and the matching token, then choose the sensor categories you
want to share. Android shows a persistent notification while the companion
connection is active.

## Lifelong Main history (current production source path)

The Android client provides a **Main history** view with an **Older** page
action. History comes from the existing canonical conversation store through
`POST /v1/mobile/main/page`, protected by the caller's individually enrolled mobile credential.

Request body: `{"device_id":"android-...","private_mode":false,"before":null,"limit":30}`.
On subsequent pages, pass `next_before` from the previous response as
`before`. Results contain source message ID, role, content, original and
thread-link timestamps, `has_more`, and the caller's audience kind.

**Important:** Private Main history requires the separate host private-chat
grant, not merely the phone toggle. Denied private reads return HTTP 403.
This is an audience-scoped projection, not a general
cross-channel transcript. Private-mode and standard-mode sessions are distinct,
and switching modes clears onscreen messages/drafts/history. A former private
conversation never automatically appears in the standard Main view. Main
retrieval cannot grant actions, touch Fleet, or deliver protected content.
