package com.aios.launcher.receivers

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.aios.launcher.services.AgentService

/** Boot Receiver for AI-OS. Starts the agent service when device boots. */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED ||
                        intent.action == "android.intent.action.QUICKBOOT_POWERON"
        ) {

            Log.i(TAG, "Device booted, starting AI-OS Agent Service")

            // Start the agent service
            val serviceIntent = Intent(context, AgentService::class.java)

            try {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent)
                } else {
                    context.startService(serviceIntent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start agent service on boot", e)
            }
        }
    }
}
