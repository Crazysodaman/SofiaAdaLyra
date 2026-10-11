# CA-4105: authenticated audience immutability independent of display name

`SocialSessionStore.bind` already refused to overwrite an existing source
session when its authenticated principal or audience differed, which is
the correct source-of-truth. The method also compared `display_name`
as though it were a cryptographic identity dimension. As a result, a
legitimate UI rename could be treated as an audience impersonation and
block old conversation continuity even though the principal and
audience remained identical.

The source binding now compares **only** principal ID, audience ID and
audience kind. It accepts a changed caller display name for the already
authenticated source session without modifying its originally persisted
display label. A request to replace or widen the audience remains denied
inside the canonical SQLite transaction. Original session/source rows are
unchanged; Main remains a separate per-owner link projection whose
per-event read checks retain the original audience.

This is a real production source correction for CA-4105, not a
cross-transport permission grant or automatic migration of history.
Regression tests authored, not run. Full historical migration and
per-event sharing acceptance remain separate partial tasks.
