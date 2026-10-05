package ai.sofia.mobile

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
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
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class ChatLine(val speaker: String, val text: String)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val secure = SecureSettings(application)
    private val api = SofiaApi(secure)
    var config by mutableStateOf(secure.load())
        private set
    var draft by mutableStateOf("")
    var status by mutableStateOf("Not connected")
    var mood by mutableStateOf("settled")
    var gesture by mutableStateOf("still")
    var busy by mutableStateOf(false)
    val messages = mutableStateListOf<ChatLine>()

    fun save(next: CompanionSettings) {
        secure.save(next)
        config = secure.load()
        status = "Settings saved"
    }

    private fun applyState(json: JSONObject) {
        val emotion = json.optJSONObject("emotion")
        mood = emotion?.optString("tone", "settled") ?: "settled"
        val expression = json.optJSONObject("expression")
        gesture = expression?.optString("primary")?.takeIf { it.isNotBlank() } ?: "still"
        val adult = json.optBoolean("adult_chat_enabled", false)
        status = if (adult) "Connected · private adult chat enabled" else "Connected · private adult chat disabled on host"
    }

    fun refresh() = launchRequest { applyState(api.state()) }

    fun send() {
        val text = draft.trim()
        if (text.isEmpty() || busy) return
        draft = ""
        messages += ChatLine("You", text)
        launchRequest {
            val result = api.chat(text)
            messages += ChatLine("Sofía", result.getString("response"))
            applyState(result)
        }
    }

    private fun launchRequest(block: () -> Unit) {
        busy = true
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { block() } }
                .onFailure { status = it.message ?: it.javaClass.simpleName }
            busy = false
        }
    }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                val model: MainViewModel = viewModel()
                SofiaScreen(model)
            }
        }
    }
}

@Composable
private fun SofiaScreen(model: MainViewModel) {
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val locationGranted = !model.config.shareLocation ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true ||
            ContextCompat.checkSelfPermission(
                model.getApplication(), Manifest.permission.ACCESS_COARSE_LOCATION,
            ) == PackageManager.PERMISSION_GRANTED
        val next = model.config.copy(shareLocation = locationGranted && model.config.shareLocation)
        model.save(next)
        SensorSyncService.setEnabled(model.getApplication(), next.shareSensors)
    }
    Scaffold { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Sofía", style = MaterialTheme.typography.headlineMedium)
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
            Toggle("Private mode", model.config.privateMode) {
                model.save(model.config.copy(baseUrl = url, token = token, privateMode = it))
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
                } else SensorSyncService.setEnabled(model.getApplication(), false)
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
                    model.save(model.config.copy(baseUrl = url, token = token))
                    model.refresh()
                }) { Text("Save & connect") }
            }

            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(model.messages) { line ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(10.dp)) {
                            Text(line.speaker, style = MaterialTheme.typography.labelMedium)
                            Text(line.text)
                        }
                    }
                }
            }
            OutlinedTextField(
                model.draft, { model.draft = it }, label = { Text("Message Sofía") },
                modifier = Modifier.fillMaxWidth(), enabled = !model.busy,
            )
            Button(onClick = model::send, enabled = !model.busy, modifier = Modifier.fillMaxWidth()) {
                Text(if (model.busy) "Waiting…" else "Send")
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
private fun Toggle(label: String, checked: Boolean, change: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label)
        Switch(checked = checked, onCheckedChange = change)
    }
}
