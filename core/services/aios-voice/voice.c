/**
 * AI-OS Voice Service
 * Speech recognition and TTS in C using PocketSphinx and eSpeak.
 * 
 * Compile: gcc -o aios-voice voice.c -lpocketsphinx -lsphinxbase -lasound -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <alsa/asoundlib.h>

/* PocketSphinx for speech recognition */
#ifdef USE_POCKETSPHINX
#include <pocketsphinx.h>
#endif

#define AGENT_SOCKET "/run/aios/agent.sock"
#define SAMPLE_RATE 16000
#define CHANNELS 1
#define WAKE_WORD "hey ai"

/* ==================== Globals ==================== */

static volatile int g_running = 1;
static int g_voice_enabled = 1;
static char g_wake_word[64] = WAKE_WORD;

/* ==================== Text-to-Speech ==================== */

static void tts_speak(const char *text) {
    if (!text || !text[0]) return;
    
    printf("[VOICE] Speaking: %s\n", text);
    
    /* Use espeak for TTS */
    char cmd[2048];
    snprintf(cmd, sizeof(cmd), "espeak -s 150 \"%s\" 2>/dev/null", text);
    system(cmd);
}

/* ==================== Agent Communication ==================== */

static int send_to_agent(const char *text, char *response, size_t response_size) {
    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) return -1;
    
    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, AGENT_SOCKET);
    
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        return -1;
    }
    
    /* Build message */
    char msg[2048];
    snprintf(msg, sizeof(msg), "{\"cmd\":\"chat\",\"text\":\"%s\"}", text);
    
    uint32_t len = htonl(strlen(msg));
    send(sock, &len, 4, 0);
    send(sock, msg, strlen(msg), 0);
    
    /* Receive response */
    if (recv(sock, &len, 4, 0) != 4) {
        close(sock);
        return -1;
    }
    len = ntohl(len);
    
    if (len < response_size) {
        recv(sock, response, len, 0);
        response[len] = '\0';
    }
    
    close(sock);
    return 0;
}

static void process_command(const char *command) {
    printf("[VOICE] Processing: %s\n", command);
    
    char response[4096] = {0};
    if (send_to_agent(command, response, sizeof(response)) == 0) {
        /* Extract response text */
        char *p = strstr(response, "\"response\":\"");
        if (p) {
            p += 12;
            char *end = strchr(p, '"');
            if (end) {
                *end = '\0';
                /* Unescape */
                char clean[1024];
                char *src = p, *dst = clean;
                while (*src && dst < clean + sizeof(clean) - 1) {
                    if (*src == '\\' && *(src+1) == 'n') {
                        *dst++ = ' ';
                        src += 2;
                    } else {
                        *dst++ = *src++;
                    }
                }
                *dst = '\0';
                tts_speak(clean);
            }
        }
    } else {
        tts_speak("Sorry, I couldn't connect to the agent.");
    }
}

/* ==================== Audio Capture ==================== */

static snd_pcm_t *open_audio_capture(void) {
    snd_pcm_t *handle;
    snd_pcm_hw_params_t *params;
    int err;
    
    err = snd_pcm_open(&handle, "default", SND_PCM_STREAM_CAPTURE, 0);
    if (err < 0) {
        fprintf(stderr, "[VOICE] Cannot open audio: %s\n", snd_strerror(err));
        return NULL;
    }
    
    snd_pcm_hw_params_alloca(&params);
    snd_pcm_hw_params_any(handle, params);
    snd_pcm_hw_params_set_access(handle, params, SND_PCM_ACCESS_RW_INTERLEAVED);
    snd_pcm_hw_params_set_format(handle, params, SND_PCM_FORMAT_S16_LE);
    snd_pcm_hw_params_set_channels(handle, params, CHANNELS);
    
    unsigned int rate = SAMPLE_RATE;
    snd_pcm_hw_params_set_rate_near(handle, params, &rate, 0);
    
    snd_pcm_hw_params_set_period_size(handle, params, 1024, 0);
    snd_pcm_hw_params_set_buffer_size(handle, params, 8192);
    
    err = snd_pcm_hw_params(handle, params);
    if (err < 0) {
        fprintf(stderr, "[VOICE] Cannot set params: %s\n", snd_strerror(err));
        snd_pcm_close(handle);
        return NULL;
    }
    
    return handle;
}

/* ==================== Simple Voice Activity Detection ==================== */

static int detect_voice_activity(int16_t *buffer, int frames) {
    int32_t sum = 0;
    for (int i = 0; i < frames; i++) {
        sum += abs(buffer[i]);
    }
    int avg = sum / frames;
    return avg > 500;  /* Threshold */
}

/* ==================== Speech Recognition Loop ==================== */

#ifdef USE_POCKETSPHINX

