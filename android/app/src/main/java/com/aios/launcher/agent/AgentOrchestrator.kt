package com.aios.launcher.agent

import android.content.Context
import android.util.Log
import com.aios.launcher.services.AIosNotificationListener
import com.aios.launcher.services.NotificationInfo
import com.aios.launcher.system.*
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext

/**
 * Master Agent Orchestrator for AI-OS. Coordinates all system components to provide complete device
 * control.
 */
@Singleton
class AgentOrchestrator
@Inject
constructor(
        @ApplicationContext private val context: Context,
        private val enhancedAgent: EnhancedAIAgent,
        private val deviceController: DeviceController,
        private val deepSystemController: DeepSystemController,
        private val systemSettings: SystemSettingsController,
        private val appManager: AppManager,
        private val devicePolicy: AIosDevicePolicyManager
) {
    companion object {
        private const val TAG = "AgentOrchestrator"
    }

    private val _agentState = MutableStateFlow<AgentState>(AgentState.Idle)
    val agentState: StateFlow<AgentState> = _agentState

    private val _lastResponse = MutableStateFlow<String>("")
    val lastResponse: StateFlow<String> = _lastResponse

    // ==================== Main Processing ====================

    /** Process a user command with full context. */
    suspend fun processCommand(command: String): OrchestratorResult =
            withContext(Dispatchers.Default) {
                _agentState.value = AgentState.Processing

                try {
                    // Capture current screen state
                    val screenContent = deepSystemController.captureScreenContent()

                    // Get device status
                    val deviceInfo = getDeviceStatus()

                    // Get notifications if available
                    val notifications = getNotifications()

                    // Process with enhanced agent
                    val response =
                            enhancedAgent.processWithContext(
                                    userInput = command,
                                    screenContent = screenContent
                            )

                    _lastResponse.value = response.response

                    // Execute actions
                    val actionResults =
                            if (response.actions.isNotEmpty()) {
                                _agentState.value = AgentState.Executing
                                enhancedAgent.executeActions(response.actions)
                            } else {
                                emptyList()
                            }

                    _agentState.value = AgentState.Idle

                    OrchestratorResult(
                            response = response.response,
                            thought = response.thought,
                            actionsExecuted = actionResults.size,
                            allSuccessful = actionResults.all { it.success },
                            screenContent = screenContent
                    )
                } catch (e: Exception) {
                    Log.e(TAG, "Command processing failed", e)
                    _agentState.value = AgentState.Error(e.message ?: "Unknown error")

                    OrchestratorResult(
                            response = "Sorry, I encountered an error: ${e.message}",
                            thought = "",
                            actionsExecuted = 0,
                            allSuccessful = false,
                            screenContent = null
                    )
                }
            }

    /** Process a voice command. */
    suspend fun processVoiceCommand(transcription: String): OrchestratorResult {
        _agentState.value = AgentState.Listening
        return processCommand(transcription)
    }

    // ==================== Device Status ====================

    /** Get comprehensive device status. */
    fun getDeviceStatus(): DeviceStatus {
        val deviceInfo = systemSettings.getDeviceInfo()
        val batteryInfo = systemSettings.getBatteryInfo()

        return DeviceStatus(
                manufacturer = deviceInfo.manufacturer,
                model = deviceInfo.model,
                androidVersion = deviceInfo.androidVersion,
                batteryLevel = batteryInfo.level,
                isCharging = batteryInfo.isCharging,
                brightness = systemSettings.getScreenBrightness(),
                mediaVolume = systemSettings.getMediaVolume(),
                ringVolume = systemSettings.getRingVolume(),
                ringerMode = systemSettings.getRingerMode(),
                isWifiEnabled = true, // Would need WifiManager
                isBluetoothEnabled = true, // Would need BluetoothManager
                isLocationEnabled = systemSettings.isLocationEnabled(),
                isAutoRotateEnabled = systemSettings.isAutoRotateEnabled(),
                isAirplaneModeEnabled = systemSettings.isAirplaneModeEnabled()
        )
    }

    // ==================== Notifications ====================

    /** Get current notifications. */
    fun getNotifications(): List<NotificationInfo> {
        return AIosNotificationListener.getInstance()?.getAllNotifications() ?: emptyList()
    }

    /** Get notification summary for AI. */
    fun getNotificationSummary(): String {
        return AIosNotificationListener.getInstance()?.getNotificationSummary()
                ?: "Notifications not available"
    }

    /** Dismiss a notification. */
    fun dismissNotification(key: String): Boolean {
        return AIosNotificationListener.getInstance()?.dismissNotification(key) ?: false
    }

    // ==================== App Management ====================

    /** Get installed apps. */
    suspend fun getInstalledApps(): List<AppInfo> {
        return appManager.getLaunchableApps()
    }

    /** Launch an app. */
    suspend fun launchApp(name: String): Boolean {
        return appManager.launchAppByName(name)
    }

    /** Search apps. */
    suspend fun searchApps(query: String): List<AppInfo> {
        return appManager.searchApps(query)
    }

    // ==================== Quick Actions ====================

    /** Quick action: Toggle flashlight. */
    fun toggleFlashlight(): Boolean {
        val currentState = false // Would need to track state
        return systemSettings.setFlashlight(!currentState)
    }

    /** Quick action: Toggle WiFi. */
    fun toggleWifi(): Boolean {
        // Would need WifiManager to check current state
        return false
    }

    /** Quick action: Toggle Bluetooth. */
    fun toggleBluetooth(): Boolean {
        // Would need BluetoothManager to check current state
        return false
    }

    /** Quick action: Set brightness. */
    fun setBrightness(level: Int): Boolean {
        return systemSettings.setScreenBrightness((level * 255) / 100)
    }

    /** Quick action: Set volume. */
    fun setVolume(level: Int): Boolean {
        return systemSettings.setMediaVolume(level)
    }

    /** Quick action: Take screenshot. */
    fun takeScreenshot(): Boolean {
        return deepSystemController.takeSystemScreenshot()
    }

    // ==================== Navigation ====================

    /** Go back. */
    fun goBack(): Boolean {
        return deepSystemController.pressBack()
    }

    /** Go home. */
    fun goHome(): Boolean {
        return deepSystemController.pressHome()
    }

    /** Open recents. */
    fun openRecents(): Boolean {
        return deepSystemController.openRecents()
    }

    /** Open notifications panel. */
    fun openNotifications(): Boolean {
        return deepSystemController.openNotifications()
    }

    /** Open quick settings. */
    fun openQuickSettings(): Boolean {
        return deepSystemController.openQuickSettings()
    }

    /** Lock the screen. */
    fun lockScreen(): Boolean {
        return deepSystemController.lockScreen()
    }

    // ==================== Permissions Check ====================

    /** Check if all required permissions are granted. */
    fun checkPermissions(): PermissionStatus {
        return PermissionStatus(
                accessibilityEnabled = isAccessibilityEnabled(),
                notificationListenerEnabled = isNotificationListenerEnabled(),
                overlayPermission = canDrawOverlays(),
                writeSettingsPermission = systemSettings.canWriteSettings(),
                deviceAdmin = devicePolicy.isDeviceAdmin(),
                deviceOwner = devicePolicy.isDeviceOwner()
        )
    }

    private fun isAccessibilityEnabled(): Boolean {
        val service = "${context.packageName}/.services.AgentAccessibilityService"
        val enabledServices =
                android.provider.Settings.Secure.getString(
                        context.contentResolver,
                        android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
                )
                        ?: ""
        return enabledServices.contains(service)
    }

    private fun isNotificationListenerEnabled(): Boolean {
        val service = "${context.packageName}/.services.AIosNotificationListener"
        val enabledListeners =
                android.provider.Settings.Secure.getString(
                        context.contentResolver,
                        "enabled_notification_listeners"
                )
                        ?: ""
        return enabledListeners.contains(service)
    }

    private fun canDrawOverlays(): Boolean {
        return android.provider.Settings.canDrawOverlays(context)
    }

    // ==================== Clear History ====================

    /** Clear conversation history. */
    fun clearConversation() {
        enhancedAgent.clearHistory()
        _lastResponse.value = ""
    }
}

