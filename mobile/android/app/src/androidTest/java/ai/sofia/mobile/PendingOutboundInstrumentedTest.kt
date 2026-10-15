package ai.sofia.mobile

import android.content.Context
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.SecretKey
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
    fun offlineDraftSurvivesAndroidAppRestartWithoutRequestOrNetwork() {
        val settings = config(privateMode = true)
        val original = SecureSettings(context)
        original.saveOfflineDraft(
            settings, "Draft retained completely offline",
        )
        val restarted = SecureSettings(context)
        val draft = restarted.offlineDraft()
        assertEquals("Draft retained completely offline", draft!!.text)
        assertTrue(draft.matches(settings))
        assertEquals(null, restarted.pendingOutbound())
        assertFalse(draft.matches(config(privateMode = false)))
        assertFalse(draft.matches(config(token = "sm1_" + "b".repeat(64))))
        restarted.clearOfflineDraft()
        assertEquals(null, SecureSettings(context).offlineDraft())
    }

    @Test
    fun offlineDraftNeverPretendsCorruptedCiphertextIsAnEmptyDraft() {
        val settings = SecureSettings(context)
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().putString("offline_draft_v1", "bad-draft-aes").commit()
        try {
            settings.offlineDraft()
            fail("Corrupt draft must require an explicit owner choice")
        } catch (_: IllegalArgumentException) {
            // Expected: preserve fail-closed scope.
        }
        settings.clearOfflineDraft()
        assertEquals(null, settings.offlineDraft())
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

    @Test
    fun chatRefusesPreviouslyQueuedTurnAfterPairingOrAudienceChange() {
        val original = config()
        val store = SecureSettings(context)
        store.save(original)
        val pending = store.reserveOutbound(
            original, "Exact original offline bytes", "request-fenced-89ac",
        )
        val changed = listOf(
            original.copy(privateMode = true),
            original.copy(token = "sm1_" + "b".repeat(64)),
            original.copy(baseUrl = "https://another.example.invalid"),
        )
        for (configuration in changed) {
            store.save(configuration)
            try {
                SofiaApi(store).chat(pending)
                fail("Chat dispatched a stale durable turn under another pairing")
            } catch (_: IllegalArgumentException) {
                // No HTTP attempt: current settings cannot authorize the
                // original encrypted outbox audience or credential.
            }
            assertEquals(pending, store.pendingOutbound())
        }
    }


    @Test
    fun corruptIncomingCiphertextBlocksNewArrivalWithoutAcknowledgmentOrOverwrite() {
        val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
        val encryptedCorrupt = "not-an-aes-gcm-record"
        assertTrue(prefs.edit().putString("incoming_messages", encryptedCorrupt).commit())
        val store = SecureSettings(context)
        try {
            store.storeIncoming("notification-new", "Should not erase protected originals")
            fail("An incoming notification must not erase unreadable protected history")
        } catch (_: IllegalStateException) {
            // The caller must withhold the host ACK and retain original bytes.
        }
        assertEquals(encryptedCorrupt, prefs.getString("incoming_messages", null))
    }

    @Test
    fun structurallyCorruptAuthenticatedInboxIsNeverSilentlyConsumed() {
        val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
        val store = SecureSettings(context)
        store.storeIncoming("notification-valid", "Retain me")
        val key = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            .getKey("sofia-mobile-api-token", null) as SecretKey
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val invalidPlaintext = "[{}]".toByteArray(Charsets.UTF_8)
        val corruptRecord = Base64.encodeToString(
            cipher.iv + cipher.doFinal(invalidPlaintext),
            Base64.NO_WRAP,
        )
        assertTrue(prefs.edit().putString("incoming_messages", corruptRecord).commit())
        try {
            store.consumeIncoming()
            fail("Malformed authenticated inbox contents must not disappear")
        } catch (_: IllegalStateException) {
            // Canonical acknowledgment remains blocked; owner may inspect/discard.
        }
        assertEquals(corruptRecord, prefs.getString("incoming_messages", null))
        try {
            store.storeIncoming("notification-new", "Must not claim host delivery")
            fail("Malformed authenticated inbox must reject and preserve a new delivery")
        } catch (_: IllegalStateException) {
            // ACK must be withheld and the older authenticated bytes retained.
        }
        assertEquals(corruptRecord, prefs.getString("incoming_messages", null))
    }

}
