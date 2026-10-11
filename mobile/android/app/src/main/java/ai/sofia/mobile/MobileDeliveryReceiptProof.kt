package ai.sofia.mobile

import java.io.IOException
import org.json.JSONObject

/**
 * Source-linked canonical reply acceptance. A 200 response without the
 * original host receipt is not proof that the requested turn completed.
 */
internal object MobileDeliveryReceiptProof {
    fun verify(
        response: JSONObject,
        expectedRequestId: String,
        expectedDeviceId: String,
        expectedPrivateMode: Boolean,
    ): Long {
        val receipt = response.optJSONObject("delivery_receipt")
            ?: throw IOException("Canonical delivery receipt missing; preserve original outbox")
        val mode = if (expectedPrivateMode) "private" else "standard"
        val sequence = receipt.optLong("canonical_sequence", -1L)
        if (
            receipt.optString("request_id") != expectedRequestId ||
            receipt.optString("origin_device_id") != expectedDeviceId ||
            receipt.optString("presentation_mode") != mode ||
            receipt.optString("logical_status") != "completed" ||
            receipt.optInt("credential_generation", 0) < 1 ||
            receipt.optString("server_received_at").isBlank() ||
            sequence < 1L
        ) {
            throw IOException("Canonical delivery receipt does not match request scope")
        }
        return sequence
    }
}
