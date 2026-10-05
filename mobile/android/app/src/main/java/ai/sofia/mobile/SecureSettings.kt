package ai.sofia.mobile

import android.content.Context
import android.provider.Settings
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class CompanionSettings(
    val baseUrl: String,
    val token: String,
    val privateMode: Boolean,
    val shareSensors: Boolean,
    val shareLocation: Boolean,
    val shareActivity: Boolean,
    val shareAmbient: Boolean,
)

class SecureSettings(private val context: Context) {
    private val prefs = context.getSharedPreferences("sofia-mobile", Context.MODE_PRIVATE)
    private val alias = "sofia-mobile-api-token"

    val deviceId: String = "android-" + Settings.Secure.getString(
        context.contentResolver, Settings.Secure.ANDROID_ID
    )

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
            .putBoolean("share_sensors", value.shareSensors)
            .putBoolean("share_location", value.shareLocation)
            .putBoolean("share_activity", value.shareActivity)
            .putBoolean("share_ambient", value.shareAmbient)
            .apply()
    }
}
