package com.aios.launcher.ui.systemui

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.wifi.WifiManager
import android.os.BatteryManager
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.*
import kotlinx.coroutines.delay

/** Custom Status Bar for AI-OS. Shows time, battery, connectivity, and AI status. */
@Composable
fun AIosStatusBar(isAgentActive: Boolean = false, onAgentClick: () -> Unit = {}) {
    val context = LocalContext.current
    var currentTime by remember { mutableStateOf("") }
    var batteryLevel by remember { mutableStateOf(100) }
    var isCharging by remember { mutableStateOf(false) }
    var wifiConnected by remember { mutableStateOf(false) }
    var cellularConnected by remember { mutableStateOf(false) }

    // Update time
    LaunchedEffect(Unit) {
        while (true) {
            currentTime = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
            delay(1000)
        }
    }

    // Battery receiver
    DisposableEffect(context) {
        val batteryReceiver =
                object : BroadcastReceiver() {
                    override fun onReceive(context: Context, intent: Intent) {
                        batteryLevel = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, 100)
                        val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                        isCharging =
                                status == BatteryManager.BATTERY_STATUS_CHARGING ||
                                        status == BatteryManager.BATTERY_STATUS_FULL
                    }
                }
        context.registerReceiver(batteryReceiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))

        onDispose { context.unregisterReceiver(batteryReceiver) }
    }

    // Connectivity check
    LaunchedEffect(Unit) {
        while (true) {
            val connectivityManager =
                    context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val wifiManager =
                    context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager

            wifiConnected = wifiManager.isWifiEnabled && wifiManager.connectionInfo.networkId != -1

            val activeNetwork = connectivityManager.activeNetworkInfo
            cellularConnected =
                    activeNetwork?.type == ConnectivityManager.TYPE_MOBILE &&
                            activeNetwork.isConnected

            delay(5000)
        }
    }

    Box(
            modifier =
                    Modifier.fillMaxWidth().height(48.dp).background(Color.Black.copy(alpha = 0.3f))
    ) {
        Row(
                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
        ) {
            // Left side - Time
            Text(
                    text = currentTime,
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium
            )

            // Right side - Status icons
            Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
            ) {
                // AI Status
                AnimatedVisibility(
                        visible = isAgentActive,
                        enter = fadeIn() + scaleIn(),
                        exit = fadeOut() + scaleOut()
                ) {
                    Box(
                            modifier =
                                    Modifier.size(24.dp)
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
                                            .clickable(onClick = onAgentClick),
                            contentAlignment = Alignment.Center
                    ) {
                        Icon(
                                imageVector = Icons.Default.Assistant,
                                contentDescription = "AI Active",
                                tint = Color.White,
                                modifier = Modifier.size(14.dp)
                        )
                    }
                }

                // WiFi
                if (wifiConnected) {
                    Icon(
                            imageVector = Icons.Default.Wifi,
                            contentDescription = "WiFi",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp)
                    )
                } else if (cellularConnected) {
                    Icon(
                            imageVector = Icons.Default.SignalCellular4Bar,
                            contentDescription = "Cellular",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp)
                    )
                } else {
                    Icon(
                            imageVector = Icons.Default.SignalCellularOff,
                            contentDescription = "No Connection",
                            tint = Color.White.copy(alpha = 0.5f),
                            modifier = Modifier.size(18.dp)
                    )
                }

                // Battery
                Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(text = "$batteryLevel%", color = Color.White, fontSize = 12.sp)
                    Icon(
                            imageVector =
                                    when {
                                        isCharging -> Icons.Default.BatteryChargingFull
                                        batteryLevel > 80 -> Icons.Default.BatteryFull
                                        batteryLevel > 50 -> Icons.Default.Battery5Bar
                                        batteryLevel > 20 -> Icons.Default.Battery3Bar
                                        else -> Icons.Default.BatteryAlert
                                    },
                            contentDescription = "Battery",
                            tint =
                                    when {
                                        batteryLevel <= 20 && !isCharging -> Color.Red
                                        isCharging -> Color(0xFF4CAF50)
                                        else -> Color.White
                                    },
                            modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}

