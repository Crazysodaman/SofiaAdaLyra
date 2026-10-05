package ai.sofia.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.sqrt

class SensorSyncService : Service(), SensorEventListener, LocationListener {
    private val scope = CoroutineScope(Dispatchers.IO + Job())
    private lateinit var settings: SecureSettings
    private lateinit var sensors: SensorManager
    private val values = ConcurrentHashMap<Int, Float>()
    @Volatile private var latestLocation: Location? = null
    @Volatile private var movingUntilMs: Long = 0L
    @Volatile private var locationRequested = false

    override fun onCreate() {
        super.onCreate()
        settings = SecureSettings(this)
        sensors = getSystemService(SENSOR_SERVICE) as SensorManager
        createNotificationChannel()
        val initial = settings.load()
        startCompanionForeground(initial)
        applyConfiguration(initial)
        scope.launch {
            while (isActive) {
                val config = settings.load()
                if (!config.shareSensors && !config.proactiveNotifications) {
                    stopSelf()
                    break
                }
                if (settings.ready(config)) {
                    val api = SofiaApi(settings)
                    if (config.shareSensors) {
                        runCatching { api.sensors(snapshot(config)) }
                    }
                    if (config.proactiveNotifications && notificationsAllowed()) {
                        var delivered = 0
                        while (delivered < 5) {
                            val notification = runCatching {
                                api.claimNotification()
                            }.getOrNull() ?: break
                            if (display(notification)) {
                                runCatching { api.acknowledgeNotification(notification.id) }
                                delivered += 1
                            } else {
                                break
                            }
                        }
                    }
                }
                delay(60_000)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val config = settings.load()
        if (!config.shareSensors && !config.proactiveNotifications) {
            stopSelf()
            return START_NOT_STICKY
        }
        startCompanionForeground(config)
        applyConfiguration(config)
        return START_STICKY
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel(
            "sofia-companion", "Sofía mobile connection", NotificationManager.IMPORTANCE_LOW,
        ))
        manager.createNotificationChannel(NotificationChannel(
            "sofia-outreach", "Sofía proactive messages", NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            lockscreenVisibility = android.app.Notification.VISIBILITY_PRIVATE
            description = "Governed proactive messages from Sofía"
        })
    }

    private fun notificationsAllowed(): Boolean =
        android.os.Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED

    private fun display(notification: ProactiveNotification): Boolean {
        settings.storeIncoming(notification.id, notification.content)
        val launch = PendingIntent.getActivity(
            this,
            notification.id.hashCode(),
            Intent(this, MainActivity::class.java).apply {
                action = "ai.sofia.mobile.OPEN_PROACTIVE"
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val rendered = NotificationCompat.Builder(this, "sofia-outreach")
            .setSmallIcon(android.R.drawable.ic_dialog_email)
            .setContentTitle(notification.title)
            .setContentText(notification.preview)
            .setContentIntent(launch)
            .setAutoCancel(true)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .build()
        return runCatching {
            val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            manager.notify(notification.id.hashCode() and Int.MAX_VALUE, rendered)
        }.isSuccess
    }

    private fun startCompanionForeground(config: CompanionSettings) {
        val launch = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = NotificationCompat.Builder(this, "sofia-companion")
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentTitle("Sofía mobile companion")
            .setContentText(
                if (config.shareSensors) "Connected with selected sensor context"
                else "Listening for proactive messages"
            )
            .setContentIntent(launch)
            .setOngoing(true)
            .build()
        val type = if (
            android.os.Build.VERSION.SDK_INT >= 29 && config.shareLocation
        ) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        } else if (android.os.Build.VERSION.SDK_INT >= 29) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        } else {
            0
        }
        ServiceCompat.startForeground(this, 41, notification, type)
    }

    private fun applyConfiguration(config: CompanionSettings) {
        sensors.unregisterListener(this)
        values.clear()
        val types = buildList {
            if (config.shareSensors && config.shareAmbient) {
                add(Sensor.TYPE_LIGHT)
                add(Sensor.TYPE_PRESSURE)
                add(Sensor.TYPE_PROXIMITY)
            }
            if (config.shareSensors && config.shareActivity) {
                add(Sensor.TYPE_STEP_COUNTER)
                add(Sensor.TYPE_LINEAR_ACCELERATION)
            }
        }
        for (type in types) {
            sensors.getDefaultSensor(type)?.let {
                sensors.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
            }
        }
        configureLocation(config.shareSensors && config.shareLocation)
    }

    private fun configureLocation(enabled: Boolean) {
        val manager = getSystemService(LOCATION_SERVICE) as LocationManager
        if (!enabled) {
            if (locationRequested) runCatching { manager.removeUpdates(this) }
            locationRequested = false
            latestLocation = null
            return
        }
        if (ContextCompat.checkSelfPermission(
                this, Manifest.permission.ACCESS_COARSE_LOCATION,
            ) != PackageManager.PERMISSION_GRANTED
        ) return
        if (locationRequested) return
        for (provider in listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)) {
            if (manager.isProviderEnabled(provider)) {
                runCatching { manager.requestLocationUpdates(provider, 60_000, 25f, this) }
                manager.getLastKnownLocation(provider)?.let { location ->
                    if (latestLocation == null || location.time > latestLocation!!.time) {
                        latestLocation = location
                    }
                }
            }
        }
        locationRequested = true
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.values.isEmpty()) return
        if (event.sensor.type == Sensor.TYPE_LINEAR_ACCELERATION && event.values.size >= 3) {
            val magnitude = sqrt(
                event.values[0] * event.values[0] +
                    event.values[1] * event.values[1] +
                    event.values[2] * event.values[2]
            )
            if (magnitude > 1.2f) movingUntilMs = System.currentTimeMillis() + 90_000
        } else {
            values[event.sensor.type] = event.values[0]
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
    override fun onLocationChanged(location: Location) { latestLocation = location }
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        sensors.unregisterListener(this)
        val manager = getSystemService(LOCATION_SERVICE) as LocationManager
        if (locationRequested) runCatching { manager.removeUpdates(this) }
        scope.coroutineContext[Job]?.cancel()
        super.onDestroy()
    }

