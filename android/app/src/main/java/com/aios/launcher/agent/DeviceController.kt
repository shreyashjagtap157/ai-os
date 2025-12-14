package com.aios.launcher.agent

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.provider.AlarmClock
import android.provider.MediaStore
import android.provider.Settings
import android.telephony.SmsManager
import android.bluetooth.BluetoothAdapter
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Device Controller for AI-OS.
 * Provides programmatic access to device functions.
 */
@Singleton
class DeviceController @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val TAG = "DeviceController"
    }
    
    private val packageManager: PackageManager = context.packageManager
    private val audioManager: AudioManager = 
        context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    
    // ==================== App Management ====================
    
    /**
     * Open an app by package name or app name.
     */
    fun openApp(packageNameOrAppName: String): Boolean {
        return try {
            // Try as package name first
            var intent = packageManager.getLaunchIntentForPackage(packageNameOrAppName)
            
            // If not found, search by app name
            if (intent == null) {
                intent = findAppByName(packageNameOrAppName)
            }
            
            intent?.let {
                it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(it)
                Log.d(TAG, "Opened app: $packageNameOrAppName")
                true
            } ?: run {
                Log.w(TAG, "App not found: $packageNameOrAppName")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error opening app", e)
            false
        }
    }
    
    private fun findAppByName(name: String): Intent? {
        val apps = packageManager.getInstalledApplications(PackageManager.GET_META_DATA)
        val matchingApp = apps.firstOrNull { app ->
            val label = packageManager.getApplicationLabel(app).toString()
            label.contains(name, ignoreCase = true)
        }
        return matchingApp?.let { 
            packageManager.getLaunchIntentForPackage(it.packageName) 
        }
    }
    
    /**
     * Get list of installed apps.
     */
    fun getInstalledApps(): List<AppInfo> {
        val intent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_LAUNCHER)
        }
        
        return packageManager.queryIntentActivities(intent, 0)
            .map { resolveInfo ->
                AppInfo(
                    name = resolveInfo.loadLabel(packageManager).toString(),
                    packageName = resolveInfo.activityInfo.packageName,
                    icon = resolveInfo.loadIcon(packageManager)
                )
            }
            .sortedBy { it.name }
    }
    
    // ==================== Communication ====================
    
    /**
     * Make a phone call.
     */
    fun makeCall(phoneNumber: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_CALL).apply {
                data = Uri.parse("tel:$phoneNumber")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: SecurityException) {
            Log.e(TAG, "Call permission denied", e)
            // Fall back to dial (doesn't auto-call)
            dialNumber(phoneNumber)
        } catch (e: Exception) {
            Log.e(TAG, "Error making call", e)
            false
        }
    }
    
    /**
     * Open dialer with number.
     */
    fun dialNumber(phoneNumber: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_DIAL).apply {
                data = Uri.parse("tel:$phoneNumber")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error opening dialer", e)
            false
        }
    }
    
    /**
     * Send an SMS message.
     */
    fun sendSMS(phoneNumber: String, message: String): Boolean {
        return try {
            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }
            
            smsManager.sendTextMessage(phoneNumber, null, message, null, null)
            Log.d(TAG, "SMS sent to $phoneNumber")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error sending SMS", e)
            false
        }
    }
    
    // ==================== Media & Audio ====================
    
    /**
     * Set device volume (0-100).
     */
    fun setVolume(level: Int): Boolean {
        return try {
            val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            val volume = (level.coerceIn(0, 100) * maxVolume / 100)
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, volume, 0)
            Log.d(TAG, "Volume set to $level%")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error setting volume", e)
            false
        }
    }
    
    /**
     * Play music with a search query.
     */
    fun playMusic(query: String): Boolean {
        return try {
            val intent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
                putExtra(MediaStore.EXTRA_MEDIA_TITLE, query)
                putExtra(SearchManager.QUERY, query)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error playing music", e)
            false
        }
    }
    
    // ==================== System Settings ====================
    
    /**
     * Set screen brightness (0-255).
     */
    fun setBrightness(level: Int): Boolean {
        return try {
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(
                    context.contentResolver,
                    Settings.System.SCREEN_BRIGHTNESS,
                    level.coerceIn(0, 255)
                )
                true
            } else {
                // Request permission
                val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                    data = Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error setting brightness", e)
            false
        }
    }
    
    /**
     * Toggle WiFi on/off.
     */
    fun toggleWifi(enable: Boolean): Boolean {
        return try {
            val wifiManager = context.applicationContext
                .getSystemService(Context.WIFI_SERVICE) as WifiManager
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // For Android 10+, open WiFi settings
                val intent = Intent(Settings.ACTION_WIFI_SETTINGS).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                true
            } else {
                @Suppress("DEPRECATION")
                wifiManager.isWifiEnabled = enable
                true
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error toggling WiFi", e)
            false
        }
    }
    
    /**
     * Toggle Bluetooth on/off.
     */
    fun toggleBluetooth(enable: Boolean): Boolean {
        return try {
            val bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
            if (bluetoothAdapter != null) {
                @Suppress("DEPRECATION")
                if (enable) {
                    bluetoothAdapter.enable()
                } else {
                    bluetoothAdapter.disable()
                }
                true
            } else {
                false
            }
        } catch (e: SecurityException) {
            Log.e(TAG, "Bluetooth permission denied", e)
            openSettings("bluetooth")
            false
        }
    }
    
    /**
     * Open device settings.
     */
    fun openSettings(section: String? = null): Boolean {
        return try {
            val intent = when (section?.lowercase()) {
                "wifi" -> Intent(Settings.ACTION_WIFI_SETTINGS)
                "bluetooth" -> Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
                "display" -> Intent(Settings.ACTION_DISPLAY_SETTINGS)
                "sound" -> Intent(Settings.ACTION_SOUND_SETTINGS)
                "battery" -> Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS)
                "apps" -> Intent(Settings.ACTION_APPLICATION_SETTINGS)
                "location" -> Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                "security" -> Intent(Settings.ACTION_SECURITY_SETTINGS)
                "accessibility" -> Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                else -> Intent(Settings.ACTION_SETTINGS)
            }.apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error opening settings", e)
            false
        }
    }
    
    // ==================== Alarms & Reminders ====================
    
    /**
     * Set an alarm.
     */
    fun setAlarm(hour: Int, minute: Int, message: String = "AI-OS Alarm"): Boolean {
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, hour)
                putExtra(AlarmClock.EXTRA_MINUTES, minute)
                putExtra(AlarmClock.EXTRA_MESSAGE, message)
                putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error setting alarm", e)
            false
        }
    }
    
    /**
     * Create a reminder/timer.
     */
    fun createReminder(title: String, timeInSeconds: Int): Boolean {
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_TIMER).apply {
                putExtra(AlarmClock.EXTRA_LENGTH, timeInSeconds)
                putExtra(AlarmClock.EXTRA_MESSAGE, title)
                putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error creating reminder", e)
            false
        }
    }
    
    // ==================== Camera & Photos ====================
    
    /**
     * Take a picture.
     */
    fun takePicture(): Boolean {
        return try {
            val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error opening camera", e)
            false
        }
    }
    
    // ==================== Web & Navigation ====================
    
    /**
     * Search the web.
     */
    fun searchWeb(query: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_WEB_SEARCH).apply {
                putExtra(SearchManager.QUERY, query)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error searching web", e)
            openUrl("https://www.google.com/search?q=${Uri.encode(query)}")
        }
    }
    
    /**
     * Open a URL in browser.
     */
    fun openUrl(url: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                data = Uri.parse(url)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error opening URL", e)
            false
        }
    }
    
    /**
     * Navigate to a destination.
     */
    fun navigate(destination: String): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                data = Uri.parse("google.navigation:q=${Uri.encode(destination)}")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error opening navigation", e)
            openUrl("https://www.google.com/maps/dir/?api=1&destination=${Uri.encode(destination)}")
        }
    }
    
    // ==================== Notifications ====================
    
    /**
     * Read current notifications.
     */
    fun readNotifications(): List<NotificationInfo> {
        // This requires NotificationListenerService - handled elsewhere
        return emptyList()
    }
    
    // ==================== Custom Commands ====================
    
    /**
     * Execute a custom action.
     */
    fun executeCustom(action: String, params: Map<String, Any>): Boolean {
        return try {
            // Custom action handling
            Log.d(TAG, "Custom action: $action with params: $params")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Error executing custom action", e)
            false
        }
    }
}

// Data classes
data class AppInfo(
    val name: String,
    val packageName: String,
    val icon: android.graphics.drawable.Drawable
)

data class NotificationInfo(
    val id: Int,
    val title: String,
    val text: String,
    val packageName: String,
    val timestamp: Long
)

// Missing import
import android.app.SearchManager
