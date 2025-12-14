package com.aios.launcher.system

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.graphics.drawable.Drawable
import android.net.Uri
import android.provider.Settings
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** App Manager for AI-OS. Provides comprehensive app management capabilities. */
@Singleton
class AppManager @Inject constructor(@ApplicationContext private val context: Context) {
    companion object {
        private const val TAG = "AppManager"
    }

    private val packageManager: PackageManager = context.packageManager

    // ==================== App Listing ====================

    /** Get all installed apps. */
    suspend fun getInstalledApps(includeSystem: Boolean = false): List<AppInfo> =
            withContext(Dispatchers.IO) {
                val apps = mutableListOf<AppInfo>()

                val packages = packageManager.getInstalledPackages(PackageManager.GET_META_DATA)

                for (packageInfo in packages) {
                    val isSystemApp =
                            (packageInfo.applicationInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0

                    if (!includeSystem && isSystemApp) {
                        continue
                    }

                    // Check if it has a launcher icon
                    val launchIntent =
                            packageManager.getLaunchIntentForPackage(packageInfo.packageName)
                    if (launchIntent == null && !includeSystem) {
                        continue
                    }

                    apps.add(extractAppInfo(packageInfo))
                }

                apps.sortedBy { it.name.lowercase() }
            }

    /** Get launchable apps only (with launcher icons). */
    suspend fun getLaunchableApps(): List<AppInfo> =
            withContext(Dispatchers.IO) {
                val apps = mutableListOf<AppInfo>()

                val intent =
                        Intent(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) }

                val resolveInfos = packageManager.queryIntentActivities(intent, 0)

                for (resolveInfo in resolveInfos) {
                    val packageName = resolveInfo.activityInfo.packageName

                    try {
                        val packageInfo =
                                packageManager.getPackageInfo(
                                        packageName,
                                        PackageManager.GET_META_DATA
                                )
                        apps.add(extractAppInfo(packageInfo))
                    } catch (e: Exception) {
                        Log.w(TAG, "Failed to get package info for $packageName", e)
                    }
                }

                apps.sortedBy { it.name.lowercase() }
            }

    /** Get recently used apps. */
    suspend fun getRecentApps(limit: Int = 10): List<AppInfo> =
            withContext(Dispatchers.IO) {
                // This would require UsageStatsManager permission
                // For now, return empty list as placeholder
                emptyList()
            }

    /** Search apps by name. */
    suspend fun searchApps(query: String): List<AppInfo> =
            withContext(Dispatchers.IO) {
                val queryLower = query.lowercase()
                getLaunchableApps().filter {
                    it.name.lowercase().contains(queryLower) ||
                            it.packageName.lowercase().contains(queryLower)
                }
            }

    // ==================== App Details ====================

    /** Get app info. */
    fun getAppInfo(packageName: String): AppInfo? {
        return try {
            val packageInfo =
                    packageManager.getPackageInfo(packageName, PackageManager.GET_META_DATA)
            extractAppInfo(packageInfo)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to get app info for $packageName", e)
            null
        }
    }

    /** Get app icon. */
    fun getAppIcon(packageName: String): Drawable? {
        return try {
            packageManager.getApplicationIcon(packageName)
        } catch (e: Exception) {
            null
        }
    }

    /** Check if app is installed. */
    fun isAppInstalled(packageName: String): Boolean {
        return try {
            packageManager.getPackageInfo(packageName, 0)
            true
        } catch (e: PackageManager.NameNotFoundException) {
            false
        }
    }

    /** Get app version. */
    fun getAppVersion(packageName: String): String? {
        return try {
            val packageInfo = packageManager.getPackageInfo(packageName, 0)
            packageInfo.versionName
        } catch (e: Exception) {
            null
        }
    }

    // ==================== App Launch ====================

    /** Launch app by package name. */
    fun launchApp(packageName: String): Boolean {
        return try {
            val intent = packageManager.getLaunchIntentForPackage(packageName)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                true
            } else {
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch app: $packageName", e)
            false
        }
    }

