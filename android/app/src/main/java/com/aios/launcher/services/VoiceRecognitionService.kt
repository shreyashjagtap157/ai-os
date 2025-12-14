package com.aios.launcher.services

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aios.launcher.AIosApplication
import com.aios.launcher.R
import dagger.hilt.android.AndroidEntryPoint
import java.util.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Voice Recognition Service for AI-OS. Handles continuous voice listening and text-to-speech. */
@AndroidEntryPoint
class VoiceRecognitionService : Service(), RecognitionListener, TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "VoiceService"
        private const val NOTIFICATION_ID = 1002
        private const val WAKE_WORD = "hey ai"

        private val _isListening = MutableStateFlow(false)
        val isListening: StateFlow<Boolean> = _isListening

        private val _lastTranscription = MutableStateFlow("")
        val lastTranscription: StateFlow<String> = _lastTranscription

        fun start(context: Context) {
            val intent = Intent(context, VoiceRecognitionService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, VoiceRecognitionService::class.java))
        }
    }

    private var speechRecognizer: SpeechRecognizer? = null
    private var textToSpeech: TextToSpeech? = null
    private var isRecognizing = false
    private var isPaused = false

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private var onCommandReceived: ((String) -> Unit)? = null

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "VoiceRecognitionService created")

        initializeSpeechRecognizer()
        initializeTextToSpeech()

        startForeground(NOTIFICATION_ID, createNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startListening()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        stopListening()
        speechRecognizer?.destroy()
        textToSpeech?.shutdown()
        serviceScope.cancel()
        Log.d(TAG, "VoiceRecognitionService destroyed")
    }

    private fun initializeSpeechRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            speechRecognizer =
                    SpeechRecognizer.createSpeechRecognizer(this).apply {
                        setRecognitionListener(this@VoiceRecognitionService)
                    }
            Log.d(TAG, "Speech recognizer initialized")
        } else {
            Log.e(TAG, "Speech recognition not available")
        }
    }

    private fun initializeTextToSpeech() {
        textToSpeech = TextToSpeech(this, this)
    }

    // TextToSpeech.OnInitListener
    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            textToSpeech?.language = Locale.US
            Log.d(TAG, "TTS initialized")
        } else {
            Log.e(TAG, "TTS initialization failed")
        }
    }

    fun startListening() {
        if (speechRecognizer == null || isRecognizing) return

        val intent =
                Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                    )
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    // For continuous listening
                    putExtra(
                            RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS,
                            3000L
                    )
                    putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1000L)
                }

        try {
            speechRecognizer?.startListening(intent)
            isRecognizing = true
            _isListening.value = true
            Log.d(TAG, "Started listening")
        } catch (e: Exception) {
            Log.e(TAG, "Error starting listener", e)
        }
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        isRecognizing = false
        _isListening.value = false
        Log.d(TAG, "Stopped listening")
    }

    fun speak(text: String, onComplete: (() -> Unit)? = null) {
        // Pause listening while speaking
        isPaused = true
        stopListening()

        textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "aios_speech")

        // Resume listening after speaking
        serviceScope.launch {
            // Estimate speech duration
            delay((text.length * 50L).coerceAtMost(10000L))
            isPaused = false
            startListening()
            onComplete?.invoke()
        }
    }

    fun setOnCommandReceived(listener: (String) -> Unit) {
        onCommandReceived = listener
    }

    // RecognitionListener implementation

    override fun onReadyForSpeech(params: Bundle?) {
        Log.d(TAG, "Ready for speech")
    }

    override fun onBeginningOfSpeech() {
        Log.d(TAG, "Speech began")
    }

    override fun onRmsChanged(rmsdB: Float) {
        // Audio level changed - could update UI
    }

    override fun onBufferReceived(buffer: ByteArray?) {}

    override fun onEndOfSpeech() {
        Log.d(TAG, "Speech ended")
    }

    override fun onError(error: Int) {
        val errorMessage =
                when (error) {
                    SpeechRecognizer.ERROR_AUDIO -> "Audio error"
                    SpeechRecognizer.ERROR_CLIENT -> "Client error"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Insufficient permissions"
                    SpeechRecognizer.ERROR_NETWORK -> "Network error"
                    SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout"
                    SpeechRecognizer.ERROR_NO_MATCH -> "No match"
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer busy"
                    SpeechRecognizer.ERROR_SERVER -> "Server error"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Speech timeout"
                    else -> "Unknown error"
                }
        Log.e(TAG, "Recognition error: $errorMessage ($error)")

        isRecognizing = false

        // Restart listening after error (with delay)
        if (!isPaused) {
            serviceScope.launch {
                delay(1000)
                startListening()
            }
        }
    }

    override fun onResults(results: Bundle?) {
        isRecognizing = false

        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val transcription = matches?.firstOrNull() ?: return

        Log.d(TAG, "Recognized: $transcription")
        _lastTranscription.value = transcription

        // Check for wake word
        val lowerTranscription = transcription.lowercase()
        if (lowerTranscription.startsWith(WAKE_WORD)) {
            val command = transcription.substring(WAKE_WORD.length).trim()
            if (command.isNotEmpty()) {
                Log.d(TAG, "Command after wake word: $command")
                onCommandReceived?.invoke(command)
            }
        }

        // Restart listening (continuous mode)
        if (!isPaused) {
            serviceScope.launch {
                delay(500)
                startListening()
            }
        }
    }

    override fun onPartialResults(partialResults: Bundle?) {
        val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val partial = matches?.firstOrNull() ?: return
        Log.v(TAG, "Partial: $partial")
    }

    override fun onEvent(eventType: Int, params: Bundle?) {}

    private fun createNotification(): Notification {
        val pendingIntent =
                PendingIntent.getActivity(
                        this,
                        0,
                        packageManager.getLaunchIntentForPackage(packageName),
                        PendingIntent.FLAG_IMMUTABLE
                )

        return NotificationCompat.Builder(this, AIosApplication.VOICE_CHANNEL_ID)
                .setContentTitle("AI-OS Voice")
                .setContentText("Listening for \"Hey AI\"...")
                .setSmallIcon(R.drawable.ic_mic)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setSilent(true)
                .build()
    }
}
