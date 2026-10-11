package ai.sofia.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

/** CA-6304/6306 typed failure classification, authored but not executed. */
class MobileTransportFailureTest {
    @Test
    fun conflictPreservesCanonicalUncertaintyInsteadOfClaimingFailure() {
        val conflict = SofiaHttpFailure(
            409, "delivery_conflict_or_uncertain",
        )
        assertEquals(409, conflict.statusCode)
        assertEquals("delivery_conflict_or_uncertain", conflict.serverCode)
        assertFalse(conflict.message.orEmpty().contains("sm1_"))
    }

    @Test
    fun deviceRevocationIsDistinctFromHostConsentDenial() {
        val revoked = SofiaHttpFailure(401, "unauthorized")
        val denied = SofiaHttpFailure(403, "forbidden")
        assertEquals(401, revoked.statusCode)
        assertEquals(403, denied.statusCode)
    }
}
