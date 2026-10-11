package ai.sofia.mobile

import android.content.Context
import android.provider.Settings
import android.util.Base64
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import org.json.JSONArray
import org.json.JSONObject

data class CompanionSettings(
    val baseUrl: String,
    val token: String,
    val privateMode: Boolean,
    val proactiveNotifications: Boolean,
    val shareSensors: Boolean,
    val shareLocation: Boolean,
    val shareActivity: Boolean,
    val shareAmbient: Boolean,
)

data class PendingMobileTurn(
    val requestId: String,
    val text: String,
    val privateMode: Boolean,
    val baseUrl: String,
    val tokenFingerprint: String,
) {
    fun matches(settings: CompanionSettings): Boolean =
        privateMode == settings.privateMode &&
        baseUrl == settings.baseUrl.trimEnd('/') &&
        tokenFingerprint == SecureSettings.tokenFingerprint(settings.token)
}

class SecureSettings(private val context: Context) {
    private val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
    private val alias = "sofia-mobile-api-token"

    val deviceId: String = "android-" + Settings.Secure.getString(
        context.contentResolver, Settings.Secure.ANDROID_ID
    )

    fun ready(value: CompanionSettings = load()): Boolean =
        value.baseUrl.startsWith("https://") &&
            value.token.startsWith("sm1_") && value.token.length >= 52

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing = store.getKey(alias, null) as? SecretKey
        if (existing != null) return existing
        return KeyGenerator.getInstance("AES", "AndroidKeyStore").run {
            init(
                android.security.keystore.KeyGenParameterSpec.Builder(
                    alias,
                    android.security.keystore.KeyProperties.PURPOSE_ENCRYPT or
                        android.security.keystore.KeyProperties.PURPOSE_DECRYPT,
                ).setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(
                        android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE
                    ).build()
            )
            generateKey()
        }
    }

    private fun encrypt(value: String): String {
        if (value.isBlank()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val body = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(cipher.iv + body, Base64.NO_WRAP)
    }

    private fun decrypt(value: String): String {
        if (value.isBlank()) return ""
        return runCatching {
            val raw = Base64.decode(value, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw.copyOfRange(0, 12)))
            String(cipher.doFinal(raw.copyOfRange(12, raw.size)), Charsets.UTF_8)
        }.getOrDefault("")
    }

    fun load() = CompanionSettings(
        baseUrl = prefs.getString("base_url", "") ?: "",
        token = decrypt(prefs.getString("token", "") ?: ""),
        privateMode = prefs.getBoolean("private_mode", false),
        proactiveNotifications = prefs.getBoolean("proactive_notifications", true),
        shareSensors = prefs.getBoolean("share_sensors", false),
        shareLocation = prefs.getBoolean("share_location", false),
        shareActivity = prefs.getBoolean("share_activity", true),
        shareAmbient = prefs.getBoolean("share_ambient", true),
    )

    fun save(value: CompanionSettings) {
        require(value.baseUrl.isBlank() || value.baseUrl.startsWith("https://")) {
            "The Sofía server URL must use HTTPS"
        }
        prefs.edit()
            .putString("base_url", value.baseUrl.trimEnd('/'))
            .putString("token", encrypt(value.token))
            .putBoolean("private_mode", value.privateMode)
            .putBoolean("proactive_notifications", value.proactiveNotifications)
            .putBoolean("share_sensors", value.shareSensors)
            .putBoolean("share_location", value.shareLocation)
            .putBoolean("share_activity", value.shareActivity)
            .putBoolean("share_ambient", value.shareAmbient)
            .apply()
    }

    companion object {
        fun tokenFingerprint(token: String): String =
            MessageDigest.getInstance("SHA-256")
                .digest(token.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }

    /** Read-only local journal entry. Never silently interpret corruption as absence. */
    fun pendingOutbound(): PendingMobileTurn? {
        val saved = prefs.getString("pending_outbound_v1", "") ?: ""
        if (saved.isBlank()) return null
        val raw = decrypt(saved)
        require(raw.isNotBlank()) {
            "Encrypted outgoing draft cannot be decrypted; explicit owner discard required"
        }
        val json = try { JSONObject(raw) } catch (error: Exception) {
            throw IllegalStateException("Encrypted outgoing draft is damaged", error)
        }
        val requestId = json.getString("request_id")
        val message = json.getString("message")
        require(requestId.length in 8..128 && message.isNotBlank() && message.length <= 12_000) {
            "Encrypted outgoing draft contains invalid fields"
        }
        return PendingMobileTurn(
            requestId = requestId, text = message,
            privateMode = json.getBoolean("private_mode"),
            baseUrl = json.getString("base_url"),
            tokenFingerprint = json.getString("token_fingerprint"),
        )
    }

    /**
     * Durable write-before-send. Once the first HTTP request may have started,
     * its ID and bytes cannot be replaced until the owner explicitly discards
     * it or the original request is confirmed completed.
     */
    fun reserveOutbound(
        settings: CompanionSettings, message: String, requestId: String,
    ): PendingMobileTurn {
        require(ready(settings)) { "Paired HTTPS endpoint required to send" }
        require(message.isNotBlank() && message.length <= 12_000) {
            "Outgoing text must be bounded"
        }
        require(requestId.length in 8..128) { "Stable request ID required" }
        val existing = pendingOutbound()
        if (existing != null) {
            check(existing.matches(settings) &&
                existing.requestId == requestId && existing.text == message
            ) { "Resolve or explicitly discard the previous unconfirmed turn" }
            return existing
        }
        val pending = PendingMobileTurn(
            requestId = requestId, text = message,
            privateMode = settings.privateMode,
            baseUrl = settings.baseUrl.trimEnd('/'),
            tokenFingerprint = tokenFingerprint(settings.token),
        )
        val json = JSONObject()
            .put("request_id", pending.requestId)
            .put("message", pending.text)
            .put("private_mode", pending.privateMode)
            .put("base_url", pending.baseUrl)
            .put("token_fingerprint", pending.tokenFingerprint)
        check(prefs.edit()
            .putString("pending_outbound_v1", encrypt(json.toString()))
            .commit()
        ) { "Could not persist outgoing request; refusing to send" }
        return pending
    }

    fun confirmOutbound(requestId: String) {
        val existing = pendingOutbound() ?: return
        check(existing.requestId == requestId) {
            "A different outgoing request became authoritative"
        }
        check(prefs.edit().remove("pending_outbound_v1").commit()) {
            "Could not durably acknowledge outgoing request"
        }
    }

    /** Destructive local operation; caller must expose explicit owner choice. */
    fun discardUnconfirmedOutbound() {
        check(prefs.edit().remove("pending_outbound_v1").commit()) {
            "Could not discard unresolved outgoing request"
        }
    }

    fun storeIncoming(notificationId: String, content: String) {
        require(notificationId.isNotBlank() && content.isNotBlank())
        val existing = decrypt(prefs.getString("incoming_messages", "") ?: "")
        val current = runCatching { JSONArray(existing) }.getOrElse { JSONArray() }
        if ((0 until current.length()).any {
                current.optJSONObject(it)?.optString("id") == notificationId
            }
        ) return
        val retained = JSONArray()
        for (index in maxOf(0, current.length() - 48) until current.length()) {
            retained.put(current.get(index))
        }
        retained.put(JSONObject().put("id", notificationId).put("content", content))
        prefs.edit()
            .putString("incoming_messages", encrypt(retained.toString()))
            .apply()
    }

    fun clearIncoming() {
        // A previous server/token/privacy mode cannot leave encrypted
        // unopened content that later resurfaces in the new audience UI.
        prefs.edit().remove("incoming_messages").commit()
    }

    fun consumeIncoming(): List<String> {
        val encrypted = prefs.getString("incoming_messages", "") ?: ""
        if (encrypted.isBlank()) return emptyList()
        val values = runCatching { JSONArray(decrypt(encrypted)) }
            .getOrElse { JSONArray() }
        val content = (0 until values.length()).mapNotNull {
            values.optJSONObject(it)?.optString("content")?.takeIf(String::isNotBlank)
        }
        prefs.edit().remove("incoming_messages").apply()
        return content
    }
}
