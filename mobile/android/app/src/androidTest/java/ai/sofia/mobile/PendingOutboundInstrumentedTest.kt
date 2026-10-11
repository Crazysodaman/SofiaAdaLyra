package ai.sofia.mobile

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Real Android Keystore and SharedPreferences proof. Authored, not executed. */
@RunWith(AndroidJUnit4::class)
class PendingOutboundInstrumentedTest {
    private lateinit var context: Context

    private fun config(
        privateMode: Boolean = false,
        token: String = "sm1_" + "a".repeat(64),
    ) = CompanionSettings(
        baseUrl = "https://test.example.invalid",
        token = token,
        privateMode = privateMode,
        proactiveNotifications = false,
        shareSensors = false,
        shareLocation = false,
        shareActivity = false,
        shareAmbient = false,
    )

    @Before
    fun before() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit()
    }

    @After
    fun after() {
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit()
    }

    @Test
    fun durableOutboxRestoresExactBytesAndRequestIdAfterNewSettingsInstance() {
        val original = SecureSettings(context)
        val settings = config(privateMode = true)
        original.save(settings)
        val first = original.reserveOutbound(
            settings, "A message after reconnect", "request-4b87b57b",
        )
        val restarted = SecureSettings(context)
        val recovered = restarted.pendingOutbound()
        assertEquals(first, recovered)
        assertTrue(recovered!!.matches(settings))
        assertEquals(
            first,
            restarted.reserveOutbound(
                settings, "A message after reconnect", "request-4b87b57b",
            ),
        )
        restarted.confirmOutbound(first.requestId)
        assertEquals(null, SecureSettings(context).pendingOutbound())
    }

    @Test
    fun existingUnconfirmedTurnCannotBeSilentlyReplacedOrSentOnOtherAudience() {
        val store = SecureSettings(context)
        val standard = config()
        val pending = store.reserveOutbound(
            standard, "Original bytes", "request-ece303cb",
        )
        assertFalse(pending.matches(config(privateMode = true)))
        assertFalse(pending.matches(config(token = "sm1_" + "b".repeat(64))))
        try {
            store.reserveOutbound(standard, "Modified bytes", "request-ece303cb")
            fail("The original durable message may have been dispatched")
        } catch (_: IllegalStateException) {
            // Expected: do not silently overwrite the prior request.
        }
        try {
            store.reserveOutbound(standard, "Original bytes", "request-changed-a9")
            fail("A reused text with a different nonce can duplicate effects")
        } catch (_: IllegalStateException) {
            // Expected.
        }
        assertEquals(pending, store.pendingOutbound())
        store.discardUnconfirmedOutbound()
        val after = store.reserveOutbound(
            standard, "User deliberately started over", "request-af7b1c9d",
        )
        assertNotEquals(pending.requestId, after.requestId)
    }

    @Test
    fun unreadableEncryptedJournalNeverLooksLikeAnEmptyOutbox() {
        val store = SecureSettings(context)
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().putString("pending_outbound_v1", "damaged-ciphertext").commit()
        try {
            store.pendingOutbound()
            fail("Damaged outbox must block automatic request replacement")
        } catch (_: IllegalArgumentException) {
            // Expected explicit recovery.
        }
        store.discardUnconfirmedOutbound()
        assertEquals(null, store.pendingOutbound())
    }
}