/** Quick Settings Panel for AI-OS. */
@Composable
fun QuickSettingsPanel(
        isExpanded: Boolean,
        onDismiss: () -> Unit,
        onWifiToggle: (Boolean) -> Unit = {},
        onBluetoothToggle: (Boolean) -> Unit = {},
        onFlashlightToggle: (Boolean) -> Unit = {},
        onAirplaneModeToggle: (Boolean) -> Unit = {},
        onDoNotDisturbToggle: (Boolean) -> Unit = {},
        onAutoRotateToggle: (Boolean) -> Unit = {}
) {
    var wifiEnabled by remember { mutableStateOf(false) }
    var bluetoothEnabled by remember { mutableStateOf(false) }
    var flashlightEnabled by remember { mutableStateOf(false) }
    var airplaneModeEnabled by remember { mutableStateOf(false) }
    var dndEnabled by remember { mutableStateOf(false) }
    var autoRotateEnabled by remember { mutableStateOf(false) }

    AnimatedVisibility(
            visible = isExpanded,
            enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(),
            exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut()
    ) {
        Surface(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                shape = RoundedCornerShape(24.dp),
                color = Color(0xFF1a1a2e).copy(alpha = 0.95f),
                tonalElevation = 8.dp
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                // Header
                Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                            text = "Quick Settings",
                            color = Color.White,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold
                    )

                    IconButton(onClick = onDismiss) {
                        Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Close",
                                tint = Color.White
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Quick toggles grid
                Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    QuickTile(
                            icon = Icons.Default.Wifi,
                            label = "WiFi",
                            enabled = wifiEnabled,
                            onClick = {
                                wifiEnabled = !wifiEnabled
                                onWifiToggle(wifiEnabled)
                            }
                    )

                    QuickTile(
                            icon = Icons.Default.Bluetooth,
                            label = "Bluetooth",
                            enabled = bluetoothEnabled,
                            onClick = {
                                bluetoothEnabled = !bluetoothEnabled
                                onBluetoothToggle(bluetoothEnabled)
                            }
                    )

                    QuickTile(
                            icon = Icons.Default.FlashlightOn,
                            label = "Flashlight",
                            enabled = flashlightEnabled,
                            onClick = {
                                flashlightEnabled = !flashlightEnabled
                                onFlashlightToggle(flashlightEnabled)
                            }
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    QuickTile(
                            icon = Icons.Default.AirplanemodeActive,
                            label = "Airplane",
                            enabled = airplaneModeEnabled,
                            onClick = {
                                airplaneModeEnabled = !airplaneModeEnabled
                                onAirplaneModeToggle(airplaneModeEnabled)
                            }
                    )

                    QuickTile(
                            icon = Icons.Default.DoNotDisturb,
                            label = "DND",
                            enabled = dndEnabled,
                            onClick = {
                                dndEnabled = !dndEnabled
                                onDoNotDisturbToggle(dndEnabled)
                            }
                    )

                    QuickTile(
                            icon = Icons.Default.ScreenRotation,
                            label = "Rotate",
                            enabled = autoRotateEnabled,
                            onClick = {
                                autoRotateEnabled = !autoRotateEnabled
                                onAutoRotateToggle(autoRotateEnabled)
                            }
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Brightness slider
                Column {
                    Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                                imageVector = Icons.Default.BrightnessLow,
                                contentDescription = null,
                                tint = Color.White
                        )

                        var brightness by remember { mutableStateOf(0.5f) }
                        Slider(
                                value = brightness,
                                onValueChange = { brightness = it },
                                modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                                colors =
                                        SliderDefaults.colors(
                                                thumbColor = Color(0xFF667eea),
                                                activeTrackColor = Color(0xFF667eea)
                                        )
                        )

                        Icon(
                                imageVector = Icons.Default.BrightnessHigh,
                                contentDescription = null,
                                tint = Color.White
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Volume slider
                Column {
                    Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                                imageVector = Icons.Default.VolumeDown,
                                contentDescription = null,
                                tint = Color.White
                        )

                        var volume by remember { mutableStateOf(0.5f) }
                        Slider(
                                value = volume,
                                onValueChange = { volume = it },
                                modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                                colors =
                                        SliderDefaults.colors(
                                                thumbColor = Color(0xFF667eea),
                                                activeTrackColor = Color(0xFF667eea)
                                        )
                        )

                        Icon(
                                imageVector = Icons.Default.VolumeUp,
                                contentDescription = null,
                                tint = Color.White
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun QuickTile(icon: ImageVector, label: String, enabled: Boolean, onClick: () -> Unit) {
    Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.clickable(onClick = onClick)
    ) {
        Box(
                modifier =
                        Modifier.size(56.dp)
                                .clip(CircleShape)
                                .background(
                                        if (enabled) {
                                            Brush.linearGradient(
                                                    colors =
                                                            listOf(
                                                                    Color(0xFF667eea),
                                                                    Color(0xFF764ba2)
                                                            )
                                            )
                                        } else {
                                            Brush.linearGradient(
                                                    colors =
                                                            listOf(
                                                                    Color.White.copy(0.1f),
                                                                    Color.White.copy(0.1f)
                                                            )
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

        Text(text = label, color = Color.White.copy(if (enabled) 1f else 0.6f), fontSize = 12.sp)
    }
}

/** Navigation Bar for AI-OS. */
@Composable
fun AIosNavigationBar(
        onBack: () -> Unit = {},
        onHome: () -> Unit = {},
        onRecents: () -> Unit = {},
        onAssistant: () -> Unit = {}
) {
    Box(
            modifier =
                    Modifier.fillMaxWidth().height(56.dp).background(Color.Black.copy(alpha = 0.3f))
    ) {
        Row(
                modifier = Modifier.fillMaxSize().padding(horizontal = 40.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
        ) {
            // Back
            IconButton(onClick = onBack) {
                Icon(
                        imageVector = Icons.Default.ArrowBack,
                        contentDescription = "Back",
                        tint = Color.White,
                        modifier = Modifier.size(24.dp)
                )
            }

            // Home
            IconButton(onClick = onHome) {
                Icon(
                        imageVector = Icons.Default.Circle,
                        contentDescription = "Home",
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                )
            }

            // Recents
            IconButton(onClick = onRecents) {
                Icon(
                        imageVector = Icons.Default.CropSquare,
                        contentDescription = "Recents",
                        tint = Color.White,
                        modifier = Modifier.size(24.dp)
                )
            }

            // AI Assistant
            IconButton(onClick = onAssistant) {
                Box(
                        modifier =
                                Modifier.size(32.dp)
                                        .clip(CircleShape)
                                        .background(
                                                Brush.linearGradient(
                                                        colors =
                                                                listOf(
                                                                        Color(0xFF667eea),
                                                                        Color(0xFF764ba2)
                                                                )
                                                )
                                        ),
                        contentAlignment = Alignment.Center
                ) {
                    Icon(
                            imageVector = Icons.Default.Assistant,
                            contentDescription = "AI Assistant",
                            tint = Color.White,
                            modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}
