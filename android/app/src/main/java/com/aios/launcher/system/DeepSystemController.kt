package com.aios.launcher.system

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext

/**
 * Deep System Controller for AI-OS. Provides complete system-level control for AI agent. This
 * enables true OS-level control similar to a system app.
 */
@Singleton
class DeepSystemController @Inject constructor(@ApplicationContext private val context: Context) {
    companion object {
        private const val TAG = "DeepSystemController"

        // Singleton reference for accessibility service
        private var accessibilityService: AccessibilityService? = null
        private var mediaProjection: MediaProjection? = null
        private var virtualDisplay: VirtualDisplay? = null
        private var imageReader: ImageReader? = null

        fun setAccessibilityService(service: AccessibilityService?) {
            accessibilityService = service
        }

        fun setMediaProjection(projection: MediaProjection?) {
            mediaProjection = projection
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager

    private val _screenContent = MutableStateFlow<ScreenContent?>(null)
    val screenContent: StateFlow<ScreenContent?> = _screenContent

    // ==================== Screen Analysis ====================

    /**
     * Capture current screen content (text and UI elements). This enables AI to "see" what's on
     * screen.
     */
    suspend fun captureScreenContent(): ScreenContent =
            withContext(Dispatchers.Main) {
                val service =
                        accessibilityService
                                ?: return@withContext ScreenContent(
                                        elements = emptyList(),
                                        packageName = "",
                                        activityName = ""
                                )

                val rootNode =
                        service.rootInActiveWindow
                                ?: return@withContext ScreenContent(
                                        elements = emptyList(),
                                        packageName = "",
                                        activityName = ""
                                )

                val elements = mutableListOf<UIElement>()
                extractElements(rootNode, elements)

                val content =
                        ScreenContent(
                                elements = elements,
                                packageName = rootNode.packageName?.toString() ?: "",
                                activityName = rootNode.className?.toString() ?: ""
                        )

                rootNode.recycle()
                _screenContent.value = content
                content
            }

    private fun extractElements(node: AccessibilityNodeInfo, elements: MutableList<UIElement>) {
        val bounds = android.graphics.Rect()
        node.getBoundsInScreen(bounds)

        elements.add(
                UIElement(
                        id = node.viewIdResourceName ?: "",
                        className = node.className?.toString() ?: "",
                        text = node.text?.toString() ?: "",
                        contentDescription = node.contentDescription?.toString() ?: "",
                        bounds = bounds,
                        isClickable = node.isClickable,
                        isEditable = node.isEditable,
                        isScrollable = node.isScrollable,
                        isCheckable = node.isCheckable,
                        isChecked = node.isChecked,
                        isEnabled = node.isEnabled,
                        isFocused = node.isFocused
                )
        )

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            extractElements(child, elements)
            child.recycle()
        }
    }

    /** Take a screenshot of the current screen. */
    suspend fun takeScreenshot(): Bitmap? =
            withContext(Dispatchers.IO) {
                val projection = mediaProjection ?: return@withContext null

                try {
                    val metrics = DisplayMetrics()
                    windowManager.defaultDisplay.getMetrics(metrics)

                    val width = metrics.widthPixels
                    val height = metrics.heightPixels
                    val density = metrics.densityDpi

                    imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)

                    virtualDisplay =
                            projection.createVirtualDisplay(
                                    "AI-OS-Screenshot",
                                    width,
                                    height,
                                    density,
                                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                                    imageReader!!.surface,
                                    null,
                                    null
                            )

                    delay(100) // Wait for capture

                    val image = imageReader!!.acquireLatestImage() ?: return@withContext null
                    val planes = image.planes
                    val buffer = planes[0].buffer
                    val pixelStride = planes[0].pixelStride
                    val rowStride = planes[0].rowStride
                    val rowPadding = rowStride - pixelStride * width

                    val bitmap =
                            Bitmap.createBitmap(
                                    width + rowPadding / pixelStride,
                                    height,
                                    Bitmap.Config.ARGB_8888
                            )
                    bitmap.copyPixelsFromBuffer(buffer)

                    image.close()
                    virtualDisplay?.release()
                    imageReader?.close()

                    Bitmap.createBitmap(bitmap, 0, 0, width, height)
                } catch (e: Exception) {
                    Log.e(TAG, "Screenshot failed", e)
                    null
                }
            }

    // ==================== Touch/Gesture Injection ====================

    /** Perform a tap at specific coordinates. */
    suspend fun tap(x: Float, y: Float): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false

                val path = Path().apply { moveTo(x, y) }

                val gesture =
                        GestureDescription.Builder()
                                .addStroke(GestureDescription.StrokeDescription(path, 0, 50))
                                .build()

                var result = false
                service.dispatchGesture(
                        gesture,
                        object : AccessibilityService.GestureResultCallback() {
                            override fun onCompleted(gestureDescription: GestureDescription?) {
                                result = true
                            }
                            override fun onCancelled(gestureDescription: GestureDescription?) {
                                result = false
                            }
                        },
                        handler
                )

