/**
 * AI-OS Voice Service Header
 * Voice recognition, TTS, and wake word detection
 */

#ifndef AIOS_VOICE_H
#define AIOS_VOICE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    VOICE_STATE_IDLE = 0,
    VOICE_STATE_LISTENING,
    VOICE_STATE_PROCESSING,
    VOICE_STATE_SPEAKING,
    VOICE_STATE_ERROR
} VoiceState;

typedef enum {
    VOICE_ERROR_NONE = 0,
    VOICE_ERROR_NO_MICROPHONE,
    VOICE_ERROR_RECOGNITION_FAILED,
    VOICE_ERROR_TTS_FAILED,
    VOICE_ERROR_NETWORK,
    VOICE_ERROR_PERMISSION
} VoiceError;

typedef struct {
    char text[1024];
    float confidence;
    char language[8];
    bool is_final;
    int audio_level;  // 0-100
} SpeechResult;

typedef struct {
    char word[32];
    bool enabled;
    float sensitivity;  // 0.0-1.0
    int detection_count;
} WakeWord;

typedef struct {
    char voice_id[64];
    char name[64];
    char language[8];
    char gender[16];
    float pitch;       // 0.5-2.0
    float speed;       // 0.5-2.0
    int sample_rate;
} TTSVoice;

typedef struct {
    bool wake_word_enabled;
    char wake_word[32];
    float wake_word_sensitivity;
    bool continuous_listening;
    char stt_language[8];
    char tts_voice_id[64];
    float tts_pitch;
    float tts_speed;
    int audio_input_device;
    int audio_output_device;
} VoiceSettings;

typedef void (*SpeechCallback)(const SpeechResult *result);
typedef void (*WakeWordCallback)(const char *wake_word);
typedef void (*VoiceStateCallback)(VoiceState state);

// ==================== Initialization ====================

/**
 * Initialize voice service
 * @return 0 on success
 */
int voice_init(void);

/**
 * Shutdown voice service
 */
void voice_shutdown(void);

/**
 * Get current voice state
 */
VoiceState voice_get_state(void);

// ==================== Speech Recognition ====================

/**
 * Start listening for speech
 * @return 0 on success
 */
int voice_start_listening(void);

/**
 * Stop listening
 */
void voice_stop_listening(void);

/**
 * Check if currently listening
 */
bool voice_is_listening(void);

/**
 * Get current audio level
 * @return Audio level 0-100
 */
int voice_get_audio_level(void);

/**
 * Set speech recognition language
 * @param language Language code (e.g., "en-US")
 * @return 0 on success
 */
int voice_set_language(const char *language);

// ==================== Wake Word ====================

/**
 * Enable wake word detection
 * @param enabled True to enable
 */
void voice_set_wake_word_enabled(bool enabled);

/**
 * Check if wake word detection is enabled
 */
bool voice_is_wake_word_enabled(void);

/**
 * Set wake word
 * @param word Wake word to detect
 * @return 0 on success
 */
int voice_set_wake_word(const char *word);

/**
 * Set wake word sensitivity
 * @param sensitivity Sensitivity 0.0-1.0
 */
void voice_set_wake_word_sensitivity(float sensitivity);

// ==================== Text-to-Speech ====================

/**
 * Speak text
 * @param text Text to speak
 * @return 0 on success
 */
int voice_speak(const char *text);

/**
 * Speak text with SSML markup
 * @param ssml SSML-formatted text
 * @return 0 on success
 */
int voice_speak_ssml(const char *ssml);

/**
 * Stop speaking
 */
void voice_stop_speaking(void);

/**
 * Check if currently speaking
 */
bool voice_is_speaking(void);

/**
 * Get available TTS voices
 * @param voices Array to fill
 * @param max_count Maximum voices to return
 * @return Number of voices
 */
int voice_get_voices(TTSVoice *voices, int max_count);

/**
 * Set TTS voice
 * @param voice_id Voice ID
 * @return 0 on success
 */
int voice_set_voice(const char *voice_id);

/**
 * Set TTS pitch
 * @param pitch Pitch multiplier (0.5-2.0)
 */
void voice_set_pitch(float pitch);

/**
 * Set TTS speed
 * @param speed Speed multiplier (0.5-2.0)
 */
void voice_set_speed(float speed);

// ==================== Settings ====================

/**
 * Get voice settings
 * @param settings Pointer to settings structure
 * @return 0 on success
 */
int voice_get_settings(VoiceSettings *settings);

/**
 * Update voice settings
 * @param settings New settings
 * @return 0 on success
 */
int voice_set_settings(const VoiceSettings *settings);

// ==================== Callbacks ====================

/**
 * Register speech recognition callback
 */
void voice_register_speech_callback(SpeechCallback callback);

/**
 * Register wake word callback
 */
void voice_register_wake_word_callback(WakeWordCallback callback);

/**
 * Register state change callback
 */
void voice_register_state_callback(VoiceStateCallback callback);

#ifdef __cplusplus
}
#endif

#endif // AIOS_VOICE_H
