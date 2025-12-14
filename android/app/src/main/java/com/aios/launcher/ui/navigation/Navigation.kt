package com.aios.launcher.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.aios.launcher.ui.home.HomeScreen

/**
 * Navigation graph for AI-OS Launcher.
 */
@Composable
fun AIosNavHost(
    navController: NavHostController,
    onAgentTrigger: () -> Unit
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Home.route
    ) {
        composable(Screen.Home.route) {
            HomeScreen(
                onAgentTrigger = onAgentTrigger,
                onSettingsClick = { navController.navigate(Screen.Settings.route) }
            )
        }
        
        composable(Screen.Settings.route) {
            SettingsScreen(
                onBackClick = { navController.popBackStack() }
            )
        }
        
        composable(Screen.AppDrawer.route) {
            AppDrawerScreen(
                onAppClick = { /* Open app */ },
                onBackClick = { navController.popBackStack() }
            )
        }
    }
}

sealed class Screen(val route: String) {
    object Home : Screen("home")
    object Settings : Screen("settings")
    object AppDrawer : Screen("app_drawer")
    object Agent : Screen("agent")
}

@Composable
fun SettingsScreen(onBackClick: () -> Unit) {
    // Placeholder - implement full settings
    androidx.compose.material3.Text("Settings Screen")
}

@Composable
fun AppDrawerScreen(
    onAppClick: (String) -> Unit,
    onBackClick: () -> Unit
) {
    // Placeholder - implement full app drawer
    androidx.compose.material3.Text("App Drawer")
}