                delay(100)
                result
            }

    /** Perform a long press at specific coordinates. */
    suspend fun longPress(x: Float, y: Float, duration: Long = 1000): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false

                val path = Path().apply { moveTo(x, y) }

                val gesture =
                        GestureDescription.Builder()
                                .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
                                .build()

                var result = false
                service.dispatchGesture(
                        gesture,
                        object : AccessibilityService.GestureResultCallback() {
                            override fun onCompleted(gestureDescription: GestureDescription?) {
                                result = true
                            }
                        },
                        handler
                )

                delay(duration + 100)
                result
            }

    /** Perform a swipe gesture. */
    suspend fun swipe(
            startX: Float,
            startY: Float,
            endX: Float,
            endY: Float,
            duration: Long = 300
    ): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false

                val path =
                        Path().apply {
                            moveTo(startX, startY)
                            lineTo(endX, endY)
                        }

                val gesture =
                        GestureDescription.Builder()
                                .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
                                .build()

                var result = false
                service.dispatchGesture(
                        gesture,
                        object : AccessibilityService.GestureResultCallback() {
                            override fun onCompleted(gestureDescription: GestureDescription?) {
                                result = true
                            }
                        },
                        handler
                )

                delay(duration + 100)
                result
            }

    /** Scroll in a direction. */
    suspend fun scroll(direction: ScrollDirection): Boolean {
        val metrics = DisplayMetrics()
        windowManager.defaultDisplay.getMetrics(metrics)

        val centerX = metrics.widthPixels / 2f
        val centerY = metrics.heightPixels / 2f
        val distance = metrics.heightPixels / 3f

        return when (direction) {
            ScrollDirection.UP -> swipe(centerX, centerY + distance, centerX, centerY - distance)
            ScrollDirection.DOWN -> swipe(centerX, centerY - distance, centerX, centerY + distance)
            ScrollDirection.LEFT -> swipe(centerX + distance, centerY, centerX - distance, centerY)
            ScrollDirection.RIGHT -> swipe(centerX - distance, centerY, centerX + distance, centerY)
        }
    }

    // ==================== UI Element Interaction ====================

    /** Click on an element by its text. */
    suspend fun clickByText(text: String): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false
                val rootNode = service.rootInActiveWindow ?: return@withContext false

                val nodes = rootNode.findAccessibilityNodeInfosByText(text)
                for (node in nodes) {
                    if (node.isClickable) {
                        val result = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        node.recycle()
                        rootNode.recycle()
                        return@withContext result
                    }

                    // Try clicking parent
                    var parent = node.parent
                    while (parent != null) {
                        if (parent.isClickable) {
                            val result = parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                            parent.recycle()
                            node.recycle()
                            rootNode.recycle()
                            return@withContext result
                        }
                        val oldParent = parent
                        parent = parent.parent
                        oldParent.recycle()
                    }
                    node.recycle()
                }

                rootNode.recycle()
                false
            }

    /** Click on an element by its ID. */
    suspend fun clickById(viewId: String): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false
                val rootNode = service.rootInActiveWindow ?: return@withContext false

                val nodes = rootNode.findAccessibilityNodeInfosByViewId(viewId)
                for (node in nodes) {
                    val result = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    node.recycle()
                    if (result) {
                        rootNode.recycle()
                        return@withContext true
                    }
                }

                rootNode.recycle()
                false
            }

    /** Type text into the currently focused field. */
    suspend fun typeText(text: String): Boolean =
            withContext(Dispatchers.Main) {
                val service = accessibilityService ?: return@withContext false
                val rootNode = service.rootInActiveWindow ?: return@withContext false

                val focusedNode = rootNode.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
                val result =
                        if (focusedNode != null && focusedNode.isEditable) {
                            val args =
                                    android.os.Bundle().apply {
                                        putCharSequence(
                                                AccessibilityNodeInfo
                                                        .ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                                                text
                                        )
                                    }
                            focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                        } else {
                            false
                        }

                focusedNode?.recycle()
                rootNode.recycle()
                result
            }

    /** Clear text in the currently focused field. */
    suspend fun clearText(): Boolean = withContext(Dispatchers.Main) { typeText("") }

    // ==================== System Navigation ====================

    /** Press the back button. */
    fun pressBack(): Boolean {
        return accessibilityService?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                ?: false
    }

    /** Press the home button. */
    fun pressHome(): Boolean {
        return accessibilityService?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
                ?: false
    }

    /** Open recent apps. */
    fun openRecents(): Boolean {
        return accessibilityService?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)
                ?: false
    }

    /** Open notifications panel. */
    fun openNotifications(): Boolean {
        return accessibilityService?.performGlobalAction(
                AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
        )
                ?: false
    }

    /** Open quick settings. */
    fun openQuickSettings(): Boolean {
        return accessibilityService?.performGlobalAction(
                AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS
        )
                ?: false
    }

    /** Lock the screen. */
    fun lockScreen(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            accessibilityService?.performGlobalAction(
                    AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN
            )
                    ?: false
        } else {
            false
        }
    }

    /** Take a system screenshot. */
    fun takeSystemScreenshot(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            accessibilityService?.performGlobalAction(
                    AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT
            )
                    ?: false
        } else {
            false
        }
    }

    /** Open power dialog. */
    fun openPowerDialog(): Boolean {
        return accessibilityService?.performGlobalAction(
                AccessibilityService.GLOBAL_ACTION_POWER_DIALOG
        )
                ?: false
    }

    /** Toggle split screen. */
    fun toggleSplitScreen(): Boolean {
        return accessibilityService?.performGlobalAction(
                AccessibilityService.GLOBAL_ACTION_TOGGLE_SPLIT_SCREEN
        )
                ?: false
    }
}

// Data classes
data class ScreenContent(
        val elements: List<UIElement>,
        val packageName: String,
        val activityName: String
)

data class UIElement(
        val id: String,
        val className: String,
        val text: String,
        val contentDescription: String,
        val bounds: android.graphics.Rect,
        val isClickable: Boolean,
        val isEditable: Boolean,
        val isScrollable: Boolean,
        val isCheckable: Boolean,
        val isChecked: Boolean,
        val isEnabled: Boolean,
        val isFocused: Boolean
)

enum class ScrollDirection {
    UP,
    DOWN,
    LEFT,
    RIGHT
}
