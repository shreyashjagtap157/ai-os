package com.aios.launcher.services

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Accessibility Service for AI-OS Agent Control. Enables AI to interact with UI elements across the
 * system.
 */
@AndroidEntryPoint
class AgentAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "AgentAccessibility"

        private var instance: AgentAccessibilityService? = null

        private val _isEnabled = MutableStateFlow(false)
        val isEnabled: StateFlow<Boolean> = _isEnabled

        fun getInstance(): AgentAccessibilityService? = instance

        /** Click on a UI element by text. */
        fun clickByText(text: String): Boolean {
            return instance?.findAndClick(text) ?: false
        }

        /** Type text into current focused element. */
        fun typeText(text: String): Boolean {
            return instance?.inputText(text) ?: false
        }

        /** Scroll in a direction. */
        fun scroll(direction: ScrollDirection): Boolean {
            return instance?.performScroll(direction) ?: false
        }

        /** Get current screen content. */
        fun getScreenContent(): List<String> {
            return instance?.extractAllText() ?: emptyList()
        }

        /** Navigate back. */
        fun navigateBack(): Boolean {
            return instance?.performGlobalAction(GLOBAL_ACTION_BACK) ?: false
        }

        /** Navigate home. */
        fun navigateHome(): Boolean {
            return instance?.performGlobalAction(GLOBAL_ACTION_HOME) ?: false
        }

        /** Open recent apps. */
        fun openRecents(): Boolean {
            return instance?.performGlobalAction(GLOBAL_ACTION_RECENTS) ?: false
        }

        /** Open notifications. */
        fun openNotifications(): Boolean {
            return instance?.performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS) ?: false
        }

        /** Open quick settings. */
        fun openQuickSettings(): Boolean {
            return instance?.performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS) ?: false
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        _isEnabled.value = true

        val info =
                AccessibilityServiceInfo().apply {
                    eventTypes = AccessibilityEvent.TYPES_ALL_MASK
                    feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
                    flags =
                            AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                                    AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
                                    AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
                    notificationTimeout = 100
                }
        serviceInfo = info

        Log.d(TAG, "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return

        // Log events for debugging
        when (event.eventType) {
            AccessibilityEvent.TYPE_VIEW_CLICKED -> {
                Log.v(TAG, "Click: ${event.text}")
            }
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> {
                Log.v(TAG, "Window changed: ${event.packageName}")
            }
            AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED -> {
                Log.v(TAG, "Notification: ${event.text}")
                // Could trigger agent notification handling
            }
        }
    }

    override fun onInterrupt() {
        Log.d(TAG, "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        _isEnabled.value = false
        Log.d(TAG, "Accessibility service destroyed")
    }

    /** Find and click on an element by text. */
    private fun findAndClick(text: String): Boolean {
        val rootNode = rootInActiveWindow ?: return false

        val nodes = rootNode.findAccessibilityNodeInfosByText(text)
        for (node in nodes) {
            if (node.isClickable) {
                val result = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                node.recycle()
                if (result) return true
            } else {
                // Try clicking parent
                var parent = node.parent
                while (parent != null) {
                    if (parent.isClickable) {
                        val result = parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                        parent.recycle()
                        node.recycle()
                        if (result) return true
                    }
                    val oldParent = parent
                    parent = parent.parent
                    oldParent.recycle()
                }
            }
            node.recycle()
        }

        rootNode.recycle()
        return false
    }

    /** Input text into focused field. */
    private fun inputText(text: String): Boolean {
        val rootNode = rootInActiveWindow ?: return false

        val focusedNode = rootNode.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        val result =
                if (focusedNode != null) {
                    val args =
                            Bundle().apply {
                                putCharSequence(
                                        AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                                        text
                                )
                            }
                    focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                } else {
                    false
                }

        focusedNode?.recycle()
        rootNode.recycle()
        return result
    }

    /** Perform scroll action. */
    private fun performScroll(direction: ScrollDirection): Boolean {
        val rootNode = rootInActiveWindow ?: return false

        val scrollableNodes = findScrollableNodes(rootNode)
        val result =
                scrollableNodes.firstOrNull()?.let { node ->
                    val action =
                            when (direction) {
                                ScrollDirection.UP, ScrollDirection.LEFT ->
                                        AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
                                ScrollDirection.DOWN, ScrollDirection.RIGHT ->
                                        AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                            }
                    node.performAction(action)
                }
                        ?: false

        scrollableNodes.forEach { it.recycle() }
        rootNode.recycle()
        return result
    }

    private fun findScrollableNodes(node: AccessibilityNodeInfo): List<AccessibilityNodeInfo> {
        val scrollable = mutableListOf<AccessibilityNodeInfo>()

        if (node.isScrollable) {
            scrollable.add(node)
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            scrollable.addAll(findScrollableNodes(child))
        }

        return scrollable
    }

    /** Extract all visible text from screen. */
    private fun extractAllText(): List<String> {
        val rootNode = rootInActiveWindow ?: return emptyList()
        val texts = mutableListOf<String>()

        extractTextRecursive(rootNode, texts)
        rootNode.recycle()

        return texts.filter { it.isNotBlank() }
    }

    private fun extractTextRecursive(node: AccessibilityNodeInfo, texts: MutableList<String>) {
        node.text?.let { texts.add(it.toString()) }
        node.contentDescription?.let { texts.add(it.toString()) }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            extractTextRecursive(child, texts)
            child.recycle()
        }
    }
}

enum class ScrollDirection {
    UP,
    DOWN,
    LEFT,
    RIGHT
}
