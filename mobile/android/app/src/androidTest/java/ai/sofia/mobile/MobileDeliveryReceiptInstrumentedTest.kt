package ai.sofia.mobile

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.IOException

/** Production Android JSON receipt checks; authored but not executed. */
@RunWith(AndroidJUnit4::class)
class MobileDeliveryReceiptInstrumentedTest {
    private fun valid() = JSONObject().put(
        "delivery_receipt", JSONObject()
            .put("request_id", "request-unique-abc")
            .put("origin_device_id", "android-owner")
            .put("presentation_mode", "standard")
            .put("credential_generation", 2)
            .put("server_received_at", "2026-10-10T12:00:00+00:00")
            .put("canonical_sequence", 9)
            .put("logical_status", "completed")
    )

    @Test
    fun exactCanonicalReceiptAuthorizesLocalOutboxAcknowledgement() {
        assertEquals(
            9L, MobileDeliveryReceiptProof.verify(
                valid(), "request-unique-abc", "android-owner", false,
            ),
        )
    }

    @Test
    fun sameHttpSuccessWithWrongAudienceOrNonceLeavesOutboxUnsettled() {
        val forged = listOf(
            valid().put("delivery_receipt", JSONObject(
                valid().getJSONObject("delivery_receipt").toString()
            ).put("request_id", "another-request")),
            valid().put("delivery_receipt", JSONObject(
                valid().getJSONObject("delivery_receipt").toString()
            ).put("canonical_sequence", 0)),
            JSONObject(),
        )
        for (reply in forged) {
            try {
                MobileDeliveryReceiptProof.verify(
                    reply, "request-unique-abc", "android-owner", false,
                )
                fail("A mismatched reply may not settle an outgoing draft")
            } catch (_: IOException) {
                // Correct: the prior durable request remains unresolved.
            }
        }
    }
}
