package ai.sofia.mobile

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred Android Keystore-backed offline Main history acceptance. */
@RunWith(AndroidJUnit4::class)
class OfflineMainCacheInstrumentedTest {
    private lateinit var context: Context

    private fun config(
        privateMode: Boolean = false,
        token: String = "sm1_" + "a".repeat(64),
        url: String = "https://canonical.example.invalid",
    ) = CompanionSettings(
        baseUrl = url, token = token, privateMode = privateMode,
        proactiveNotifications = false, shareSensors = false,
        shareLocation = false, shareActivity = false, shareAmbient = false,
    )

    private fun page(privateMode: Boolean = false) = JSONObject()
        .put(
            "audience_id",
            if (privateMode) "mobile:private:device-digest"
            else "mobile:standard:device-digest",
        )
        .put("audience_kind", if (privateMode) "private" else "shared")
        .put("messages", JSONArray().put(JSONObject()
            .put("role", "user")
            .put("content", "Original recent Main message")))

    @Before fun before() {
        context = ApplicationProvider.getApplicationContext()
        assertTrue(context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit())
    }

    @After fun after() {
        context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
            .edit().clear().commit()
    }

    @Test fun encryptedMainCacheSurvivesRestartButNeverChangesAudience() {
        val first = SecureSettings(context)
        first.saveMainCache(config(), page())
        val restarted = SecureSettings(context)
        val snapshot = restarted.cachedMainPage(config())
        assertEquals(
            "Original recent Main message",
            snapshot!!.getJSONArray("messages").getJSONObject(0).getString("content"),
        )
        assertNull(restarted.cachedMainPage(config(privateMode = true)))
        assertNull(restarted.cachedMainPage(config(token = "sm1_" + "b".repeat(64))))
        assertNull(restarted.cachedMainPage(config(url = "https://different.invalid")))
        restarted.clearMainCache()
        assertNull(SecureSettings(context).cachedMainPage(config()))
    }

    @Test fun forgedCrossAudiencePageCannotBeCached() {
        val store = SecureSettings(context)
        try {
            store.saveMainCache(config(privateMode = true), page(privateMode = false))
            fail("Never accept a shared audience as private offline evidence")
        } catch (_: IllegalArgumentException) {
            // Required.
        }
        assertNull(store.cachedMainPage(config(privateMode = true)))
    }

    @Test fun corruptedEncryptedMainIsPreservedForExplicitOwnerDiscard() {
        val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
        assertTrue(prefs.edit()
            .putString("offline_main_page_v1", "unreadable-main-cache").commit())
        val store = SecureSettings(context)
        try {
            store.cachedMainPage(config())
            fail("Encrypted corruption must never be treated as empty history")
        } catch (_: IllegalArgumentException) {
            // Stored bytes remain for explicit recovery or local disposal.
        }
        assertEquals(
            "unreadable-main-cache",
            prefs.getString("offline_main_page_v1", null),
        )
        store.clearMainCache()
        assertNull(store.cachedMainPage(config()))
    }

    @Test fun offlineFallbackOnlyPermitsNetworkFailures() {
        assertTrue(isOfflineNetworkFailure(java.net.UnknownHostException("offline")))
        assertTrue(isOfflineNetworkFailure(java.net.ConnectException("refused")))
        assertTrue(isOfflineNetworkFailure(java.net.SocketTimeoutException("timed out")))
        assertFalse(isOfflineNetworkFailure(SofiaHttpFailure(403, "forbidden")))
        assertFalse(isOfflineNetworkFailure(SofiaHttpFailure(401, "unauthorized")))
        assertFalse(isOfflineNetworkFailure(javax.net.ssl.SSLHandshakeException("untrusted")))
        assertFalse(isOfflineNetworkFailure(
            java.io.IOException("response exceeds bounded reply size"),
        ))
        assertFalse(isOfflineNetworkFailure(IllegalArgumentException("bad JSON")))
    }
}
