package com.aios.launcher.ui.home

import android.content.Intent
import android.content.pm.PackageManager
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aios.launcher.agent.AppInfo
import com.aios.launcher.agent.DeviceController
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*
import javax.inject.Inject

/**
 * ViewModel for the Home Screen.
 */
@HiltViewModel
class HomeViewModel @Inject constructor(
    private val deviceController: DeviceController
) : ViewModel() {
    
    private val _apps = MutableStateFlow<List<AppInfo>>(emptyList())
    val apps: StateFlow<List<AppInfo>> = _apps
    
    private val _currentTime = MutableStateFlow("")
    val currentTime: StateFlow<String> = _currentTime
    
    private val _currentDate = MutableStateFlow("")
    val currentDate: StateFlow<String> = _currentDate
    
    private val timeFormat = SimpleDateFormat("HH:mm", Locale.getDefault())
    private val dateFormat = SimpleDateFormat("EEEE, MMMM d", Locale.getDefault())
    
    init {
        loadApps()
        startClock()
    }
    
    private fun loadApps() {
        viewModelScope.launch {
            _apps.value = deviceController.getInstalledApps()
        }
    }
    
    private fun startClock() {
        viewModelScope.launch {
            while (true) {
                val now = Date()
                _currentTime.value = timeFormat.format(now)
                _currentDate.value = dateFormat.format(now)
                delay(1000)
            }
        }
    }
    
    fun openApp(app: AppInfo) {
        deviceController.openApp(app.packageName)
    }
    
    fun refreshApps() {
        loadApps()
    }
}
