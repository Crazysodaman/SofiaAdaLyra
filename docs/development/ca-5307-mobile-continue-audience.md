# CA-5307: truthful "Continue on this phone" audience presentation

The mobile server already binds each device to an authenticated
credential generation, private/standard audience and source session,
but Android had no visible indication of which session it was
continuing. Users could mistake the "Main" button for globally mirrored
Discord/desktop private history, even though source projections rightly
exclude foreign audiences.

The existing mobile gateway now supplies the exact authenticated
`audience_id` and `audience_kind` alongside the existing server
`session_id` in read-only state responses. Main history responses
likewise report their exact source audience. Both report
`cross_channel_mirroring=false`: no new cross-channel sharing is
enabled. Android shows the server-confirmed current session, audience
and explicit no-mirroring warning, and clears this presentation on
re-pairing or private/shared mode changes. The device cannot set the
audience by sending its own display label.

This is a visible, truthful device continuity cue, not full global
Main synchronization or user-approved cross-channel mirroring. An
operator-approved device must still authenticate with its unique
credential; original source-event privacy remains enforced by existing
LifelongThreadStore and SocialSessionStore checks. The client never
displays an invented server session while disconnected.

Regression cases were written, not run, and the Android client was not
built or installed. CA-5307 remains partially wired pending UX and
real-device acceptance.
