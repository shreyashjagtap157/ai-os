package com.aios.launcher.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.aios.launcher.ui.navigation.AIosNavHost
import com.aios.launcher.ui.theme.AIosTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Main Activity serving as the Android Launcher.
 * This is the entry point for AI-OS on Android.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setContent {
            AIosTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AIosLauncher()
                }
            }
        }
    }
    
    // Override back button to prevent leaving the launcher
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        // Do nothing - we're the home screen
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AIosLauncher() {
    val navController = rememberNavController()
    var showAgentSheet by remember { mutableStateOf(false) }
    
    Scaffold(
        modifier = Modifier.fillMaxSize()
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Main navigation host
            AIosNavHost(
                navController = navController,
                onAgentTrigger = { showAgentSheet = true }
            )
        }
    }
    
    // Agent bottom sheet
    if (showAgentSheet) {
        AgentBottomSheet(
            onDismiss = { showAgentSheet = false }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentBottomSheet(onDismiss: () -> Unit) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        modifier = Modifier.fillMaxHeight(0.9f)
    ) {
        AgentInterface(
            onClose = onDismiss
        )
    }
}

@Composable
fun AgentInterface(
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    var userInput by remember { mutableStateOf("") }
    var isListening by remember { mutableStateOf(false) }
    var conversation by remember { mutableStateOf(listOf<ChatMessage>()) }
    
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "AI-OS Agent",
                style = MaterialTheme.typography.headlineMedium
            )
            IconButton(onClick = onClose) {
                Icon(
                    imageVector = androidx.compose.material.icons.Icons.Default.Close,
                    contentDescription = "Close"
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Conversation list
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            reverseLayout = true
        ) {
            items(conversation.reversed()) { message ->
                ChatBubble(message = message)
                Spacer(modifier = Modifier.height(8.dp))
            }
        }
        
        // Input area
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = userInput,
                onValueChange = { userInput = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask AI-OS anything...") },
                singleLine = true
            )
            
            // Voice button
            IconButton(
                onClick = { isListening = !isListening }
            ) {
                Icon(
                    imageVector = if (isListening) 
                        androidx.compose.material.icons.Icons.Default.MicOff 
                    else 
                        androidx.compose.material.icons.Icons.Default.Mic,
                    contentDescription = if (isListening) "Stop" else "Voice"
                )
            }
            
            // Send button
            IconButton(
                onClick = {
                    if (userInput.isNotBlank()) {
                        conversation = conversation + ChatMessage(
                            content = userInput,
                            isFromUser = true
                        )
                        // TODO: Send to AI service
                        userInput = ""
                    }
                }
            ) {
                Icon(
                    imageVector = androidx.compose.material.icons.Icons.Default.Send,
                    contentDescription = "Send"
                )
            }
        }
    }
}

@Composable
fun ChatBubble(message: ChatMessage) {
    val bubbleColor = if (message.isFromUser) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.surfaceVariant
    }
    
    val textColor = if (message.isFromUser) {
        MaterialTheme.colorScheme.onPrimary
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }
    
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (message.isFromUser) Arrangement.End else Arrangement.Start
    ) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = bubbleColor,
            modifier = Modifier.widthIn(max = 280.dp)
        ) {
            Text(
                text = message.content,
                modifier = Modifier.padding(12.dp),
                color = textColor
            )
        }
    }
}

data class ChatMessage(
    val content: String,
    val isFromUser: Boolean,
    val timestamp: Long = System.currentTimeMillis()
)

// Import for LazyColumn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.ui.unit.dp
