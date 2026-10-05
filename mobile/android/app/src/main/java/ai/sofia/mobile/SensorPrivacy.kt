package ai.sofia.mobile

/** Pure privacy boundary for reducing motion samples to a bounded label. */
object SensorPrivacy {
    fun activity(
        sharingEnabled: Boolean,
        movingUntilMs: Long,
        nowMs: Long,
    ): String = when {
        !sharingEnabled -> "unknown"
        nowMs < movingUntilMs -> "moving"
        else -> "stationary"
    }
}
