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
        initial.storeIncoming("notification-1", "Durable private preview")

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

    @Test fun protectedInboxRemainsDurableAcrossUiRecreationAndDeduplicates() {
        val store = SecureSettings(context)
        store.storeIncoming("notification-keep-1", "Never lose this private message")
        val application = context.applicationContext as android.app.Application

        val first = MainViewModel(application)
        assertEquals(1, first.messages.size)
        first.receivePending()  // Called both during init and activity creation.
        assertEquals(1, first.messages.size)
        assertEquals(1, SecureSettings(context).readIncoming().size)

        store.storeIncoming("notification-keep-2", "Second protected message")
        first.receivePending()
        assertEquals(2, first.messages.size)
        assertEquals(2, store.readIncoming().size)

        // A cold-start-style new ViewModel still finds its originals.
        val restarted = MainViewModel(application)
        assertEquals(2, restarted.messages.size)
        restarted.receivePending()
        assertEquals(2, restarted.messages.size)
        store.clearIncoming()
        assertTrue(SecureSettings(context).readIncoming().isEmpty())
    }


    @Test fun conflictingNotificationIdFailsClosedWithoutAlteringFirstReceipt() {
        val store = SecureSettings(context)
        store.storeIncoming("notice-conflict", "Original persisted delivery")
        try {
            store.storeIncoming("notice-conflict", "Different response from host")
            fail("An acknowledged notification ID must not change its original bytes")
        } catch (_: IllegalStateException) {
            // The original encrypted body is authoritative for this phone.
        }
        assertEquals(
            listOf(CachedMobileNotification("notice-conflict", "Original persisted delivery")),
            SecureSettings(context).readIncoming(),
        )
    }

    @Test fun fullInboxRefusesNewAckWithoutEvictingAnyReceivedOriginal() {
        val store = SecureSettings(context)
        for (i in 0 until 49) {
            store.storeIncoming("notice-" + i, "Exact message " + i)
        }
        val originals = store.readIncoming()
        assertEquals(49, originals.size)
        try {
            store.storeIncoming("notice-50", "Not yet durably admitted")
            fail("Full protected inbox must reject new delivery rather than discard originals")
        } catch (_: IllegalStateException) {
            // The server claim must remain unresolved and retryable.
        }
        assertEquals(originals, SecureSettings(context).readIncoming())
        // Idempotent redelivery of an already stored notice is permitted.
        store.storeIncoming("notice-0", "Exact message 0")
        assertEquals(originals, store.readIncoming())
    }


    @Test fun inboxClearRequiresTwoExplicitOwnerStepsAndKeepsUnrelatedOutbox() {
        val store = SecureSettings(context)
        store.storeIncoming("notice-saved", "Sensitive local notification")
        val app = context.applicationContext as android.app.Application
        val model = MainViewModel(app)
        assertTrue(model.hasStoredIncoming())
        assertEquals(false, model.confirmClearInbox)
        // A direct confirmation without the preceding review request is inert.
        model.clearInboxAfterConfirmation()
        assertEquals(1, store.readIncoming().size)
        model.requestClearInbox()
        assertTrue(model.confirmClearInbox)
        model.cancelClearInbox()
        assertEquals(false, model.confirmClearInbox)
        assertEquals(1, store.readIncoming().size)
        model.requestClearInbox()
        model.clearInboxAfterConfirmation()
        assertEquals(false, model.confirmClearInbox)
        assertTrue(store.readIncoming().isEmpty())
    }


    @Test fun newDeliveryDuringDeleteReviewIsNeverSilentlyDiscarded() {
        val store = SecureSettings(context)
        store.storeIncoming("before-review", "First persisted notification")
        val application = context.applicationContext as android.app.Application
        val model = MainViewModel(application)
        model.requestClearInbox()
        assertTrue(model.confirmClearInbox)
        // Same-process service and UI have different store objects.
        SecureSettings(context).storeIncoming(
            "after-review", "Arrived while the owner reviewed deletion",
        )
        model.clearInboxAfterConfirmation()
        assertEquals(false, model.confirmClearInbox)
        assertEquals(
            listOf("before-review", "after-review"),
            store.readIncoming().map { it.id },
        )
        model.requestClearInbox()
        model.clearInboxAfterConfirmation()
        assertTrue(store.readIncoming().isEmpty())
    }

}
