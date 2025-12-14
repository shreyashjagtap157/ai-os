package com.aios.launcher.di

import android.content.Context
import com.aios.launcher.agent.*
import com.aios.launcher.system.*
import com.aios.launcher.ui.overlay.AgentOverlay
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/** Hilt Dependency Injection Module for AI-OS. */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideDeviceController(@ApplicationContext context: Context): DeviceController {
        return DeviceController(context)
    }

    @Provides
    @Singleton
    fun provideDeepSystemController(@ApplicationContext context: Context): DeepSystemController {
        return DeepSystemController(context)
    }

    @Provides
    @Singleton
    fun provideSystemSettingsController(
            @ApplicationContext context: Context
    ): SystemSettingsController {
        return SystemSettingsController(context)
    }

    @Provides
    @Singleton
    fun provideAppManager(@ApplicationContext context: Context): AppManager {
        return AppManager(context)
    }

    @Provides
    @Singleton
    fun provideDevicePolicyManager(@ApplicationContext context: Context): AIosDevicePolicyManager {
        return AIosDevicePolicyManager(context)
    }

    @Provides
    @Singleton
    fun provideAIAgent(
            @ApplicationContext context: Context,
            deviceController: DeviceController
    ): AIAgent {
        return AIAgent(context, deviceController)
    }

    @Provides
    @Singleton
    fun provideEnhancedAIAgent(
            @ApplicationContext context: Context,
            deviceController: DeviceController,
            deepSystemController: DeepSystemController,
            systemSettings: SystemSettingsController
    ): EnhancedAIAgent {
        return EnhancedAIAgent(context, deviceController, deepSystemController, systemSettings)
    }

    @Provides
    @Singleton
    fun provideAgentOrchestrator(
            @ApplicationContext context: Context,
            enhancedAgent: EnhancedAIAgent,
            deviceController: DeviceController,
            deepSystemController: DeepSystemController,
            systemSettings: SystemSettingsController,
            appManager: AppManager,
            devicePolicy: AIosDevicePolicyManager
    ): AgentOrchestrator {
        return AgentOrchestrator(
                context,
                enhancedAgent,
                deviceController,
                deepSystemController,
                systemSettings,
                appManager,
                devicePolicy
        )
    }

    @Provides
    @Singleton
    fun provideAgentOverlay(@ApplicationContext context: Context): AgentOverlay {
        return AgentOverlay(context)
    }
}