    /** Launch app by name (searches and launches). */
    suspend fun launchAppByName(name: String): Boolean =
            withContext(Dispatchers.Main) {
                val apps = searchApps(name)
                if (apps.isNotEmpty()) {
                    launchApp(apps.first().packageName)
                } else {
                    false
                }
            }

    /** Launch app component. */
    fun launchComponent(packageName: String, className: String): Boolean {
        return try {
            val intent =
                    Intent().apply {
                        setClassName(packageName, className)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch component", e)
            false
        }
    }

    // ==================== App Settings ====================

    /** Open app settings page. */
    fun openAppSettings(packageName: String): Boolean {
        return try {
            val intent =
                    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.parse("package:$packageName")
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open app settings", e)
            false
        }
    }

    /** Open Play Store page for app. */
    fun openPlayStore(packageName: String): Boolean {
        return try {
            val intent =
                    Intent(Intent.ACTION_VIEW).apply {
                        data = Uri.parse("market://details?id=$packageName")
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            // Try web fallback
            try {
                val webIntent =
                        Intent(Intent.ACTION_VIEW).apply {
                            data =
                                    Uri.parse(
                                            "https://play.google.com/store/apps/details?id=$packageName"
                                    )
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                context.startActivity(webIntent)
                true
            } catch (e2: Exception) {
                Log.e(TAG, "Failed to open Play Store", e2)
                false
            }
        }
    }

    // ==================== App Control ====================

    /** Force stop app (requires device owner or root). */
    fun forceStopApp(packageName: String): Boolean {
        // This requires system-level permissions
        // Open app settings as fallback
        return openAppSettings(packageName)
    }

    /** Clear app data (requires device owner or root). */
    fun clearAppData(packageName: String): Boolean {
        // This requires system-level permissions
        return openAppSettings(packageName)
    }

    /** Uninstall app. */
    fun uninstallApp(packageName: String): Boolean {
        return try {
            val intent =
                    Intent(Intent.ACTION_DELETE).apply {
                        data = Uri.parse("package:$packageName")
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to uninstall app", e)
            false
        }
    }

    // ==================== Default Apps ====================

    /** Get default browser. */
    fun getDefaultBrowser(): AppInfo? {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("http://example.com"))
        val resolveInfo = packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
        return resolveInfo?.activityInfo?.packageName?.let { getAppInfo(it) }
    }

    /** Get default SMS app. */
    fun getDefaultSmsApp(): AppInfo? {
        val packageName = android.provider.Telephony.Sms.getDefaultSmsPackage(context)
        return packageName?.let { getAppInfo(it) }
    }

    /** Get default phone app. */
    fun getDefaultPhoneApp(): AppInfo? {
        val intent = Intent(Intent.ACTION_DIAL)
        val resolveInfo = packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
        return resolveInfo?.activityInfo?.packageName?.let { getAppInfo(it) }
    }

    // ==================== Helpers ====================

    private fun extractAppInfo(packageInfo: PackageInfo): AppInfo {
        val appInfo = packageInfo.applicationInfo
        val isSystemApp = (appInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0

        return AppInfo(
                packageName = packageInfo.packageName,
                name = packageManager.getApplicationLabel(appInfo).toString(),
                versionName = packageInfo.versionName ?: "",
                versionCode =
                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                            packageInfo.longVersionCode
                        } else {
                            @Suppress("DEPRECATION") packageInfo.versionCode.toLong()
                        },
                isSystemApp = isSystemApp,
                isEnabled = appInfo.enabled,
                installedTime = packageInfo.firstInstallTime,
                updatedTime = packageInfo.lastUpdateTime,
                targetSdkVersion = appInfo.targetSdkVersion,
                minSdkVersion =
                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                            appInfo.minSdkVersion
                        } else {
                            0
                        }
        )
    }
}

data class AppInfo(
        val packageName: String,
        val name: String,
        val versionName: String,
        val versionCode: Long,
        val isSystemApp: Boolean,
        val isEnabled: Boolean,
        val installedTime: Long,
        val updatedTime: Long,
        val targetSdkVersion: Int,
        val minSdkVersion: Int
)
