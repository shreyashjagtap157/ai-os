package com.aios.launcher.services

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import dagger.hilt.android.AndroidEntryPoint
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Notification Listener Service for AI-OS. Allows AI agent to read, summarize, and act on
 * notifications.
 */
@AndroidEntryPoint
class AIosNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "AIosNotificationListener"

        private val _notifications = MutableStateFlow<List<NotificationInfo>>(emptyList())
        val notifications: StateFlow<List<NotificationInfo>> = _notifications

        private val _newNotification = MutableStateFlow<NotificationInfo?>(null)
        val newNotification: StateFlow<NotificationInfo?> = _newNotification

        private var instance: AIosNotificationListener? = null

        fun getInstance(): AIosNotificationListener? = instance

        fun isServiceRunning(): Boolean = instance != null
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        instance = this
        Log.i(TAG, "Notification listener service created")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        Log.i(TAG, "Notification listener service destroyed")
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        Log.i(TAG, "Notification listener connected")

        // Fetch existing notifications
        scope.launch { refreshNotifications() }
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        Log.i(TAG, "Notification listener disconnected")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        super.onNotificationPosted(sbn)
        Log.d(TAG, "Notification posted: ${sbn.packageName}")

        scope.launch {
            val info = extractNotificationInfo(sbn)
            _newNotification.value = info
            refreshNotifications()
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        super.onNotificationRemoved(sbn)
        Log.d(TAG, "Notification removed: ${sbn.packageName}")

        scope.launch { refreshNotifications() }
    }

    private fun refreshNotifications() {
        try {
            val activeNotifications = activeNotifications ?: return
            val notificationList = activeNotifications.map { extractNotificationInfo(it) }
            _notifications.value = notificationList
        } catch (e: Exception) {
            Log.e(TAG, "Failed to refresh notifications", e)
        }
    }

    private fun extractNotificationInfo(sbn: StatusBarNotification): NotificationInfo {
        val notification = sbn.notification
        val extras = notification.extras

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString() ?: ""
        val subText = extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString() ?: ""

        val appName =
                try {
                    val pm = packageManager
                    val appInfo = pm.getApplicationInfo(sbn.packageName, 0)
                    pm.getApplicationLabel(appInfo).toString()
                } catch (e: Exception) {
                    sbn.packageName
                }

        val time =
                Instant.ofEpochMilli(sbn.postTime)
                        .atZone(ZoneId.systemDefault())
                        .format(DateTimeFormatter.ofPattern("HH:mm"))

        // Get actions
        val actions =
                notification.actions?.map { action ->
                    NotificationAction(
                            title = action.title?.toString() ?: "",
                            actionIntent = action.actionIntent
                    )
                }
                        ?: emptyList()

        return NotificationInfo(
                key = sbn.key,
                packageName = sbn.packageName,
                appName = appName,
                title = title,
                text = text,
                bigText = bigText.ifEmpty { text },
                subText = subText,
                time = time,
                timestamp = sbn.postTime,
                isOngoing = sbn.isOngoing,
                isClearable = sbn.isClearable,
                actions = actions,
                category = notification.category ?: ""
        )
    }

    // ==================== Agent Actions ====================

    /** Get all current notifications. */
    fun getAllNotifications(): List<NotificationInfo> {
        return _notifications.value
    }

    /** Get notifications from a specific app. */
    fun getNotificationsFromApp(packageName: String): List<NotificationInfo> {
        return _notifications.value.filter { it.packageName == packageName }
    }

    /** Get unread/active notifications count. */
    fun getNotificationCount(): Int {
        return _notifications.value.size
    }

    /** Dismiss a specific notification. */
    fun dismissNotification(key: String): Boolean {
        return try {
            cancelNotification(key)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to dismiss notification", e)
            false
        }
    }

    /** Dismiss all notifications. */
    fun dismissAllNotifications(): Boolean {
        return try {
            cancelAllNotifications()
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to dismiss all notifications", e)
            false
        }
    }

    /** Dismiss notifications from a specific app. */
    fun dismissNotificationsFromApp(packageName: String): Boolean {
        return try {
            _notifications.value
                    .filter { it.packageName == packageName && it.isClearable }
                    .forEach { cancelNotification(it.key) }
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to dismiss app notifications", e)
            false
        }
    }

    /** Click a notification action. */
    fun clickNotificationAction(notificationKey: String, actionIndex: Int): Boolean {
        val info = _notifications.value.find { it.key == notificationKey } ?: return false
        val action = info.actions.getOrNull(actionIndex) ?: return false

        return try {
            action.actionIntent?.send()
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to click notification action", e)
            false
        }
    }

    /** Get notification summary for AI. */
    fun getNotificationSummary(): String {
        val notifications = _notifications.value

        if (notifications.isEmpty()) {
            return "No notifications"
        }

        val byApp = notifications.groupBy { it.appName }
        val summary = StringBuilder()

        summary.append("You have ${notifications.size} notifications:\n\n")

        byApp.forEach { (app, appNotifications) ->
            summary.append("$app (${appNotifications.size}):\n")
            appNotifications.take(3).forEach { notif ->
                summary.append("  - ${notif.title}: ${notif.text.take(50)}\n")
            }
            if (appNotifications.size > 3) {
                summary.append("  ... and ${appNotifications.size - 3} more\n")
            }
            summary.append("\n")
        }

        return summary.toString()
    }

    /** Search notifications by content. */
    fun searchNotifications(query: String): List<NotificationInfo> {
        val queryLower = query.lowercase()
        return _notifications.value.filter {
            it.title.lowercase().contains(queryLower) ||
                    it.text.lowercase().contains(queryLower) ||
                    it.bigText.lowercase().contains(queryLower) ||
                    it.appName.lowercase().contains(queryLower)
        }
    }
}

data class NotificationInfo(
        val key: String,
        val packageName: String,
        val appName: String,
        val title: String,
        val text: String,
        val bigText: String,
        val subText: String,
        val time: String,
        val timestamp: Long,
        val isOngoing: Boolean,
        val isClearable: Boolean,
        val actions: List<NotificationAction>,
        val category: String
)

data class NotificationAction(val title: String, val actionIntent: android.app.PendingIntent?)
