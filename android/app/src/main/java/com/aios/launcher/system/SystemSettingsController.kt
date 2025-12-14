package com.aios.launcher.system

import android.app.NotificationManager
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.location.LocationManager
import android.media.AudioManager
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.os.Vibrator
import android.provider.Settings
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Complete System Settings Controller for AI-OS. Provides comprehensive control over all device
 * settings.
 */
@Singleton
class SystemSettingsController
@Inject
constructor(@ApplicationContext private val context: Context) {
    companion object {
        private const val TAG = "SystemSettings"
    }

    private val contentResolver: ContentResolver = context.contentResolver
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
    private val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator

    // ==================== Display Settings ====================

    /** Get current screen brightness (0-255). */
    fun getScreenBrightness(): Int {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS)
        } catch (e: Exception) {
            -1
        }
    }

    /** Set screen brightness (0-255). */
    fun setScreenBrightness(brightness: Int): Boolean {
        return try {
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(
                        contentResolver,
                        Settings.System.SCREEN_BRIGHTNESS,
                        brightness.coerceIn(0, 255)
                )
                true
            } else {
                requestWriteSettingsPermission()
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to set brightness", e)
            false
        }
    }

    /** Get auto brightness mode. */
    fun isAutoBrightnessEnabled(): Boolean {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE) ==
                    Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC
        } catch (e: Exception) {
            false
        }
    }

    /** Set auto brightness mode. */
    fun setAutoBrightness(enabled: Boolean): Boolean {
        return try {
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(
                        contentResolver,
                        Settings.System.SCREEN_BRIGHTNESS_MODE,
                        if (enabled) Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC
                        else Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL
                )
                true
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    /** Get screen timeout in milliseconds. */
    fun getScreenTimeout(): Int {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.SCREEN_OFF_TIMEOUT)
        } catch (e: Exception) {
            -1
        }
    }

    /** Set screen timeout. */
    fun setScreenTimeout(timeoutMs: Int): Boolean {
        return try {
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(
                        contentResolver,
                        Settings.System.SCREEN_OFF_TIMEOUT,
                        timeoutMs
                )
                true
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    // ==================== Audio Settings ====================

    /** Get media volume (0-100). */
    fun getMediaVolume(): Int {
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val current = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        return (current * 100 / max)
    }

    /** Set media volume (0-100). */
    fun setMediaVolume(percent: Int): Boolean {
        return try {
            val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            val volume = (percent.coerceIn(0, 100) * max / 100)
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, volume, 0)
            true
        } catch (e: Exception) {
            false
        }
    }

    /** Get ring volume (0-100). */
    fun getRingVolume(): Int {
        val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_RING)
        val current = audioManager.getStreamVolume(AudioManager.STREAM_RING)
        return (current * 100 / max)
    }

    /** Set ring volume (0-100). */
    fun setRingVolume(percent: Int): Boolean {
        return try {
            val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_RING)
            val volume = (percent.coerceIn(0, 100) * max / 100)
            audioManager.setStreamVolume(AudioManager.STREAM_RING, volume, 0)
            true
        } catch (e: Exception) {
            false
        }
    }

    /** Set ringer mode. */
    fun setRingerMode(mode: RingerMode): Boolean {
        return try {
            val audioMode =
                    when (mode) {
                        RingerMode.NORMAL -> AudioManager.RINGER_MODE_NORMAL
                        RingerMode.VIBRATE -> AudioManager.RINGER_MODE_VIBRATE
                        RingerMode.SILENT -> AudioManager.RINGER_MODE_SILENT
                    }
            audioManager.ringerMode = audioMode
            true
        } catch (e: Exception) {
            false
        }
    }

    /** Get current ringer mode. */
    fun getRingerMode(): RingerMode {
        return when (audioManager.ringerMode) {
            AudioManager.RINGER_MODE_NORMAL -> RingerMode.NORMAL
            AudioManager.RINGER_MODE_VIBRATE -> RingerMode.VIBRATE
            AudioManager.RINGER_MODE_SILENT -> RingerMode.SILENT
            else -> RingerMode.NORMAL
        }
    }

    /** Set Do Not Disturb mode. */
    fun setDoNotDisturb(enabled: Boolean): Boolean {
        return try {
            if (notificationManager.isNotificationPolicyAccessGranted) {
                val filter =
                        if (enabled) {
                            NotificationManager.INTERRUPTION_FILTER_NONE
                        } else {
                            NotificationManager.INTERRUPTION_FILTER_ALL
                        }
                notificationManager.setInterruptionFilter(filter)
                true
            } else {
                // Request DND access
                context.startActivity(
                        Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        }
                )
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    // ==================== Vibration ====================

    /** Vibrate for duration. */
    fun vibrate(durationMs: Long): Boolean {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(
                        android.os.VibrationEffect.createOneShot(
                                durationMs,
                                android.os.VibrationEffect.DEFAULT_AMPLITUDE
                        )
                )
            } else {
                @Suppress("DEPRECATION") vibrator.vibrate(durationMs)
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    // ==================== Flashlight ====================

    /** Toggle flashlight. */
    fun setFlashlight(enabled: Boolean): Boolean {
        return try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraId = cameraManager.cameraIdList.firstOrNull() ?: return false
            cameraManager.setTorchMode(cameraId, enabled)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to toggle flashlight", e)
            false
        }
    }

    // ==================== System Information ====================

    /** Get comprehensive device information. */
    fun getDeviceInfo(): DeviceInfo {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager

        return DeviceInfo(
                manufacturer = Build.MANUFACTURER,
                model = Build.MODEL,
                device = Build.DEVICE,
                androidVersion = Build.VERSION.RELEASE,
                sdkVersion = Build.VERSION.SDK_INT,
                batteryLevel =
                        batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY),
                isCharging = batteryManager.isCharging,
                isPowerSaveMode = powerManager.isPowerSaveMode
        )
    }

    /** Get battery information. */
    fun getBatteryInfo(): BatteryInfo {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager

        return BatteryInfo(
                level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY),
                isCharging = batteryManager.isCharging,
                temperature = 0, // Requires battery intent
                health = "Unknown"
        )
    }

    // ==================== Airplane Mode ====================

    /** Check if airplane mode is enabled. */
    fun isAirplaneModeEnabled(): Boolean {
        return Settings.Global.getInt(contentResolver, Settings.Global.AIRPLANE_MODE_ON, 0) != 0
    }

    /** Toggle airplane mode (requires root on modern Android). */
    fun setAirplaneMode(enabled: Boolean): Boolean {
        // On modern Android, this requires system-level permissions
        // Open settings instead
        context.startActivity(
                Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
        )
        return false
    }

    // ==================== Location ====================

    /** Check if location is enabled. */
    fun isLocationEnabled(): Boolean {
        return try {
            val locationManager =
                    context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
                    locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        } catch (e: Exception) {
            false
        }
    }

    /** Open location settings. */
    fun openLocationSettings() {
        context.startActivity(
                Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
        )
    }

    // ==================== Rotation ====================

    /** Get auto-rotate setting. */
    fun isAutoRotateEnabled(): Boolean {
        return try {
            Settings.System.getInt(contentResolver, Settings.System.ACCELEROMETER_ROTATION) == 1
        } catch (e: Exception) {
            false
        }
    }

    /** Set auto-rotate. */
    fun setAutoRotate(enabled: Boolean): Boolean {
        return try {
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(
                        contentResolver,
                        Settings.System.ACCELEROMETER_ROTATION,
                        if (enabled) 1 else 0
                )
                true
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    // ==================== Helpers ====================

    private fun requestWriteSettingsPermission() {
        val intent =
                Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                    data = android.net.Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
        context.startActivity(intent)
    }

    fun canWriteSettings(): Boolean {
        return Settings.System.canWrite(context)
    }

    fun requestWriteSettings() {
        requestWriteSettingsPermission()
    }
}

// Data classes
data class DeviceInfo(
        val manufacturer: String,
        val model: String,
        val device: String,
        val androidVersion: String,
        val sdkVersion: Int,
        val batteryLevel: Int,
        val isCharging: Boolean,
        val isPowerSaveMode: Boolean
)

data class BatteryInfo(
        val level: Int,
        val isCharging: Boolean,
        val temperature: Int,
        val health: String
)

enum class RingerMode {
    NORMAL,
    VIBRATE,
    SILENT
}
