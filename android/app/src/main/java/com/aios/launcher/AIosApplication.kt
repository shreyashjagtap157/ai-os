package com.aios.launcher

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import dagger.hilt.android.HiltAndroidApp

/**
 * AI-OS Application class.
 * Initializes Hilt dependency injection and notification channels.
 */
@HiltAndroidApp
class AIosApplication : Application() {
    
    companion object {
        const val AGENT_CHANNEL_ID = "aios_agent_channel"
        const val VOICE_CHANNEL_ID = "aios_voice_channel"
        const val NOTIFICATION_CHANNEL_ID = "aios_notification_channel"
    }
    
    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }
    
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = getSystemService(NotificationManager::class.java)
            
            // Agent foreground service channel
            val agentChannel = NotificationChannel(
                AGENT_CHANNEL_ID,
                "AI Agent",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "AI-OS Agent background service"
                setShowBadge(false)
            }
            
            // Voice recognition channel
            val voiceChannel = NotificationChannel(
                VOICE_CHANNEL_ID,
                "Voice Recognition",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Voice command recognition"
            }
            
            // General notifications channel
            val notificationChannel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "AI-OS Notifications",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "AI-OS alerts and notifications"
            }
            
            notificationManager.createNotificationChannels(
                listOf(agentChannel, voiceChannel, notificationChannel)
            )
        }
    }
}
