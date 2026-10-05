package ai.sofia.mobile

import org.json.JSONObject
import java.net.URL
import javax.net.ssl.HttpsURLConnection

class SofiaApi(private val settings: SecureSettings) {
    private fun post(path: String, payload: JSONObject): JSONObject {
        val config = settings.load()
        require(config.baseUrl.startsWith("https://") && config.token.length >= 32) {
            "Configure an HTTPS server and pairing token first"
        }
        val connection = URL(config.baseUrl + path).openConnection() as HttpsURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 10_000
        connection.readTimeout = 120_000
        connection.doOutput = true
        connection.setRequestProperty("Authorization", "Bearer ${config.token}")
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.write(payload.toString().toByteArray()) }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream.bufferedReader().use { it.readText() }
        connection.disconnect()
        if (status !in 200..299) throw IllegalStateException("Sofía server returned HTTP $status")
        return JSONObject(text)
    }

    fun chat(message: String): JSONObject {
        val config = settings.load()
        return post("/v1/mobile/chat", JSONObject()
            .put("device_id", settings.deviceId)
            .put("message", message)
            .put("private_mode", config.privateMode))
    }

    fun state(): JSONObject {
        val config = settings.load()
        return post("/v1/mobile/state", JSONObject()
            .put("device_id", settings.deviceId)
            .put("private_mode", config.privateMode))
    }

    fun sensors(payload: JSONObject): JSONObject = post("/v1/mobile/sensors", payload)
}