static void recognition_loop(void) {
    snd_pcm_t *audio = open_audio_capture();
    if (!audio) {
        fprintf(stderr, "[VOICE] No audio device\n");
        return;
    }
    
    /* Initialize PocketSphinx */
    ps_config_t *config = ps_config_init(NULL);
    ps_config_set_str(config, "hmm", "/usr/share/pocketsphinx/model/en-us/en-us");
    ps_config_set_str(config, "lm", "/usr/share/pocketsphinx/model/en-us/en-us.lm.bin");
    ps_config_set_str(config, "dict", "/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict");
    
    ps_decoder_t *decoder = ps_init(config);
    if (!decoder) {
        fprintf(stderr, "[VOICE] Failed to init decoder\n");
        snd_pcm_close(audio);
        return;
    }
    
    ps_start_utt(decoder);
    
    int16_t buffer[1024];
    int listening_for_command = 0;
    int silence_frames = 0;
    char command[256] = {0};
    
    printf("[VOICE] Listening for wake word: '%s'\n", g_wake_word);
    
    while (g_running) {
        int frames = snd_pcm_readi(audio, buffer, 1024);
        if (frames < 0) {
            snd_pcm_recover(audio, frames, 0);
            continue;
        }
        
        ps_process_raw(decoder, buffer, frames, FALSE, FALSE);
        
        const char *hyp = ps_get_hyp(decoder, NULL);
        
        if (hyp) {
            char lower[256];
            strncpy(lower, hyp, sizeof(lower) - 1);
            for (char *p = lower; *p; p++) *p = (*p >= 'A' && *p <= 'Z') ? *p + 32 : *p;
            
            if (!listening_for_command) {
                if (strstr(lower, g_wake_word)) {
                    printf("[VOICE] Wake word detected!\n");
                    tts_speak("Yes?");
                    listening_for_command = 1;
                    command[0] = '\0';
                    ps_end_utt(decoder);
                    ps_start_utt(decoder);
                }
            } else {
                /* Accumulate command */
                strncpy(command, hyp, sizeof(command) - 1);
                
                /* Check for silence */
                if (!detect_voice_activity(buffer, frames)) {
                    silence_frames++;
                    if (silence_frames > 20) {  /* ~1 second of silence */
                        if (command[0]) {
                            process_command(command);
                        }
                        listening_for_command = 0;
                        silence_frames = 0;
                        ps_end_utt(decoder);
                        ps_start_utt(decoder);
                    }
                } else {
                    silence_frames = 0;
                }
            }
        }
    }
    
    ps_end_utt(decoder);
    ps_free(decoder);
    ps_config_free(config);
    snd_pcm_close(audio);
}

#else

/* Simplified loop without PocketSphinx - uses external speech-to-text */
static void recognition_loop(void) {
    printf("[VOICE] Running in voice activity detection mode\n");
    printf("[VOICE] Say '%s' to activate\n", g_wake_word);
    
    snd_pcm_t *audio = open_audio_capture();
    if (!audio) {
        /* Fallback to console input */
        printf("[VOICE] No audio, using console input\n");
        
        char line[256];
        while (g_running) {
            printf("Voice> ");
            if (!fgets(line, sizeof(line), stdin)) break;
            
            line[strcspn(line, "\n")] = '\0';
            if (line[0]) {
                process_command(line);
            }
        }
        return;
    }
    
    int16_t buffer[1024];
    int was_speaking = 0;
    int silence_count = 0;
    
    while (g_running) {
        int frames = snd_pcm_readi(audio, buffer, 1024);
        if (frames < 0) {
            snd_pcm_recover(audio, frames, 0);
            continue;
        }
        
        int is_speaking = detect_voice_activity(buffer, frames);
        
        if (is_speaking && !was_speaking) {
            printf("[VOICE] Voice activity detected\n");
        } else if (!is_speaking && was_speaking) {
            silence_count++;
            if (silence_count > 10) {
                printf("[VOICE] Voice ended\n");
                /* Would trigger STT here */
                silence_count = 0;
            }
        }
        
        was_speaking = is_speaking;
        usleep(10000);
    }
    
    snd_pcm_close(audio);
}

#endif

/* ==================== Main ==================== */

static void signal_handler(int sig) {
    g_running = 0;
}

int main(int argc, char *argv[]) {
    printf("[VOICE] AI-OS Voice Service starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    /* Load config */
    FILE *f = fopen("/etc/aios/voice.json", "r");
    if (f) {
        char buf[1024];
        fread(buf, 1, sizeof(buf), f);
        fclose(f);
        
        char *p = strstr(buf, "\"wake_word\":\"");
        if (p) {
            sscanf(p, "\"wake_word\":\"%63[^\"]\"", g_wake_word);
        }
        
        if (strstr(buf, "\"enabled\":false")) {
            g_voice_enabled = 0;
        }
    }
    
    if (!g_voice_enabled) {
        printf("[VOICE] Voice service disabled\n");
        while (g_running) sleep(60);
        return 0;
    }
    
    tts_speak("AI-OS voice service ready");
    
    recognition_loop();
    
    printf("[VOICE] Voice service stopped\n");
    return 0;
}
