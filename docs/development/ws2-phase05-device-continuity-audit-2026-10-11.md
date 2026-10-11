# Workstream 2 • Phase 05 CA-5303 original-source audit

**Date:** 2026-10-11  
**Repo:** `Crazysodaman/SofiaAdaLyra`; `main` only.  
**Mode:** source audit / source coding; tests, CI, Android builds, pairing changes, live migrations and host updates deferred.

## CA-5303: device cursors, offline queue, reconnect, receipts and synchronization

**Classification: `partial_wiring`, not accepted.**

The following *production* paths already exist, not just roadmap placeholders:

- `LifelongThreadStore.visible_message_page` pages canonical Main/project original messages in bounded, authenticated per-audience SQL. `MobileCompanionGateway._canonical_history_page` returns opaque page cursors and adaptive page sizes without copying originals into a second server-side transcript.
- `MobileMainSeenStore.current/acknowledge` stores last-seen Main cursor per authenticated mobile device, privacy mode and exact paired credential generation. It checks the originally visible server message and credential hash in canonical SQLite before advancing the read receipt. The gateway composes this path through `acknowledge_main_seen`.
- Android `MainViewModel.loadMainHistory` loads recent/older pages, tracks `historyCursor` and `historyHasMore`, and persists a bounded offline Main cache through `SecureSettings.saveMainCache`, encrypted with Android Keystore AES-GCM.
- Android `SecureSettings.reserveOutbound/pendingOutbound` persists **one** unconfirmed outbound request with original text, request ID, privacy scope, server origin and token fingerprint **before** HTTP dispatch. `MainViewModel.reconcileUnconfirmed` requests server receipt status after reconnect and does not blindly replay an uncertain send or reexecute tool actions.
- `MobileCompanionGateway.chat/delivery_status` use canonical request receipts with original credential-epoch protection, stable digest, and transactionally verified status. The Android caller must explicitly discard an uncertain request before sending a different one.

## Missing original acceptance / full production gates

- No proven real-time streaming subscription across desktop, Discord, Terra and Android: periodic/manual authenticated Main fetch exists, but is **not** push-style cross-device event delivery.
- No accepted edit/correction propagation or system-wide cross-device presentation cursor policy for every supported client.
- No offline **multi-message** outgoing queue; the existing one-outstanding-request journal is intentionally conservative, and the user must reconcile uncertainty rather than auto-replay.
- No final restart, credential rotation, long-disconnect, concurrent-device and cross-audience acceptance campaign yet.
- Archived project discovery on Android and durable never-linked/withdrawn-source distinction were added in Items 77–80; those do not imply project turn **write** routing or remote archive mutation.

**Source evidence:** `src/sofia/conversation/lifelong.py`, `src/sofia/mobile/gateway.py`, `src/sofia/mobile/main_seen.py`, `mobile/android/app/src/main/java/ai/sofia/mobile/SofiaApi.kt`, `mobile/android/app/src/main/java/ai/sofia/mobile/SecureSettings.kt`, `mobile/android/app/src/main/java/ai/sofia/mobile/MainActivity.kt`.

No test/CI execution or live state changes were performed. Do not mark CA-5303 accepted or code-complete based on this audit.