    private fun network(): String {
        val manager = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        val capabilities = manager.getNetworkCapabilities(manager.activeNetwork) ?: return "offline"
        return when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            else -> "other"
        }
    }

    private fun snapshot(config: CompanionSettings): JSONObject {
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val status = battery?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val location = if (config.shareLocation) latestLocation else null
        fun optional(value: Any?): Any = value ?: JSONObject.NULL
        return JSONObject()
            .put("device_id", settings.deviceId)
            .put("observed_at", Instant.now().toString())
            .put("timezone", ZoneId.systemDefault().id)
            .put("latitude", optional(location?.latitude))
            .put("longitude", optional(location?.longitude))
            .put("accuracy_meters", optional(location?.accuracy?.toDouble()))
            .put(
                "battery_percent",
                optional(if (level >= 0 && scale > 0) level * 100.0 / scale else null),
            )
            .put(
                "charging",
                optional(if (status < 0) null else status == BatteryManager.BATTERY_STATUS_CHARGING ||
                    status == BatteryManager.BATTERY_STATUS_FULL),
            )
            .put("network", network())
            .put(
                "activity",
                SensorPrivacy.activity(
                    config.shareActivity,
                    movingUntilMs,
                    System.currentTimeMillis(),
                ),
            )
            .put(
                "ambient_light_lux",
                optional(if (config.shareAmbient) values[Sensor.TYPE_LIGHT]?.toDouble() else null),
            )
            .put(
                "pressure_hpa",
                optional(if (config.shareAmbient) values[Sensor.TYPE_PRESSURE]?.toDouble() else null),
            )
            .put(
                "proximity_near",
                optional(if (config.shareAmbient) values[Sensor.TYPE_PROXIMITY]?.let { it < 1f } else null),
            )
            .put(
                "step_counter",
                optional(if (config.shareActivity) values[Sensor.TYPE_STEP_COUNTER]?.toDouble() else null),
            )
    }

    companion object {
        fun setEnabled(context: Context, enabled: Boolean) {
            val intent = Intent(context, SensorSyncService::class.java)
            if (enabled) ContextCompat.startForegroundService(context, intent)
            else context.stopService(intent)
        }
    }
}
