package ai.sofia.mobile

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred device tests for crash-safe, privacy-scoped host notification ACK. */
@RunWith(AndroidJUnit4::class)
class IncomingNotificationInstrumentedTest {
    private lateinit var context: Context

    @Before fun before() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit()
    }

    @After fun after() {
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit()
    }

    @Test fun notificationPersistsAcrossSettingsRecreationBeforeLocalConsumption() {
        val initial = SecureSettings(context)
        initial.storeIncoming("notification-1", "Durable private preview")
        initial.storeIncoming("notification-1", "Duplicate must not replace original")

        val restarted = SecureSettings(context)
        assertEquals(listOf("Durable private preview"), restarted.consumeIncoming())
        assertTrue(SecureSettings(context).consumeIncoming().isEmpty())
    }

    @Test fun damagedEncryptedInboxIsPreservedRatherThanDiscardedAsEmpty() {
        val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
        assertTrue(prefs.edit().putString("incoming_messages", "corrupt-aes").commit())
        val store = SecureSettings(context)

        try {
            store.consumeIncoming()
            fail("Malformed ciphertext cannot be treated as an empty inbox")
        } catch (_: Exception) {
            // Original encrypted bytes must remain for explicit recovery.
        }
        assertEquals("corrupt-aes", prefs.getString("incoming_messages", null))
        try {
            store.storeIncoming("new-id", "New message")
            fail("Corrupt prior cache cannot be silently overwritten")
        } catch (_: Exception) {
            // A service must withhold host ACK when local retention is unsafe.
        }
        assertEquals("corrupt-aes", prefs.getString("incoming_messages", null))
    }

    @Test fun privacyAudienceResetDurablyClearsPriorEncryptedInbox() {
        val store = SecureSettings(context)
        store.storeIncoming("notification-2", "Local private message")
        store.clearIncoming()
        assertTrue(SecureSettings(context).consumeIncoming().isEmpty())
    }
}
