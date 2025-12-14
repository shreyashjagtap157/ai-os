package com.aios.launcher.agent

import android.content.Context
import android.graphics.Bitmap
import android.util.Base64
import android.util.Log
import com.aios.launcher.BuildConfig
import com.aios.launcher.system.DeepSystemController
import com.aios.launcher.system.ScreenContent
import com.aios.launcher.system.SystemSettingsController
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.ByteArrayOutputStream
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/**
 * Enhanced AI Agent with Visual Understanding and Full Device Control. This agent can see the
 * screen, understand context, and control any app.
 */
@Singleton
class EnhancedAIAgent
@Inject
constructor(
        @ApplicationContext private val context: Context,
        private val deviceController: DeviceController,
        private val deepSystemController: DeepSystemController,
        private val systemSettings: SystemSettingsController
) {
    companion object {
        private const val TAG = "EnhancedAIAgent"
        private const val OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
        private const val ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    }

    private val httpClient =
            OkHttpClient.Builder().callTimeout(java.time.Duration.ofSeconds(120)).build()

    private val conversationHistory = mutableListOf<Message>()

    private val systemPrompt =
            """
You are AI-OS, an intelligent operating system that has COMPLETE control over this Android device.
You can see the screen, understand what apps are showing, and control every aspect of the device.

## Your Capabilities:

### Screen Understanding
- You can see the current screen content (list of UI elements with text, positions, states)
- You can identify which app is running and what it's showing
- You can understand context from visual information

### Touch/Gesture Control
- Tap on any coordinates or UI element
- Long press
- Swipe in any direction
- Scroll up/down/left/right
- Type text into any field

### System Navigation
- Press Back, Home, Recent Apps
- Open notifications and quick settings
- Lock screen, take screenshots
- Toggle split screen

### Device Settings
- Brightness (0-255)
- Volume (media, ring, alarm)
- WiFi, Bluetooth, Location
- Ringer mode (normal, vibrate, silent)
- Do Not Disturb
- Flashlight
- Screen timeout
- Auto-rotate

### App Control
- Open any installed app
- Close apps
- Switch between apps
- Control in-app actions

### Communication
- Make calls
- Send SMS
- Read notifications

## Response Format

When you need to perform an action, respond with JSON:

```json
{
  "thought": "What I understand and plan to do",
  "actions": [
    {"type": "action_type", "params": {...}},
    ...
  ],
  "response": "What to say to the user"
}
```

### Available Action Types:

**Touch Actions:**
- {"type": "tap", "params": {"x": 500, "y": 800}}
- {"type": "tap_element", "params": {"text": "Settings"}}
- {"type": "tap_id", "params": {"id": "com.app:id/button"}}
- {"type": "long_press", "params": {"x": 500, "y": 800, "duration": 1000}}
- {"type": "swipe", "params": {"startX": 500, "startY": 1500, "endX": 500, "endY": 500, "duration": 300}}
- {"type": "scroll", "params": {"direction": "up|down|left|right"}}
- {"type": "type_text", "params": {"text": "Hello world"}}
- {"type": "clear_text", "params": {}}

**Navigation Actions:**
- {"type": "back", "params": {}}
- {"type": "home", "params": {}}
- {"type": "recents", "params": {}}
- {"type": "notifications", "params": {}}
- {"type": "quick_settings", "params": {}}
- {"type": "lock_screen", "params": {}}
- {"type": "screenshot", "params": {}}

**Settings Actions:**
- {"type": "brightness", "params": {"value": 128}}
- {"type": "volume_media", "params": {"value": 50}}
- {"type": "volume_ring", "params": {"value": 50}}
- {"type": "ringer_mode", "params": {"mode": "normal|vibrate|silent"}}
- {"type": "dnd", "params": {"enabled": true}}
- {"type": "flashlight", "params": {"enabled": true}}
- {"type": "auto_rotate", "params": {"enabled": true}}
- {"type": "screen_timeout", "params": {"ms": 60000}}

**App Actions:**
- {"type": "open_app", "params": {"name": "Chrome"}}
- {"type": "call", "params": {"number": "+1234567890"}}
- {"type": "sms", "params": {"number": "+1234567890", "message": "Hello"}}

**Wait Actions:**
- {"type": "wait", "params": {"ms": 1000}}

## Important Guidelines

1. ALWAYS analyze the current screen content before taking action
2. If you can't find an element, try scrolling or navigating
3. For multi-step tasks, execute actions in sequence
4. Confirm dangerous actions (calls, SMS, settings changes)
5. Be proactive but careful - you have real control
6. If something fails, try alternative approaches
"""

    init {
        conversationHistory.add(Message("system", systemPrompt))
    }

    /** Process a command with visual context. */
    suspend fun processWithContext(
            userInput: String,
            screenContent: ScreenContent?,
            screenshot: Bitmap? = null
    ): AgentResponse =
            withContext(Dispatchers.IO) {

                // Build context message
                val contextBuilder = StringBuilder()
                contextBuilder.append("User command: $userInput\n\n")

                if (screenContent != null) {
                    contextBuilder.append("Current Screen:\n")
                    contextBuilder.append("- App: ${screenContent.packageName}\n")
                    contextBuilder.append("- Activity: ${screenContent.activityName}\n")
                    contextBuilder.append("\nVisible UI Elements:\n")

                    screenContent
                            .elements
                            .filter {
                                it.text.isNotEmpty() ||
                                        it.contentDescription.isNotEmpty() ||
                                        it.isClickable
                            }
                            .take(50) // Limit for token management
                            .forEachIndexed { index, element ->
                                val text = element.text.ifEmpty { element.contentDescription }
                                val props = mutableListOf<String>()
                                if (element.isClickable) props.add("clickable")
                                if (element.isEditable) props.add("editable")
                                if (element.isScrollable) props.add("scrollable")
                                if (element.isChecked) props.add("checked")

                                contextBuilder.append(
                                        "[$index] \"$text\" at (${element.bounds.centerX()}, ${element.bounds.centerY()})"
                                )
                                if (element.id.isNotEmpty()) {
                                    contextBuilder.append(" id=${element.id}")
                                }
                                if (props.isNotEmpty()) {
                                    contextBuilder.append(" [${props.joinToString(", ")}]")
                                }
                                contextBuilder.append("\n")
                            }
                }

                conversationHistory.add(Message("user", contextBuilder.toString()))

                val response =
                        try {
                            if (BuildConfig.OPENAI_API_KEY.isNotBlank()) {
                                if (screenshot != null) {
                                    callOpenAIWithVision(conversationHistory, screenshot)
                                } else {
                                    callOpenAI(conversationHistory)
                                }
                            } else if (BuildConfig.ANTHROPIC_API_KEY.isNotBlank()) {
                                callAnthropic(conversationHistory)
                            } else {
                                processLocally(userInput, screenContent)
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "AI processing error", e)
                            """{"thought": "Error occurred", "actions": [], "response": "Sorry, I encountered an error: ${e.message}"}"""
                        }

                conversationHistory.add(Message("assistant", response))

                // Keep history manageable
                if (conversationHistory.size > 20) {
                    conversationHistory.removeAt(1)
                    conversationHistory.removeAt(1)
                }

                parseAgentResponse(response)
            }

    /** Execute a sequence of actions. */
    suspend fun executeActions(actions: List<AgentAction>): List<ActionResult> {
        val results = mutableListOf<ActionResult>()

        for (action in actions) {
            val result = executeAction(action)
            results.add(result)

            // Small delay between actions
            if (result.success) {
                kotlinx.coroutines.delay(200)
            }
        }

        return results
    }

    private suspend fun executeAction(action: AgentAction): ActionResult {
        return try {
            val success =
                    when (action.type) {
                        // Touch actions
                        "tap" -> {
                            val x = action.params["x"]?.toString()?.toFloatOrNull() ?: 0f
                            val y = action.params["y"]?.toString()?.toFloatOrNull() ?: 0f
                            deepSystemController.tap(x, y)
                        }
                        "tap_element" -> {
                            val text = action.params["text"]?.toString() ?: ""
                            deepSystemController.clickByText(text)
                        }
                        "tap_id" -> {
                            val id = action.params["id"]?.toString() ?: ""
                            deepSystemController.clickById(id)
                        }
                        "long_press" -> {
                            val x = action.params["x"]?.toString()?.toFloatOrNull() ?: 0f
                            val y = action.params["y"]?.toString()?.toFloatOrNull() ?: 0f
                            val duration =
                                    action.params["duration"]?.toString()?.toLongOrNull() ?: 1000L
                            deepSystemController.longPress(x, y, duration)
                        }
                        "swipe" -> {
                            val startX = action.params["startX"]?.toString()?.toFloatOrNull() ?: 0f
                            val startY = action.params["startY"]?.toString()?.toFloatOrNull() ?: 0f
                            val endX = action.params["endX"]?.toString()?.toFloatOrNull() ?: 0f
                            val endY = action.params["endY"]?.toString()?.toFloatOrNull() ?: 0f
                            val duration =
                                    action.params["duration"]?.toString()?.toLongOrNull() ?: 300L
                            deepSystemController.swipe(startX, startY, endX, endY, duration)
                        }
                        "scroll" -> {
                            val direction = action.params["direction"]?.toString() ?: "down"
                            val scrollDir =
                                    when (direction.lowercase()) {
                                        "up" -> com.aios.launcher.system.ScrollDirection.UP
                                        "down" -> com.aios.launcher.system.ScrollDirection.DOWN
                                        "left" -> com.aios.launcher.system.ScrollDirection.LEFT
                                        "right" -> com.aios.launcher.system.ScrollDirection.RIGHT
                                        else -> com.aios.launcher.system.ScrollDirection.DOWN
                                    }
                            deepSystemController.scroll(scrollDir)
                        }
                        "type_text" -> {
                            val text = action.params["text"]?.toString() ?: ""
                            deepSystemController.typeText(text)
                        }
                        "clear_text" -> {
                            deepSystemController.clearText()
                        }

                        // Navigation
                        "back" -> deepSystemController.pressBack()
                        "home" -> deepSystemController.pressHome()
                        "recents" -> deepSystemController.openRecents()
                        "notifications" -> deepSystemController.openNotifications()
                        "quick_settings" -> deepSystemController.openQuickSettings()
                        "lock_screen" -> deepSystemController.lockScreen()
                        "screenshot" -> deepSystemController.takeSystemScreenshot()

                        // Settings
                        "brightness" -> {
                            val value = action.params["value"]?.toString()?.toIntOrNull() ?: 128
                            systemSettings.setScreenBrightness(value)
                        }
                        "volume_media" -> {
                            val value = action.params["value"]?.toString()?.toIntOrNull() ?: 50
                            systemSettings.setMediaVolume(value)
                        }
                        "volume_ring" -> {
                            val value = action.params["value"]?.toString()?.toIntOrNull() ?: 50
                            systemSettings.setRingVolume(value)
                        }
                        "ringer_mode" -> {
                            val mode = action.params["mode"]?.toString() ?: "normal"
                            val ringerMode =
                                    when (mode.lowercase()) {
                                        "normal" -> com.aios.launcher.system.RingerMode.NORMAL
                                        "vibrate" -> com.aios.launcher.system.RingerMode.VIBRATE
                                        "silent" -> com.aios.launcher.system.RingerMode.SILENT
                                        else -> com.aios.launcher.system.RingerMode.NORMAL
                                    }
                            systemSettings.setRingerMode(ringerMode)
                        }
                        "dnd" -> {
                            val enabled = action.params["enabled"]?.toString()?.toBoolean() ?: false
                            systemSettings.setDoNotDisturb(enabled)
                        }
                        "flashlight" -> {
                            val enabled = action.params["enabled"]?.toString()?.toBoolean() ?: false
                            systemSettings.setFlashlight(enabled)
                        }
                        "auto_rotate" -> {
                            val enabled = action.params["enabled"]?.toString()?.toBoolean() ?: false
                            systemSettings.setAutoRotate(enabled)
                        }
                        "screen_timeout" -> {
                            val ms = action.params["ms"]?.toString()?.toIntOrNull() ?: 60000
                            systemSettings.setScreenTimeout(ms)
                        }

                        // App control
                        "open_app" -> {
                            val name = action.params["name"]?.toString() ?: ""
                            deviceController.openApp(name)
                        }
                        "call" -> {
                            val number = action.params["number"]?.toString() ?: ""
                            deviceController.makeCall(number)
                        }
                        "sms" -> {
                            val number = action.params["number"]?.toString() ?: ""
                            val message = action.params["message"]?.toString() ?: ""
                            deviceController.sendSMS(number, message)
                        }

                        // Wait
                        "wait" -> {
                            val ms = action.params["ms"]?.toString()?.toLongOrNull() ?: 1000L
                            kotlinx.coroutines.delay(ms)
                            true
                        }
                        else -> {
                            Log.w(TAG, "Unknown action type: ${action.type}")
                            false
                        }
                    }

            ActionResult(action.type, success, null)
        } catch (e: Exception) {
            Log.e(TAG, "Action execution failed: ${action.type}", e)
            ActionResult(action.type, false, e.message)
        }
    }

    private suspend fun callOpenAI(messages: List<Message>): String {
        val messagesArray =
                JSONArray().apply {
                    messages.forEach { msg ->
                        put(
                                JSONObject().apply {
                                    put("role", msg.role)
                                    put("content", msg.content)
                                }
                        )
                    }
                }

        val requestBody =
                JSONObject().apply {
                    put("model", "gpt-4-turbo-preview")
                    put("messages", messagesArray)
                    put("temperature", 0.7)
                    put("max_tokens", 2048)
                }

        val request =
                Request.Builder()
                        .url(OPENAI_API_URL)
                        .addHeader("Authorization", "Bearer ${BuildConfig.OPENAI_API_KEY}")
                        .addHeader("Content-Type", "application/json")
                        .post(
                                requestBody
                                        .toString()
                                        .toRequestBody("application/json".toMediaType())
                        )
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

    private suspend fun callOpenAIWithVision(messages: List<Message>, screenshot: Bitmap): String {
        // Convert bitmap to base64
        val outputStream = ByteArrayOutputStream()
        screenshot.compress(Bitmap.CompressFormat.JPEG, 70, outputStream)
        val base64Image = Base64.encodeToString(outputStream.toByteArray(), Base64.NO_WRAP)

        val lastMessage = messages.last()
        val messagesWithImage = messages.dropLast(1).toMutableList()

        // Add message with image
        val contentArray =
                JSONArray().apply {
                    put(
                            JSONObject().apply {
                                put("type", "text")
                                put("text", lastMessage.content)
                            }
                    )
                    put(
                            JSONObject().apply {
                                put("type", "image_url")
                                put(
                                        "image_url",
                                        JSONObject().apply {
                                            put("url", "data:image/jpeg;base64,$base64Image")
                                            put("detail", "low")
                                        }
                                )
                            }
                    )
                }

        val messagesArray =
                JSONArray().apply {
                    messagesWithImage.forEach { msg ->
                        put(
                                JSONObject().apply {
                                    put("role", msg.role)
                                    put("content", msg.content)
                                }
                        )
                    }
                    put(
                            JSONObject().apply {
                                put("role", "user")
                                put("content", contentArray)
                            }
                    )
                }

        val requestBody =
                JSONObject().apply {
                    put("model", "gpt-4-vision-preview")
                    put("messages", messagesArray)
                    put("max_tokens", 2048)
                }

        val request =
                Request.Builder()
                        .url(OPENAI_API_URL)
                        .addHeader("Authorization", "Bearer ${BuildConfig.OPENAI_API_KEY}")
                        .addHeader("Content-Type", "application/json")
                        .post(
                                requestBody
                                        .toString()
                                        .toRequestBody("application/json".toMediaType())
                        )
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
        val convMessages = messages.filter { it.role != "system" }

        val messagesArray =
                JSONArray().apply {
                    convMessages.forEach { msg ->
                        put(
                                JSONObject().apply {
                                    put(
                                            "role",
                                            if (msg.role == "assistant") "assistant" else "user"
                                    )
                                    put("content", msg.content)
                                }
                        )
                    }
                }

        val requestBody =
                JSONObject().apply {
                    put("model", "claude-3-opus-20240229")
                    put("max_tokens", 2048)
                    put("system", systemMsg)
                    put("messages", messagesArray)
                }

        val request =
                Request.Builder()
                        .url(ANTHROPIC_API_URL)
                        .addHeader("x-api-key", BuildConfig.ANTHROPIC_API_KEY)
                        .addHeader("anthropic-version", "2023-06-01")
                        .addHeader("Content-Type", "application/json")
                        .post(
                                requestBody
                                        .toString()
                                        .toRequestBody("application/json".toMediaType())
                        )
                        .build()

        val response = httpClient.newCall(request).execute()
        val responseBody = response.body?.string() ?: throw Exception("Empty response")

        if (!response.isSuccessful) {
            throw Exception("API error: ${response.code} - $responseBody")
        }

        val json = JSONObject(responseBody)
        return json.getJSONArray("content").getJSONObject(0).getString("text")
    }

    private fun processLocally(input: String, screenContent: ScreenContent?): String {
        val lowerInput = input.lowercase()

        val actions = mutableListOf<Map<String, Any>>()
        var thought = "Processing locally without AI"
        var responseText = ""

        when {
            "brightness" in lowerInput && "up" in lowerInput -> {
                thought = "User wants to increase brightness"
                actions.add(mapOf("type" to "brightness", "params" to mapOf("value" to 200)))
                responseText = "Increasing brightness"
            }
            "brightness" in lowerInput && "down" in lowerInput -> {
                thought = "User wants to decrease brightness"
                actions.add(mapOf("type" to "brightness", "params" to mapOf("value" to 50)))
                responseText = "Decreasing brightness"
            }
            "volume" in lowerInput && "up" in lowerInput -> {
                thought = "User wants to increase volume"
                actions.add(mapOf("type" to "volume_media", "params" to mapOf("value" to 80)))
                responseText = "Increasing volume"
            }
            "volume" in lowerInput && "down" in lowerInput -> {
                thought = "User wants to decrease volume"
                actions.add(mapOf("type" to "volume_media", "params" to mapOf("value" to 30)))
                responseText = "Decreasing volume"
            }
            "silent" in lowerInput || "mute" in lowerInput -> {
                thought = "User wants silent mode"
                actions.add(mapOf("type" to "ringer_mode", "params" to mapOf("mode" to "silent")))
                responseText = "Setting phone to silent"
            }
            "flashlight" in lowerInput && "on" in lowerInput -> {
                thought = "User wants to turn on flashlight"
                actions.add(mapOf("type" to "flashlight", "params" to mapOf("enabled" to true)))
                responseText = "Turning on flashlight"
            }
            "flashlight" in lowerInput && "off" in lowerInput -> {
                thought = "User wants to turn off flashlight"
                actions.add(mapOf("type" to "flashlight", "params" to mapOf("enabled" to false)))
                responseText = "Turning off flashlight"
            }
            "open" in lowerInput -> {
                val appName = input.replace("open", "", ignoreCase = true).trim()
                thought = "User wants to open $appName"
                actions.add(mapOf("type" to "open_app", "params" to mapOf("name" to appName)))
                responseText = "Opening $appName"
            }
            "go back" in lowerInput || "back" in lowerInput -> {
                thought = "User wants to go back"
                actions.add(mapOf("type" to "back", "params" to emptyMap<String, Any>()))
                responseText = "Going back"
            }
            "home" in lowerInput -> {
                thought = "User wants to go home"
                actions.add(mapOf("type" to "home", "params" to emptyMap<String, Any>()))
                responseText = "Going to home screen"
            }
            "scroll" in lowerInput && "down" in lowerInput -> {
                thought = "User wants to scroll down"
                actions.add(mapOf("type" to "scroll", "params" to mapOf("direction" to "down")))
                responseText = "Scrolling down"
            }
            "scroll" in lowerInput && "up" in lowerInput -> {
                thought = "User wants to scroll up"
                actions.add(mapOf("type" to "scroll", "params" to mapOf("direction" to "up")))
                responseText = "Scrolling up"
            }
            "click" in lowerInput || "tap" in lowerInput -> {
                // Try to find the element to click
                val words = input.split(" ")
                val targetText = words.drop(1).joinToString(" ")
                thought = "User wants to click on '$targetText'"
                actions.add(mapOf("type" to "tap_element", "params" to mapOf("text" to targetText)))
                responseText = "Tapping on '$targetText'"
            }
            else -> {
                thought = "Command not recognized in local mode"
                responseText =
                        "I'm running in local mode. For full AI capabilities, please configure an API key. Try commands like 'open Chrome', 'brightness up', 'scroll down', etc."
            }
        }

        val actionsJson =
                JSONArray().apply {
                    actions.forEach { action ->
                        put(
                                JSONObject().apply {
                                    put("type", action["type"])
                                    put("params", JSONObject(action["params"] as Map<*, *>))
                                }
                        )
                    }
                }

        return JSONObject()
                .apply {
                    put("thought", thought)
                    put("actions", actionsJson)
                    put("response", responseText)
                }
                .toString()
    }

    private fun parseAgentResponse(response: String): AgentResponse {
        return try {
            // Extract JSON from response (might be wrapped in markdown)
            val jsonPattern =
                    """\{[\s\S]*"thought"[\s\S]*"actions"[\s\S]*"response"[\s\S]*\}""".toRegex()
            val match = jsonPattern.find(response)

            val json =
                    if (match != null) {
                        JSONObject(match.value)
                    } else {
                        JSONObject(response)
                    }

            val thought = json.optString("thought", "")
            val responseText = json.optString("response", response)

            val actionsArray = json.optJSONArray("actions") ?: JSONArray()
            val actions = mutableListOf<AgentAction>()

            for (i in 0 until actionsArray.length()) {
                val actionJson = actionsArray.getJSONObject(i)
                val type = actionJson.getString("type")
                val params = mutableMapOf<String, Any>()

                val paramsJson = actionJson.optJSONObject("params")
                if (paramsJson != null) {
                    paramsJson.keys().forEach { key -> params[key] = paramsJson.get(key) }
                }

                actions.add(AgentAction(type, params))
            }

            AgentResponse(thought, actions, responseText)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse response", e)
            AgentResponse("", emptyList(), response)
        }
    }

    fun clearHistory() {
        conversationHistory.clear()
        conversationHistory.add(Message("system", systemPrompt))
    }
}

data class Message(val role: String, val content: String)

data class AgentAction(val type: String, val params: Map<String, Any>)

data class AgentResponse(val thought: String, val actions: List<AgentAction>, val response: String)

data class ActionResult(val actionType: String, val success: Boolean, val error: String?)
