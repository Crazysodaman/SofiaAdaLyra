package ai.sofia.mobile

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.viewModels
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID

data class ChatLine(val speaker: String, val text: String)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val secure = SecureSettings(application)
    private val api = SofiaApi(secure)
    val pairingDeviceId: String = secure.deviceId
    var config by mutableStateOf(secure.load())
        private set
    var draft by mutableStateOf("")
    var status by mutableStateOf("Not connected")
    var mood by mutableStateOf("settled")
    var gesture by mutableStateOf("still")
    var busy by mutableStateOf(false)
    val messages = mutableStateListOf<ChatLine>()
    val mainHistory = mutableStateListOf<ChatLine>()
    var historyOpen by mutableStateOf(false)
        private set
    var historyHasMore by mutableStateOf(false)
        private set
    private var historyCursor: JSONObject? = null
    private var pendingText: String? = null
    private var pendingRequestId: String? = null
    private var pendingPrivateMode: Boolean? = null

    init {
        receivePending()
    }

    fun receivePending() {
        secure.consumeIncoming().forEach { messages += ChatLine("Sofía", it) }
    }

    fun serviceNeeded(value: CompanionSettings = config): Boolean =
        secure.ready(value) && (value.shareSensors || value.proactiveNotifications)

    fun save(next: CompanionSettings) {
        if (busy && (next.token != config.token || next.baseUrl != config.baseUrl)) {
            status = "Finish the current request before changing the paired server"
            return
        }
        if (next.token != config.token || next.baseUrl != config.baseUrl) {
            // Old server/audience material must not appear under a newly
            // paired credential. Keep only the owner's unsent local draft.
            messages.clear()
            mainHistory.clear()
            historyCursor = null
            historyHasMore = false
            historyOpen = false
            pendingText = null
            pendingRequestId = null
            pendingPrivateMode = null
            mood = "settled"
            gesture = "still"
        }
        secure.save(next)
        config = secure.load()
        status = "Settings saved"
    }

    fun setPrivateMode(next: CompanionSettings) {
        // Do not permit a pending private HTTP response to populate standard UI.
        if (busy) {
            status = "Finish the current request before changing privacy mode"
            return
        }
        if (next.privateMode != config.privateMode) {
            // The previous mode's transcript must not remain on a shared screen.
            messages.clear()
            mainHistory.clear()
            historyCursor = null
            historyOpen = false
            historyHasMore = false
            draft = ""
            pendingText = null
            pendingRequestId = null
            pendingPrivateMode = null
            mood = "settled"
            gesture = "still"
        }
        save(next)
        status = "Privacy mode changed; refresh host state"
    }

    fun showChat() { historyOpen = false }

    fun loadMainHistory(reset: Boolean = true) {
        if (busy) return
        if (!reset && !historyHasMore) return
        val cursor = if (reset) null else historyCursor
        historyOpen = true
        launchRequest {
            val result = withContext(Dispatchers.IO) {
                api.mainPage(cursor)
            }
            // Compose state is owned by the UI dispatcher, never IO.
            val array = result.getJSONArray("messages")
            val loaded = (0 until array.length()).map { index ->
                val item = array.getJSONObject(index)
                val speaker = if (item.getString("role") == "user") "You" else "Sofía"
                ChatLine(speaker, item.getString("content"))
            }
            if (reset) {
                mainHistory.clear()
                mainHistory.addAll(loaded)
            } else mainHistory.addAll(0, loaded)
            historyCursor = result.optJSONObject("next_before")
            historyHasMore = result.optBoolean("has_more", false)
        }
    }

    private fun applyState(json: JSONObject) {
        val emotion = json.optJSONObject("emotion")
        mood = emotion?.optString("tone", "settled") ?: "settled"
        val expression = json.optJSONObject("expression")
        gesture = expression?.optString("primary")?.takeIf { it.isNotBlank() } ?: "still"
        val adult = json.optBoolean("adult_chat_enabled", false)
        status = if (adult) "Connected · private adult chat enabled" else "Connected · private adult chat disabled on host"
    }

    fun refresh() = launchRequest {
        val result = withContext(Dispatchers.IO) { api.state() }
        applyState(result)
    }

    fun send() {
        val text = draft.trim()
        if (text.isEmpty() || busy) return
        draft = ""
        val requestId = if (
            pendingText == text && pendingPrivateMode == config.privateMode
        ) pendingRequestId ?: UUID.randomUUID().toString()
        else UUID.randomUUID().toString()
        pendingText = text
        pendingPrivateMode = config.privateMode
        pendingRequestId = requestId
        val pending = ChatLine("You", text)
        val index = messages.size
        messages += pending
        launchRequest {
            try {
                val result = withContext(Dispatchers.IO) {
                    api.chat(text, requestId)
                }
                pendingText = null
                pendingRequestId = null
                pendingPrivateMode = null
                messages += ChatLine("Sofía", result.getString("response"))
                applyState(result)
            } catch (failure: Exception) {
                // A timeout does NOT mean the host did not receive the
                // message. Do not blindly replay an uncertain send.
                if (index < messages.size && messages[index] == pending) {
                    messages.removeAt(index)
                }
                draft = text
                status = "Delivery unconfirmed; check Main history before resending"
            }
        }
    }

    private fun launchRequest(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try {
                block()
            } catch (failure: Exception) {
                status = failure.message ?: failure.javaClass.simpleName
            } finally {
                busy = false
            }
        }
    }
}