// Data classes
sealed class AgentState {
    object Idle : AgentState()
    object Listening : AgentState()
    object Processing : AgentState()
    object Executing : AgentState()
    data class Error(val message: String) : AgentState()
}

data class OrchestratorResult(
        val response: String,
        val thought: String,
        val actionsExecuted: Int,
        val allSuccessful: Boolean,
        val screenContent: ScreenContent?
)

data class DeviceStatus(
        val manufacturer: String,
        val model: String,
        val androidVersion: String,
        val batteryLevel: Int,
        val isCharging: Boolean,
        val brightness: Int,
        val mediaVolume: Int,
        val ringVolume: Int,
        val ringerMode: RingerMode,
        val isWifiEnabled: Boolean,
        val isBluetoothEnabled: Boolean,
        val isLocationEnabled: Boolean,
        val isAutoRotateEnabled: Boolean,
        val isAirplaneModeEnabled: Boolean
)

data class PermissionStatus(
        val accessibilityEnabled: Boolean,
        val notificationListenerEnabled: Boolean,
        val overlayPermission: Boolean,
        val writeSettingsPermission: Boolean,
        val deviceAdmin: Boolean,
        val deviceOwner: Boolean
) {
    val allEssentialGranted: Boolean
        get() = accessibilityEnabled && overlayPermission

    val allOptionalGranted: Boolean
        get() = notificationListenerEnabled && writeSettingsPermission
}
