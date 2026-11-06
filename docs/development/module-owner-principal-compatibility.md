# Module owner principal compatibility

The module command boundary accepts SAFE's verified owner principal projection
(`person:sparks`) after consuming exact authenticated approval evidence. Legacy
`Sparks` receipt encoding remains supported by SAFE. New lifecycle receipts use
the stable principal ID for attribution; existing receipt history is untouched.

Module settings accepts the canonical principal ID and retains the historical
`principal:sparks` request encoding. The exact request principal and audience
remain included in the consumed approval fingerprint; aliases cannot replay an
approval against a different request. Neither label authorizes an operation
without the independently verified one-time approval.

The Core-free host receipt consumer uses the same principal projection and
records the stable actor in its existing audit chain. This change does not alter
its remote receipt-import trust boundary or implement arbitrary owner enrollment.
It also does not complete the remaining Platform-wide principal migration.
