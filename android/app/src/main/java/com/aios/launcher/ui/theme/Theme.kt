package com.aios.launcher.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// AI-OS Color Palette
private val AIosPrimary = Color(0xFF667eea)
private val AIosSecondary = Color(0xFF764ba2)
private val AIosBackground = Color(0xFF1a1a2e)
private val AIosSurface = Color(0xFF16213e)
private val AIosOnPrimary = Color.White
private val AIosOnBackground = Color.White
private val AIosOnSurface = Color.White

private val DarkColorScheme =
        darkColorScheme(
                primary = AIosPrimary,
                secondary = AIosSecondary,
                tertiary = Color(0xFF0f3460),
                background = AIosBackground,
                surface = AIosSurface,
                onPrimary = AIosOnPrimary,
                onBackground = AIosOnBackground,
                onSurface = AIosOnSurface,
                surfaceVariant = Color(0xFF2a2a4a),
                onSurfaceVariant = Color.White.copy(alpha = 0.7f)
        )

private val LightColorScheme =
        lightColorScheme(
                primary = AIosPrimary,
                secondary = AIosSecondary,
                tertiary = Color(0xFF0f3460),
                background = Color(0xFFF5F5F5),
                surface = Color.White,
                onPrimary = Color.White,
                onBackground = Color.Black,
                onSurface = Color.Black,
                surfaceVariant = Color(0xFFE0E0E0),
                onSurfaceVariant = Color.Black.copy(alpha = 0.7f)
        )

@Composable
fun AIosTheme(
        darkTheme: Boolean = isSystemInDarkTheme(),
        dynamicColor: Boolean = true,
        content: @Composable () -> Unit
) {
    val colorScheme =
            when {
                dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
                    val context = LocalContext.current
                    if (darkTheme) dynamicDarkColorScheme(context)
                    else dynamicLightColorScheme(context)
                }
                darkTheme -> DarkColorScheme
                else -> LightColorScheme
            }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = Color.Transparent.toArgb()
            window.navigationBarColor = Color.Transparent.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(colorScheme = colorScheme, typography = Typography, content = content)
}

// Typography
val Typography =
        Typography(
                displayLarge =
                        androidx.compose.ui.text.TextStyle(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Light,
                                fontSize =
                                        androidx.compose.ui.unit.TextUnit(
                                                72f,
                                                androidx.compose.ui.unit.TextUnitType.Sp
                                        )
                        ),
                headlineLarge =
                        androidx.compose.ui.text.TextStyle(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                                fontSize =
                                        androidx.compose.ui.unit.TextUnit(
                                                32f,
                                                androidx.compose.ui.unit.TextUnitType.Sp
                                        )
                        ),
                headlineMedium =
                        androidx.compose.ui.text.TextStyle(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
                                fontSize =
                                        androidx.compose.ui.unit.TextUnit(
                                                24f,
                                                androidx.compose.ui.unit.TextUnitType.Sp
                                        )
                        ),
                titleMedium =
                        androidx.compose.ui.text.TextStyle(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Medium,
                                fontSize =
                                        androidx.compose.ui.unit.TextUnit(
                                                16f,
                                                androidx.compose.ui.unit.TextUnitType.Sp
                                        )
                        ),
                labelSmall =
                        androidx.compose.ui.text.TextStyle(
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Normal,
                                fontSize =
                                        androidx.compose.ui.unit.TextUnit(
                                                11f,
                                                androidx.compose.ui.unit.TextUnitType.Sp
                                        )
                        )
        )
