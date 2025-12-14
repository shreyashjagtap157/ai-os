package com.aios.launcher.agent

import android.content.Context
import android.util.Log
import com.aios.launcher.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

/**
 * AI Agent for AI-OS.
 * Handles natural language processing and command extraction.
 */
@Singleton
class AIAgent @Inject constructor(
    @ApplicationContext private val context: Context,
    private val deviceController: DeviceController
) {
    companion object {
        private const val TAG = "AIAgent"
        private const val OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
        private const val ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    }
    
    private val httpClient = OkHttpClient.Builder()
        .callTimeout(java.time.Duration.ofSeconds(60))
        .build()
    
    private val conversationHistory = mutableListOf<Message>()
    
    private val systemPrompt = """
You are AI-OS, an intelligent Android operating system assistant.
You can control the device and help users with their tasks through natural language.

Available device commands (respond with JSON when you want to execute):
- {"action": "open_app", "app": "app name or package"}
- {"action": "call", "number": "phone number"}
- {"action": "sms", "number": "phone number", "message": "text"}
- {"action": "alarm", "hour": 8, "minute": 30}
- {"action": "brightness", "level": 0-255}
- {"action": "volume", "level": 0-100}
- {"action": "wifi", "enable": true/false}
- {"action": "bluetooth", "enable": true/false}
- {"action": "camera"}
- {"action": "search", "query": "search terms"}
- {"action": "navigate", "destination": "address"}
- {"action": "settings", "section": "wifi/bluetooth/display/sound/etc"}
- {"action": "reminder", "title": "text", "seconds": 300}

When user asks to perform a device action:
1. Acknowledge the request
2. Include the JSON command in your response wrapped in ```json ... ```
3. Confirm what you're doing

Be helpful, friendly, and conversational. You're the user's AI assistant for their phone.
""".trimIndent()
    
    init {
        conversationHistory.add(Message("system", systemPrompt))
    }
    
    /**
     * Process a natural language command.
     */
    suspend fun process(userInput: String): String = withContext(Dispatchers.IO) {
        conversationHistory.add(Message("user", userInput))
        
        val response = try {
            if (BuildConfig.OPENAI_API_KEY.isNotBlank()) {
                callOpenAI(conversationHistory)
            } else if (BuildConfig.ANTHROPIC_API_KEY.isNotBlank()) {
                callAnthropic(conversationHistory)
            } else {
                processLocally(userInput)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error processing command", e)
            "Sorry, I encountered an error: ${e.message}"
        }
        
        conversationHistory.add(Message("assistant", response))
        
        // Keep history manageable
        if (conversationHistory.size > 20) {
            conversationHistory.removeAt(1) // Keep system prompt
            conversationHistory.removeAt(1)
        }
        
        response
    }
    
    /**
     * Extract device command from AI response.
     */
    fun extractDeviceCommand(response: String): AgentCommand? {
        // Look for JSON command in response
        val jsonPattern = "```json\\s*(\\{[^}]+\\})\\s*```".toRegex()
        val match = jsonPattern.find(response) ?: return null
        
        return try {
            val json = JSONObject(match.groupValues[1])
            parseCommand(json)
        } catch (e: Exception) {
            Log.e(TAG, "Error parsing command", e)
            null
        }
    }
    
    private fun parseCommand(json: JSONObject): AgentCommand? {
        return when (json.optString("action")) {
            "open_app" -> AgentCommand.OpenApp(json.getString("app"))
            "call" -> AgentCommand.Call(json.getString("number"))
            "sms" -> AgentCommand.SendSMS(
                json.getString("number"),
                json.getString("message")
            )
            "alarm" -> AgentCommand.SetAlarm(
                json.getInt("hour"),
                json.getInt("minute")
            )
            "brightness" -> AgentCommand.SetBrightness(json.getInt("level"))
            "volume" -> AgentCommand.SetVolume(json.getInt("level"))
            "wifi" -> AgentCommand.ToggleWifi(json.getBoolean("enable"))
            "bluetooth" -> AgentCommand.ToggleBluetooth(json.getBoolean("enable"))
            "camera" -> AgentCommand.TakePicture
            "search" -> AgentCommand.SearchWeb(json.getString("query"))
            "navigate" -> AgentCommand.Navigate(json.getString("destination"))
            "settings" -> AgentCommand.OpenSettings(json.optString("section"))
            "reminder" -> AgentCommand.CreateReminder(
                json.getString("title"),
                json.getInt("seconds")
            )
            else -> null
        }
    }
    
    private suspend fun callOpenAI(messages: List<Message>): String {
        val messagesArray = JSONArray().apply {
            messages.forEach { msg ->
                put(JSONObject().apply {
                    put("role", msg.role)
                    put("content", msg.content)
                })
            }
        }
        
        val requestBody = JSONObject().apply {
            put("model", "gpt-4")
            put("messages", messagesArray)
            put("temperature", 0.7)
            put("max_tokens", 1024)
        }
        
        val request = Request.Builder()
            .url(OPENAI_API_URL)
            .addHeader("Authorization", "Bearer ${BuildConfig.OPENAI_API_KEY}")
            .addHeader("Content-Type", "application/json")
            .post(requestBody.toString().toRequestBody("application/json".toMediaType()))
            .build()
        
        val response = httpClient.newCall(request).execute()
        val responseBody = response.body?.string() ?: throw Exception("Empty response")
        
        if (!response.isSuccessful) {
            throw Exception("API error: ${response.code} - $responseBody")
        }
        
        val json = JSONObject(responseBody)
        return json.getJSONArray("choices")
            .getJSONObject(0)
            .getJSONObject("message")
            .getString("content")
    }
    
    private suspend fun callAnthropic(messages: List<Message>): String {
        val systemMsg = messages.firstOrNull { it.role == "system" }?.content ?: ""
        val conversationMessages = messages.filter { it.role != "system" }
        
        val messagesArray = JSONArray().apply {
            conversationMessages.forEach { msg ->
                put(JSONObject().apply {
                    put("role", if (msg.role == "assistant") "assistant" else "user")
                    put("content", msg.content)
                })
            }
        }
        
        val requestBody = JSONObject().apply {
            put("model", "claude-3-opus-20240229")
            put("max_tokens", 1024)
            put("system", systemMsg)
            put("messages", messagesArray)
        }
        
        val request = Request.Builder()
            .url(ANTHROPIC_API_URL)
            .addHeader("x-api-key", BuildConfig.ANTHROPIC_API_KEY)
            .addHeader("anthropic-version", "2023-06-01")
            .addHeader("Content-Type", "application/json")
            .post(requestBody.toString().toRequestBody("application/json".toMediaType()))
            .build()
        
        val response = httpClient.newCall(request).execute()
        val responseBody = response.body?.string() ?: throw Exception("Empty response")
        
        if (!response.isSuccessful) {
            throw Exception("API error: ${response.code} - $responseBody")
        }
        
        val json = JSONObject(responseBody)
        return json.getJSONArray("content")
            .getJSONObject(0)
            .getString("text")
    }
    
    private fun processLocally(input: String): String {
        val lowerInput = input.lowercase()
        
        return when {
            "time" in lowerInput -> {
                val time = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault())
                    .format(java.util.Date())
                "The current time is $time"
            }
            "date" in lowerInput -> {
                val date = java.text.SimpleDateFormat("EEEE, MMMM d, yyyy", java.util.Locale.getDefault())
                    .format(java.util.Date())
                "Today is $date"
            }
            "open" in lowerInput -> {
                val appName = input.replace("open", "", ignoreCase = true).trim()
                """I'll open $appName for you.
```json
{"action": "open_app", "app": "$appName"}
```"""
            }
            "call" in lowerInput -> {
                "I'm running in local mode. Please configure an API key for full call functionality."
            }
            "help" in lowerInput -> {
                """I can help you with:
• Open apps: "Open YouTube"
• Make calls: "Call John" (requires API key)  
• Send texts: "Text Mom I'm on my way"
• Set alarms: "Wake me up at 7am"
• Control settings: "Turn on WiFi"
• Search: "Search for Italian restaurants"
• Navigate: "Navigate to Central Park"

For full AI capabilities, please add your OpenAI or Anthropic API key in settings."""
            }
            else -> {
                "I'm running in local mode with limited capabilities. Configure an API key in settings for full AI features. Try 'help' to see what I can do locally."
            }
        }
    }
    
    fun clearHistory() {
        conversationHistory.clear()
        conversationHistory.add(Message("system", systemPrompt))
    }
}

data class Message(
    val role: String,
    val content: String
)

sealed class AgentCommand {
    data class OpenApp(val packageName: String) : AgentCommand()
    data class Call(val phoneNumber: String) : AgentCommand()
    data class SendSMS(val phoneNumber: String, val message: String) : AgentCommand()
    data class SetAlarm(val hour: Int, val minute: Int) : AgentCommand()
    object TakePicture : AgentCommand()
    data class SetBrightness(val level: Int) : AgentCommand()
    data class ToggleWifi(val enable: Boolean) : AgentCommand()
    data class ToggleBluetooth(val enable: Boolean) : AgentCommand()
    data class PlayMusic(val query: String) : AgentCommand()
    data class SetVolume(val level: Int) : AgentCommand()
    data class OpenSettings(val section: String?) : AgentCommand()
    data class SearchWeb(val query: String) : AgentCommand()
    data class Navigate(val destination: String) : AgentCommand()
    data class CreateReminder(val title: String, val time: Int) : AgentCommand()
    object ReadNotifications : AgentCommand()
    data class Custom(val action: String, val params: Map<String, Any>) : AgentCommand()
}
