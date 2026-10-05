package ai.sofia.mobile

import org.junit.Assert.assertEquals
import org.junit.Test

class SensorPrivacyTest {
    @Test
    fun disabledSharingAlwaysProducesUnknownActivity() {
        assertEquals("unknown", SensorPrivacy.activity(false, 20_000, 10_000))
    }

    @Test
    fun recentMotionProducesOnlyBoundedMovingLabel() {
        assertEquals("moving", SensorPrivacy.activity(true, 20_000, 10_000))
    }

    @Test
    fun expiredMotionWindowProducesStationaryLabel() {
        assertEquals("stationary", SensorPrivacy.activity(true, 10_000, 20_000))
    }
}
