package com.aios.launcher.services

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aios.launcher.AIosApplication
import com.aios.launcher.R
import com.aios.launcher.agent.AIAgent
import com.aios.launcher.agent.AgentCommand
import com.aios.launcher.agent.DeviceController
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import javax.inject.Inject

/**
 * AI Agent Foreground Service.
 * Runs continuously to handle voice commands and AI interactions.
 */
@AndroidEntryPoint
class AgentService : Service() {
    
    companion object {
        private const val TAG = "AgentService"
        private const val NOTIFICATION_ID = 1001
        
        fun start(context: Context) {
            val intent = Intent(context, AgentService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
        
        fun stop(context: Context) {
            context.stopService(Intent(context, AgentService::class.java))
        }
    }
    
    @Inject lateinit var aiAgent: AIAgent
    @Inject lateinit var deviceController: DeviceController
    
    private val binder = AgentBinder()
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    private val _isListening = MutableStateFlow(false)
    val isListening: StateFlow<Boolean> = _isListening
    
    private val _agentState = MutableStateFlow<AgentState>(AgentState.Idle)
    val agentState: StateFlow<AgentState> = _agentState
    
    inner class AgentBinder : Binder() {
        fun getService(): AgentService = this@AgentService
    }
    
    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "AgentService created")
        startForeground(NOTIFICATION_ID, createNotification())
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "AgentService started")
        return START_STICKY
    }
    
    override fun onBind(intent: Intent): IBinder = binder
    
    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        Log.d(TAG, "AgentService destroyed")
    }
    
    /**
     * Process a user command through the AI agent.
     */
    suspend fun processCommand(command: String): String {
        _agentState.value = AgentState.Processing
        
        return try {
            val response = aiAgent.process(command)
            
            // Check if AI wants to execute a device command
            val deviceCommand = aiAgent.extractDeviceCommand(response)
            if (deviceCommand != null) {
                executeDeviceCommand(deviceCommand)
            }
            
            _agentState.value = AgentState.Idle
            response
        } catch (e: Exception) {
            Log.e(TAG, "Error processing command", e)
            _agentState.value = AgentState.Error(e.message ?: "Unknown error")
            "Sorry, I encountered an error: ${e.message}"
        }
    }
    
    /**
     * Execute a device control command.
     */
    private suspend fun executeDeviceCommand(command: AgentCommand) {
        when (command) {
            is AgentCommand.OpenApp -> deviceController.openApp(command.packageName)
            is AgentCommand.Call -> deviceController.makeCall(command.phoneNumber)
            is AgentCommand.SendSMS -> deviceController.sendSMS(command.phoneNumber, command.message)
            is AgentCommand.SetAlarm -> deviceController.setAlarm(command.hour, command.minute)
            is AgentCommand.TakePicture -> deviceController.takePicture()
            is AgentCommand.SetBrightness -> deviceController.setBrightness(command.level)
            is AgentCommand.ToggleWifi -> deviceController.toggleWifi(command.enable)
            is AgentCommand.ToggleBluetooth -> deviceController.toggleBluetooth(command.enable)
            is AgentCommand.PlayMusic -> deviceController.playMusic(command.query)
            is AgentCommand.SetVolume -> deviceController.setVolume(command.level)
            is AgentCommand.OpenSettings -> deviceController.openSettings(command.section)
            is AgentCommand.SearchWeb -> deviceController.searchWeb(command.query)
            is AgentCommand.Navigate -> deviceController.navigate(command.destination)
            is AgentCommand.CreateReminder -> deviceController.createReminder(command.title, command.time)
            is AgentCommand.ReadNotifications -> deviceController.readNotifications()
            is AgentCommand.Custom -> deviceController.executeCustom(command.action, command.params)
        }
    }
    
    /**
     * Start continuous voice listening.
     */
    fun startVoiceListening() {
        _isListening.value = true
        // Start voice recognition service
        VoiceRecognitionService.start(this)
    }
    
    /**
     * Stop voice listening.
     */
    fun stopVoiceListening() {
        _isListening.value = false
        VoiceRecognitionService.stop(this)
    }
    
    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            packageManager.getLaunchIntentForPackage(packageName),
            PendingIntent.FLAG_IMMUTABLE
        )
        
        return NotificationCompat.Builder(this, AIosApplication.AGENT_CHANNEL_ID)
            .setContentTitle("AI-OS Agent")
            .setContentText("AI Agent is running")
            .setSmallIcon(R.drawable.ic_agent)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }
}

sealed class AgentState {
    object Idle : AgentState()
    object Listening : AgentState()
    object Processing : AgentState()
    data class Responding(val text: String) : AgentState()
    data class Error(val message: String) : AgentState()
}
