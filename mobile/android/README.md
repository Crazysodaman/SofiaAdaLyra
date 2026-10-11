# Sofía Android companion

This app is an authenticated mobile interface to the same Sofía runtime used by
the desktop and Discord clients. It provides chat, current mood/expression, and
individually controlled read-only phone observations. It also receives
policy-approved proactive outreach without Home Assistant. It does not create
a second identity or grant Sofía control of the phone.

## Privacy and adult/private mode

- The phone must authenticate with a 32–512 character bearer token.
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
SOFIA_MOBILE_TOKEN=<a randomly generated 32+ character secret>
```

A non-loopback binding is refused unless a TLS certificate and private key are
configured. Use a certificate for the hostname entered in the Android app and
issued by a CA the phone trusts. Do not commit the token or TLS private key.
The token can alternatively be stored as the host's protected
`mobile-api-token` secret.

### Recommended remote access: Cloudflare named tunnel

Keep the mobile listener on loopback and let an already-provisioned named
Cloudflare Tunnel supply public TLS:

```text
SOFIA_MOBILE_ENABLED=true
SOFIA_MOBILE_HOST=127.0.0.1
SOFIA_MOBILE_PORT=8766
SOFIA_MOBILE_TOKEN=<a randomly generated 32+ character secret>
SOFIA_CLOUDFLARE_TUNNEL_ENABLED=true
SOFIA_CLOUDFLARE_CONFIG=C:\\ProgramData\\cloudflared\\config.yml
SOFIA_CLOUDFLARE_TUNNEL=sofia-mobile
SOFIA_CLOUDFLARE_PUBLIC_URL=https://sofia.example.com
```

Configure the tunnel ingress to proxy that hostname to
`http://127.0.0.1:8766`. The public hostname goes in the Android endpoint field.
The tunnel never replaces the mobile bearer token, private-mode policy, quiet
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
`POST /v1/mobile/main/page`, protected by the normal mobile bearer token.

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
