package com.aios.launcher.ui.home

import android.content.pm.PackageManager
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.aios.launcher.agent.AppInfo
import java.text.SimpleDateFormat
import java.util.*

/**
 * AI-OS Launcher Home Screen.
 * Displays apps, widgets, and AI assistant access.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onAgentTrigger: () -> Unit,
    onSettingsClick: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel()
) {
    val apps by viewModel.apps.collectAsState()
    val currentTime by viewModel.currentTime.collectAsState()
    val currentDate by viewModel.currentDate.collectAsState()
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        Color(0xFF1a1a2e),
                        Color(0xFF16213e),
                        Color(0xFF0f3460)
                    )
                )
            )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            // Status bar area
            Spacer(modifier = Modifier.height(24.dp))
            
            // Clock Widget
            ClockWidget(
                time = currentTime,
                date = currentDate,
                modifier = Modifier.fillMaxWidth()
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Quick Actions
            QuickActionsBar(
                onAgentTrigger = onAgentTrigger,
                onSettingsClick = onSettingsClick
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // App Grid
            AppGrid(
                apps = apps,
                onAppClick = { app -> viewModel.openApp(app) },
                modifier = Modifier.weight(1f)
            )
            
            // Bottom Dock
            BottomDock(
                onAgentTrigger = onAgentTrigger
            )
        }
    }
}

@Composable
fun ClockWidget(
    time: String,
    date: String,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = time,
            style = MaterialTheme.typography.displayLarge,
            color = Color.White,
            fontSize = 72.sp
        )
        
        Text(
            text = date,
            style = MaterialTheme.typography.titleMedium,
            color = Color.White.copy(alpha = 0.7f)
        )
    }
}

@Composable
fun QuickActionsBar(
    onAgentTrigger: () -> Unit,
    onSettingsClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.White.copy(alpha = 0.1f))
            .padding(12.dp),
        horizontalArrangement = Arrangement.SpaceEvenly
    ) {
        QuickActionButton(
            icon = Icons.Default.Wifi,
            label = "WiFi",
            onClick = { /* Toggle WiFi */ }
        )
        QuickActionButton(
            icon = Icons.Default.Bluetooth,
            label = "Bluetooth",
            onClick = { /* Toggle Bluetooth */ }
        )
        QuickActionButton(
            icon = Icons.Default.FlashlightOn,
            label = "Torch",
            onClick = { /* Toggle Flashlight */ }
        )
        QuickActionButton(
            icon = Icons.Default.Assistant,
            label = "AI",
            onClick = onAgentTrigger,
            highlight = true
        )
        QuickActionButton(
            icon = Icons.Default.Settings,
            label = "Settings",
            onClick = onSettingsClick
        )
    }
}

@Composable
fun QuickActionButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    onClick: () -> Unit,
    highlight: Boolean = false
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .padding(8.dp)
    ) {
        Box(
            modifier = Modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(
                    if (highlight) {
                        Brush.linearGradient(
                            colors = listOf(Color(0xFF667eea), Color(0xFF764ba2))
                        )
                    } else {
                        Brush.linearGradient(
                            colors = listOf(Color.White.copy(alpha = 0.2f), Color.White.copy(alpha = 0.1f))
                        )
                    }
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = Color.White,
                modifier = Modifier.size(24.dp)
            )
        }
        
        Spacer(modifier = Modifier.height(4.dp))
        
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White.copy(alpha = 0.7f)
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun AppGrid(
    apps: List<AppInfo>,
    onAppClick: (AppInfo) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(4),
        modifier = modifier,
        contentPadding = PaddingValues(8.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        items(apps) { app ->
            AppIcon(
                app = app,
                onClick = { onAppClick(app) }
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun AppIcon(
    app: AppInfo,
    onClick: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .combinedClickable(
                onClick = onClick,
                onLongClick = { /* Show app options */ }
            )
            .padding(4.dp)
    ) {
        // App icon
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(Color.White.copy(alpha = 0.1f)),
            contentAlignment = Alignment.Center
        ) {
            val bitmap = remember(app.icon) {
                app.icon.toBitmap().asImageBitmap()
            }
            
            androidx.compose.foundation.Image(
                bitmap = bitmap,
                contentDescription = app.name,
                modifier = Modifier.size(48.dp)
            )
        }
        
        Spacer(modifier = Modifier.height(4.dp))
        
        // App name
        Text(
            text = app.name,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
            modifier = Modifier.width(72.dp)
        )
    }
}

@Composable
fun BottomDock(
    onAgentTrigger: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.Black.copy(alpha = 0.3f))
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Phone
        DockIcon(
            icon = Icons.Default.Phone,
            label = "Phone",
            onClick = { /* Open Phone */ }
        )
        
        // Messages
        DockIcon(
            icon = Icons.Default.Message,
            label = "Messages",
            onClick = { /* Open Messages */ }
        )
        
        // AI Assistant (Center, larger)
        FloatingActionButton(
            onClick = onAgentTrigger,
            containerColor = Color(0xFF667eea),
            modifier = Modifier.size(64.dp)
        ) {
            Icon(
                imageVector = Icons.Default.Assistant,
                contentDescription = "AI Assistant",
                tint = Color.White,
                modifier = Modifier.size(32.dp)
            )
        }
        
        // Camera
        DockIcon(
            icon = Icons.Default.CameraAlt,
            label = "Camera",
            onClick = { /* Open Camera */ }
        )
        
        // Browser
        DockIcon(
            icon = Icons.Default.Language,
            label = "Browser",
            onClick = { /* Open Browser */ }
        )
    }
}

@Composable
fun DockIcon(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    onClick: () -> Unit
) {
    IconButton(onClick = onClick) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = Color.White,
            modifier = Modifier.size(28.dp)
        )
    }
}
