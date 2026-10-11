package ai.sofia.mobile

import org.json.JSONObject
import java.io.IOException
import java.net.URL
import javax.net.ssl.HttpsURLConnection

data class ProactiveNotification(
    val id: String,
    val title: String,
    val content: String,
    val preview: String,
)

/** Status-only transport failure. Never include bearer or raw response bytes. */
class SofiaHttpFailure(
    val statusCode: Int,
    val serverCode: String,
) : IOException("Sofía HTTP $statusCode ($serverCode)")

class SofiaApi(private val settings: SecureSettings) {
    private fun post(path: String, payload: JSONObject): JSONObject {
        val config = settings.load()
        require(config.baseUrl.startsWith("https://") &&
            config.token.startsWith("sm1_") && config.token.length >= 52) {
            "Configure an HTTPS server and pairing token first"
        }
        val connection = URL(config.baseUrl + path).openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 10_000
            connection.readTimeout = 120_000
            connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer ${config.token}")
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use {
                it.write(payload.toString().toByteArray(Charsets.UTF_8))
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) {
                connection.inputStream
            } else connection.errorStream
            // Read a bounded reply; a hostile proxy/server must not fill
            // phone memory or echo secrets through an exception message.
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { reader ->
                val body = StringBuilder()
                val chunk = CharArray(4096)
                while (true) {
                    val count = reader.read(chunk)
                    if (count < 0) break
                    body.append(chunk, 0, count)
                    if (body.length > 256_000) {
                        throw IOException("Sofía response exceeds bounded reply size")
                    }
                }
                body.toString()
            } ?: ""
            if (status !in 200..299) {
                val code = runCatching {
                    JSONObject(text).optString("error", "http_error")
                }.getOrDefault("http_error")
                throw SofiaHttpFailure(
                    status, code.takeIf { it in setOf(
                        "unauthorized", "forbidden",
                        "delivery_conflict_or_uncertain", "not_found",
                    ) } ?: "http_error",
                )
            }
            return JSONObject(text)
        } finally {
            // HttpsURLConnection must be released on timeouts, HTTP errors,
            // malformed JSON and cancellation, not just on successful calls.
            connection.disconnect()
        }
    }

    fun chat(message: String, requestId: String): JSONObject {
        val config = settings.load()
        return post("/v1/mobile/chat", JSONObject()
            .put("device_id", settings.deviceId)
            .put("message", message)
            .put("private_mode", config.privateMode)
            .put("request_id", requestId))
    }

    fun state(): JSONObject {
        val config = settings.load()
        return post("/v1/mobile/state", JSONObject()
            .put("device_id", settings.deviceId)
            .put("private_mode", config.privateMode))
    }

    fun mainPage(before: JSONObject? = null, limit: Int = 30): JSONObject {
        val config = settings.load()
        val body = JSONObject()
            .put("device_id", settings.deviceId)
            .put("private_mode", config.privateMode)
            .put("before", before ?: JSONObject.NULL)
            .put("limit", limit)
        return post("/v1/mobile/main/page", body)
    }

    fun sensors(payload: JSONObject): JSONObject = post("/v1/mobile/sensors", payload)

    fun claimNotification(): ProactiveNotification? {
        val config = settings.load()
        val result = post("/v1/mobile/notifications/claim", JSONObject()
            .put("device_id", settings.deviceId)
            .put("private_mode", config.privateMode))
        val notification = result.optJSONObject("notification") ?: return null
        return ProactiveNotification(
            id = notification.getString("id"),
            title = notification.getString("title"),
            content = notification.getString("content"),
            preview = notification.getString("preview"),
        )
    }

    fun acknowledgeNotification(notificationId: String): JSONObject =
        post("/v1/mobile/notifications/ack", JSONObject()
            .put("device_id", settings.deviceId)
            .put("notification_id", notificationId))
}