class MainActivity : ComponentActivity() {
    private val model: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        model.receivePending()
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                SofiaScreen(model)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        model.receivePending()
    }
}

@Composable
private fun SofiaScreen(model: MainViewModel) {
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val notificationsGranted = Build.VERSION.SDK_INT < 33 ||
            grants[Manifest.permission.POST_NOTIFICATIONS] == true ||
            ContextCompat.checkSelfPermission(
                model.getApplication(), Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        val locationGranted = !model.config.shareLocation ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true ||
            ContextCompat.checkSelfPermission(
                model.getApplication(), Manifest.permission.ACCESS_COARSE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED
        val next = model.config.copy(
            shareLocation = locationGranted && model.config.shareLocation,
            proactiveNotifications = (
                notificationsGranted && model.config.proactiveNotifications
            ),
        )
        model.save(next)
        SensorSyncService.setEnabled(model.getApplication(), model.serviceNeeded(next))
    }
    LaunchedEffect(model.config.baseUrl, model.config.token) {
        if (model.serviceNeeded()) {
            if (
                Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(
                    model.getApplication(), Manifest.permission.POST_NOTIFICATIONS,
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                permissionLauncher.launch(arrayOf(Manifest.permission.POST_NOTIFICATIONS))
            } else {
                SensorSyncService.setEnabled(model.getApplication(), true)
            }
        }
    }
    Scaffold { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Sofía", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Device ID for operator pairing: ${model.pairingDeviceId}",
                style = MaterialTheme.typography.bodySmall,
            )
            Text("Mood: ${model.mood} · Expression: ${model.gesture}")
            Text(model.status, style = MaterialTheme.typography.bodySmall)

            var url by remember(model.config.baseUrl) {
                mutableStateOf(model.config.baseUrl)
            }
            var token by remember(model.config.token) {
                mutableStateOf(model.config.token)
            }
            OutlinedTextField(url, { url = it }, label = { Text("HTTPS server URL") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(
                token, { token = it }, label = { Text("Pairing token") },
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(),
            )
            Toggle("Private mode", model.config.privateMode, enabled = !model.busy) {
                model.setPrivateMode(model.config.copy(baseUrl = url, token = token, privateMode = it))
            }
            Toggle("Allow proactive notifications", model.config.proactiveNotifications) { enabled ->
                val next = model.config.copy(
                    baseUrl = url,
                    token = token,
                    proactiveNotifications = enabled,
                )
                model.save(next)
                if (
                    enabled && Build.VERSION.SDK_INT >= 33 &&
                    ContextCompat.checkSelfPermission(
                        model.getApplication(), Manifest.permission.POST_NOTIFICATIONS,
                    ) != PackageManager.PERMISSION_GRANTED
                ) {
                    permissionLauncher.launch(arrayOf(Manifest.permission.POST_NOTIFICATIONS))
                } else {
                    SensorSyncService.setEnabled(
                        model.getApplication(), model.serviceNeeded(next),
                    )
                }
            }
            Toggle("Share selected read-only sensors", model.config.shareSensors) { enabled ->
                val next = model.config.copy(baseUrl = url, token = token, shareSensors = enabled)
                model.save(next)
                if (enabled) {
                    val permissions = buildList {
                        if (next.shareLocation) {
                            add(Manifest.permission.ACCESS_COARSE_LOCATION)
                        }
                        if (next.shareActivity && Build.VERSION.SDK_INT >= 29) {
                            add(Manifest.permission.ACTIVITY_RECOGNITION)
                        }
                        if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
                    }.filter { ContextCompat.checkSelfPermission(model.getApplication(), it) != PackageManager.PERMISSION_GRANTED }
                    if (permissions.isEmpty()) SensorSyncService.setEnabled(model.getApplication(), true)
                    else permissionLauncher.launch(permissions.toTypedArray())
                } else SensorSyncService.setEnabled(
                    model.getApplication(), model.serviceNeeded(next),
                )
            }
            Toggle("Share approximate location", model.config.shareLocation) {
                val next = model.config.copy(baseUrl = url, token = token, shareLocation = it)
                model.save(next)
                if (it) {
                    val missing = listOf(
                        Manifest.permission.ACCESS_COARSE_LOCATION,
                    ).filter {
                        ContextCompat.checkSelfPermission(model.getApplication(), it) !=
                            PackageManager.PERMISSION_GRANTED
                    }
                    if (missing.isNotEmpty()) permissionLauncher.launch(missing.toTypedArray())
                    else if (next.shareSensors) SensorSyncService.setEnabled(model.getApplication(), true)
                } else if (next.shareSensors) {
                    SensorSyncService.setEnabled(model.getApplication(), true)
                }
            }
            Toggle("Share derived movement and steps", model.config.shareActivity) {
                val next = model.config.copy(baseUrl = url, token = token, shareActivity = it)
                model.save(next)
                if (
                    it && Build.VERSION.SDK_INT >= 29 &&
                    ContextCompat.checkSelfPermission(
                        model.getApplication(), Manifest.permission.ACTIVITY_RECOGNITION,
                    ) != PackageManager.PERMISSION_GRANTED
                ) {
                    permissionLauncher.launch(arrayOf(Manifest.permission.ACTIVITY_RECOGNITION))
                } else if (next.shareSensors) {
                    SensorSyncService.setEnabled(model.getApplication(), true)
                }
            }
            Toggle("Share light, pressure, and proximity", model.config.shareAmbient) {
                val next = model.config.copy(baseUrl = url, token = token, shareAmbient = it)
                model.save(next)
                if (next.shareSensors) SensorSyncService.setEnabled(model.getApplication(), true)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val next = model.config.copy(baseUrl = url, token = token)
                    model.save(next)
                    SensorSyncService.setEnabled(
                        model.getApplication(), model.serviceNeeded(next),
                    )
                    model.refresh()
                }) { Text("Save & connect") }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = model::showChat, enabled = !model.busy) { Text("Chat") }
                Button(onClick = { model.loadMainHistory() }, enabled = !model.busy) {
                    Text("Main history")
                }
                if (model.historyOpen && model.historyHasMore) {
                    Button(onClick = { model.loadMainHistory(false) }, enabled = !model.busy) {
                        Text("Older")
                    }
                }
            }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(if (model.historyOpen) model.mainHistory else model.messages) { line ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(10.dp)) {
                            Text(line.speaker, style = MaterialTheme.typography.labelMedium)
                            Text(line.text)
                        }
                    }
                }
            }
            if (!model.historyOpen) {
                OutlinedTextField(
                    model.draft, { model.draft = it }, label = { Text("Message Sofía") },
                    modifier = Modifier.fillMaxWidth(), enabled = !model.busy,
                )
                Button(onClick = model::send, enabled = !model.busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (model.busy) "Waiting…" else "Send")
                }
            }
            Spacer(Modifier.height(4.dp))
            Text(
                "Sensor access is read-only. Private mode does not imply consent or enable shared channels.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun Toggle(
    label: String, checked: Boolean, enabled: Boolean = true,
    change: (Boolean) -> Unit,
) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label)
        Switch(checked = checked, onCheckedChange = change, enabled = enabled)
    }
}
