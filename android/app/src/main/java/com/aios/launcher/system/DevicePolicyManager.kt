package com.aios.launcher.system

import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.UserHandle
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Device Policy Manager for AI-OS. Enables enterprise-level device control when activated as device
 * admin/owner.
 */
@Singleton
class AIosDevicePolicyManager
@Inject
constructor(@ApplicationContext private val context: Context) {
    companion object {
        private const val TAG = "AIosDevicePolicy"
    }

    private val devicePolicyManager: DevicePolicyManager =
            context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager

    private val adminComponent = ComponentName(context, AIosDeviceAdminReceiver::class.java)

    /** Check if AI-OS is device admin. */
    fun isDeviceAdmin(): Boolean {
        return devicePolicyManager.isAdminActive(adminComponent)
    }

    /** Check if AI-OS is device owner (highest privilege). */
    fun isDeviceOwner(): Boolean {
        return devicePolicyManager.isDeviceOwnerApp(context.packageName)
    }

    /** Request device admin activation. */
    fun requestDeviceAdmin(): Intent {
        return Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
            putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComponent)
            putExtra(
                    DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                    "AI-OS needs device admin access for full agent control capabilities."
            )
        }
    }

    // ==================== Screen Lock Control ====================

    /** Lock the screen immediately. */
    fun lockScreen(): Boolean {
        return if (isDeviceAdmin()) {
            try {
                devicePolicyManager.lockNow()
                true
            } catch (e: SecurityException) {
                Log.e(TAG, "Failed to lock screen", e)
                false
            }
        } else false
    }

    /** Set screen lock timeout. */
    fun setScreenLockTimeout(timeoutMs: Long): Boolean {
        return if (isDeviceAdmin()) {
            try {
                devicePolicyManager.setMaximumTimeToLock(adminComponent, timeoutMs)
                true
            } catch (e: Exception) {
                Log.e(TAG, "Failed to set lock timeout", e)
                false
            }
        } else false
    }

    // ==================== Camera Control ====================

    /** Disable camera. */
    fun setCameraDisabled(disabled: Boolean): Boolean {
        return if (isDeviceAdmin()) {
            try {
                devicePolicyManager.setCameraDisabled(adminComponent, disabled)
                true
            } catch (e: Exception) {
                Log.e(TAG, "Failed to set camera state", e)
                false
            }
        } else false
    }

    fun isCameraDisabled(): Boolean {
        return devicePolicyManager.getCameraDisabled(adminComponent)
    }

    // ==================== Encryption ====================

    /** Get encryption status. */
    fun getEncryptionStatus(): EncryptionStatus {
        return when (devicePolicyManager.storageEncryptionStatus) {
            DevicePolicyManager.ENCRYPTION_STATUS_UNSUPPORTED -> EncryptionStatus.UNSUPPORTED
            DevicePolicyManager.ENCRYPTION_STATUS_INACTIVE -> EncryptionStatus.INACTIVE
            DevicePolicyManager.ENCRYPTION_STATUS_ACTIVATING -> EncryptionStatus.ACTIVATING
            DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE -> EncryptionStatus.ACTIVE
            DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE_DEFAULT_KEY ->
                    EncryptionStatus.ACTIVE_DEFAULT_KEY
            DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE_PER_USER ->
                    EncryptionStatus.ACTIVE_PER_USER
            else -> EncryptionStatus.UNKNOWN
        }
    }

    // ==================== Password Policies (Device Owner) ====================

    /** Set password quality requirement. */
    fun setPasswordQuality(quality: PasswordQuality): Boolean {
        if (!isDeviceOwner()) return false

        try {
            val qualityValue =
                    when (quality) {
                        PasswordQuality.NONE -> DevicePolicyManager.PASSWORD_QUALITY_UNSPECIFIED
                        PasswordQuality.BIOMETRIC ->
                                DevicePolicyManager.PASSWORD_QUALITY_BIOMETRIC_WEAK
                        PasswordQuality.PATTERN -> DevicePolicyManager.PASSWORD_QUALITY_SOMETHING
                        PasswordQuality.PIN -> DevicePolicyManager.PASSWORD_QUALITY_NUMERIC
                        PasswordQuality.PIN_COMPLEX ->
                                DevicePolicyManager.PASSWORD_QUALITY_NUMERIC_COMPLEX
                        PasswordQuality.PASSWORD -> DevicePolicyManager.PASSWORD_QUALITY_ALPHABETIC
                        PasswordQuality.PASSWORD_COMPLEX ->
                                DevicePolicyManager.PASSWORD_QUALITY_COMPLEX
                    }
            devicePolicyManager.setPasswordQuality(adminComponent, qualityValue)
            return true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to set password quality", e)
            return false
        }
    }

    // ==================== Wipe Device (Device Owner) ====================

    /** Factory reset the device. USE WITH EXTREME CAUTION! */
    fun wipeDevice(reason: String = "AI-OS initiated wipe"): Boolean {
        if (!isDeviceOwner()) return false

        try {
            devicePolicyManager.wipeData(DevicePolicyManager.WIPE_EXTERNAL_STORAGE, reason)
            return true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to wipe device", e)
            return false
        }
    }

    // ==================== Reboot (Device Owner) ====================

    /** Reboot the device. */
    fun rebootDevice(): Boolean {
        if (!isDeviceOwner()) return false

        return try {
            devicePolicyManager.reboot(adminComponent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to reboot", e)
            false
        }
    }

    // ==================== App Management (Device Owner) ====================

    /** Set an app as hidden. */
    fun setAppHidden(packageName: String, hidden: Boolean): Boolean {
        if (!isDeviceOwner()) return false

        return try {
            devicePolicyManager.setApplicationHidden(adminComponent, packageName, hidden)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to hide app", e)
            false
        }
    }

    /** Check if an app is hidden. */
    fun isAppHidden(packageName: String): Boolean {
        return if (isDeviceOwner()) {
            devicePolicyManager.isApplicationHidden(adminComponent, packageName)
        } else false
    }

    /** Enable system app. */
    fun enableSystemApp(packageName: String): Boolean {
        if (!isDeviceOwner()) return false

        return try {
            devicePolicyManager.enableSystemApp(adminComponent, packageName)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to enable system app", e)
            false
        }
    }

    // ==================== Network Control (Device Owner) ====================

    /** Set WiFi configuration locked. */
    fun setWifiConfigLocked(locked: Boolean): Boolean {
        // Requires device owner and API level checks
        return false // Placeholder
    }

    // ==================== Kiosk Mode (Device Owner) ====================

    /** Start kiosk/lock task mode. */
    fun startKioskMode(packages: Array<String>): Boolean {
        if (!isDeviceOwner()) return false

        return try {
            devicePolicyManager.setLockTaskPackages(adminComponent, packages)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start kiosk mode", e)
            false
        }
    }

    /** Get kiosk mode packages. */
    fun getKioskPackages(): Array<String> {
        return if (isDeviceOwner()) {
            devicePolicyManager.getLockTaskPackages(adminComponent)
        } else emptyArray()
    }
}

/** Device Admin Receiver for AI-OS. */
class AIosDeviceAdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i("AIosAdmin", "Device admin enabled")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.i("AIosAdmin", "Device admin disabled")
    }

    override fun onPasswordChanged(context: Context, intent: Intent, userHandle: UserHandle) {
        super.onPasswordChanged(context, intent, userHandle)
        Log.i("AIosAdmin", "Password changed")
    }

    override fun onPasswordFailed(context: Context, intent: Intent, userHandle: UserHandle) {
        super.onPasswordFailed(context, intent, userHandle)
        Log.i("AIosAdmin", "Password failed")
    }
}

enum class EncryptionStatus {
    UNSUPPORTED,
    INACTIVE,
    ACTIVATING,
    ACTIVE,
    ACTIVE_DEFAULT_KEY,
    ACTIVE_PER_USER,
    UNKNOWN
}

enum class PasswordQuality {
    NONE,
    BIOMETRIC,
    PATTERN,
    PIN,
    PIN_COMPLEX,
    PASSWORD,
    PASSWORD_COMPLEX
}
