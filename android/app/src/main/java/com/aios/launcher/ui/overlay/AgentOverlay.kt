package com.aios.launcher.ui.overlay

import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.StateFlow

/** Always-visible AI Agent Overlay. Provides quick access to AI assistant from any app. */
@Singleton
class AgentOverlay @Inject constructor(@ApplicationContext private val context: Context) :
        LifecycleOwner, SavedStateRegistryOwner {

    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var overlayView: View? = null
    private var fabView: View? = null
    private var isExpanded = false

    private val lifecycleRegistry = LifecycleRegistry(this)
    private val savedStateRegistryController = SavedStateRegistryController.create(this)

    override val lifecycle: Lifecycle
        get() = lifecycleRegistry
    override val savedStateRegistry: SavedStateRegistry
        get() = savedStateRegistryController.savedStateRegistry

    // Callbacks
    var onVoiceCommand: ((String) -> Unit)? = null
    var onTextCommand: ((String) -> Unit)? = null
    var agentState: StateFlow<AgentOverlayState>? = null

    init {
        savedStateRegistryController.performRestore(null)
        lifecycleRegistry.currentState = Lifecycle.State.CREATED
    }

    /** Show the floating AI button. */
    fun showFloatingButton() {
        if (fabView != null) return

        lifecycleRegistry.currentState = Lifecycle.State.STARTED
        lifecycleRegistry.currentState = Lifecycle.State.RESUMED

        val params =
                WindowManager.LayoutParams(
                                WindowManager.LayoutParams.WRAP_CONTENT,
                                WindowManager.LayoutParams.WRAP_CONTENT,
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                                        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                                else WindowManager.LayoutParams.TYPE_PHONE,
                                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                                        WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                                PixelFormat.TRANSLUCENT
                        )
                        .apply {
                            gravity = Gravity.END or Gravity.CENTER_VERTICAL
                            x = 0
                            y = 0
                        }

        fabView =
                ComposeView(context).apply {
                    setViewTreeLifecycleOwner(this@AgentOverlay)
                    setViewTreeSavedStateRegistryOwner(this@AgentOverlay)

                    setContent { FloatingAgentButton(onClick = { toggleExpandedView() }) }
                }

        try {
            windowManager.addView(fabView, params)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    /** Hide the floating button. */
    fun hideFloatingButton() {
        fabView?.let {
            windowManager.removeView(it)
            fabView = null
        }
        hideExpandedView()
        lifecycleRegistry.currentState = Lifecycle.State.DESTROYED
    }

    /** Toggle the expanded assistant view. */
    private fun toggleExpandedView() {
        if (isExpanded) {
            hideExpandedView()
        } else {
            showExpandedView()
        }
    }

    private fun showExpandedView() {
        if (overlayView != null) return

        val params =
                WindowManager.LayoutParams(
                                WindowManager.LayoutParams.MATCH_PARENT,
                                (context.resources.displayMetrics.heightPixels * 0.6).toInt(),
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                                        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                                else WindowManager.LayoutParams.TYPE_PHONE,
                                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                                PixelFormat.TRANSLUCENT
                        )
                        .apply {
                            gravity = Gravity.BOTTOM
                            y = 0
                        }

        overlayView =
                ComposeView(context).apply {
                    setViewTreeLifecycleOwner(this@AgentOverlay)
                    setViewTreeSavedStateRegistryOwner(this@AgentOverlay)

                    setContent {
                        ExpandedAgentView(
                                onClose = { hideExpandedView() },
                                onSend = { text -> onTextCommand?.invoke(text) },
                                onVoice = { onVoiceCommand?.invoke("listen") }
                        )
                    }
                }

        try {
            windowManager.addView(overlayView, params)
            isExpanded = true
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun hideExpandedView() {
        overlayView?.let {
            windowManager.removeView(it)
            overlayView = null
        }
        isExpanded = false
    }
}

@Composable
fun FloatingAgentButton(onClick: () -> Unit) {
    Box(
            modifier =
                    Modifier.size(56.dp)
                            .padding(8.dp)
                            .clip(CircleShape)
                            .background(
                                    Brush.linearGradient(
                                            colors = listOf(Color(0xFF667eea), Color(0xFF764ba2))
                                    )
                            )
                            .clickable(onClick = onClick),
            contentAlignment = Alignment.Center
    ) {
        Icon(
                imageVector = Icons.Default.Assistant,
                contentDescription = "AI Assistant",
                tint = Color.White,
                modifier = Modifier.size(28.dp)
        )
    }
}

@Composable
fun ExpandedAgentView(onClose: () -> Unit, onSend: (String) -> Unit, onVoice: () -> Unit) {
    var inputText by remember { mutableStateOf("") }
    var messages by remember { mutableStateOf(listOf<ChatMessage>()) }

    Surface(
            modifier = Modifier.fillMaxSize(),
            color = Color(0xFF1a1a2e),
            shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                        text = "AI-OS Assistant",
                        style = MaterialTheme.typography.headlineSmall,
                        color = Color.White
                )

                IconButton(onClick = onClose) {
                    Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = Color.White
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Messages
            LazyColumn(modifier = Modifier.weight(1f).fillMaxWidth(), reverseLayout = true) {
                items(messages.reversed()) { message ->
                    ChatBubble(message)
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Input
            Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Ask anything...", color = Color.White.copy(0.5f)) },
                        colors =
                                OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = Color.White,
                                        unfocusedTextColor = Color.White,
                                        focusedBorderColor = Color(0xFF667eea),
                                        unfocusedBorderColor = Color.White.copy(0.3f)
                                ),
                        singleLine = true
                )

                Spacer(modifier = Modifier.width(8.dp))

                IconButton(
                        onClick = onVoice,
                        modifier =
                                Modifier.size(48.dp)
                                        .clip(CircleShape)
                                        .background(Color.White.copy(0.1f))
                ) {
                    Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = "Voice",
                            tint = Color.White
                    )
                }

                Spacer(modifier = Modifier.width(8.dp))

                IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                messages = messages + ChatMessage(inputText, true)
                                onSend(inputText)
                                inputText = ""
                            }
                        },
                        modifier =
                                Modifier.size(48.dp)
                                        .clip(CircleShape)
                                        .background(
                                                Brush.linearGradient(
                                                        colors =
                                                                listOf(
                                                                        Color(0xFF667eea),
                                                                        Color(0xFF764ba2)
                                                                )
                                                )
                                        )
                ) {
                    Icon(
                            imageVector = Icons.Default.Send,
                            contentDescription = "Send",
                            tint = Color.White
                    )
                }
            }
        }
    }
}

@Composable
fun ChatBubble(message: ChatMessage) {
    val bubbleColor =
            if (message.isFromUser) {
                Color(0xFF667eea)
            } else {
                Color.White.copy(0.1f)
            }

    Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = if (message.isFromUser) Arrangement.End else Arrangement.Start
    ) {
        Surface(
                color = bubbleColor,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.widthIn(max = 280.dp)
        ) { Text(text = message.content, modifier = Modifier.padding(12.dp), color = Color.White) }
    }
}

data class ChatMessage(val content: String, val isFromUser: Boolean)

sealed class AgentOverlayState {
    object Idle : AgentOverlayState()
    object Listening : AgentOverlayState()
    object Processing : AgentOverlayState()
    data class Responding(val text: String) : AgentOverlayState()
}
