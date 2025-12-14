/**
 * AI-OS Agent Daemon Implementation
 * Core AI agent with LLM integration and action execution.
 * 
 * Compile: gcc -o aios-agent agent.c -I../../hal -L../../hal -laios-hal -lcurl -lcjson -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <time.h>
#include <curl/curl.h>
#include <cjson/cJSON.h>

#include "agent.h"
#include "hal.h"

/* ==================== Globals ==================== */

static agent_config_t g_config;
static int g_server_fd = -1;
static volatile bool g_running = false;
static chat_message_t g_history[MAX_HISTORY_SIZE];
static int g_history_count = 0;
static pthread_mutex_t g_history_mutex = PTHREAD_MUTEX_INITIALIZER;

/* ==================== Logging ==================== */

static FILE *g_log_file = NULL;

static void log_msg(const char *level, const char *fmt, ...) {
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", tm);
    
    va_list args;
    va_start(args, fmt);
    
    fprintf(stderr, "[%s] [%s] ", timestamp, level);
    vfprintf(stderr, fmt, args);
    fprintf(stderr, "\n");
    
    if (g_log_file) {
        fprintf(g_log_file, "[%s] [%s] ", timestamp, level);
        vfprintf(g_log_file, fmt, args);
        fprintf(g_log_file, "\n");
        fflush(g_log_file);
    }
    
    va_end(args);
}

#define LOG_INFO(...)  log_msg("INFO", __VA_ARGS__)
#define LOG_WARN(...)  log_msg("WARN", __VA_ARGS__)
#define LOG_ERROR(...) log_msg("ERROR", __VA_ARGS__)

/* ==================== Configuration ==================== */

static int load_config(void) {
    /* Defaults */
    g_config.provider = AI_PROVIDER_LOCAL;
    g_config.confirm_dangerous = true;
    strcpy(g_config.model, "gpt-4");
    
    /* Load from environment */
    const char *key = getenv("OPENAI_API_KEY");
    if (key && key[0]) {
        strncpy(g_config.openai_api_key, key, sizeof(g_config.openai_api_key) - 1);
        g_config.provider = AI_PROVIDER_OPENAI;
    }
    
    key = getenv("ANTHROPIC_API_KEY");
    if (key && key[0]) {
        strncpy(g_config.anthropic_api_key, key, sizeof(g_config.anthropic_api_key) - 1);
        if (g_config.provider == AI_PROVIDER_LOCAL) {
            g_config.provider = AI_PROVIDER_ANTHROPIC;
        }
    }
    
    /* Load from config file */
    FILE *f = fopen(AGENT_CONFIG_PATH, "r");
    if (f) {
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        fseek(f, 0, SEEK_SET);
        
        char *buf = malloc(size + 1);
        if (buf) {
            fread(buf, 1, size, f);
            buf[size] = '\0';
            
            cJSON *json = cJSON_Parse(buf);
            if (json) {
                cJSON *item = cJSON_GetObjectItem(json, "provider");
                if (item && item->valuestring) {
                    if (strcmp(item->valuestring, "openai") == 0)
                        g_config.provider = AI_PROVIDER_OPENAI;
                    else if (strcmp(item->valuestring, "anthropic") == 0)
                        g_config.provider = AI_PROVIDER_ANTHROPIC;
                }
                
                item = cJSON_GetObjectItem(json, "model");
                if (item && item->valuestring)
                    strncpy(g_config.model, item->valuestring, sizeof(g_config.model) - 1);
                
                item = cJSON_GetObjectItem(json, "confirm_dangerous");
                if (item)
                    g_config.confirm_dangerous = cJSON_IsTrue(item);
                
                cJSON_Delete(json);
            }
            free(buf);
        }
        fclose(f);
    }
    
    LOG_INFO("Config loaded - provider: %d, model: %s", g_config.provider, g_config.model);
    return 0;
}

/* ==================== HTTP Helper ==================== */

struct response_buffer {
    char *data;
    size_t size;
};

static size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t total = size * nmemb;
    struct response_buffer *buf = (struct response_buffer *)userp;
    
    char *ptr = realloc(buf->data, buf->size + total + 1);
    if (!ptr) return 0;
    
    buf->data = ptr;
    memcpy(&buf->data[buf->size], contents, total);
    buf->size += total;
    buf->data[buf->size] = '\0';
    
    return total;
}

/* ==================== AI Integration ==================== */

static int call_openai(const char *user_message, char *response, size_t response_size) {
    CURL *curl = curl_easy_init();
    if (!curl) return -1;
    
    /* Build request */
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "model", g_config.model);
    
    cJSON *messages = cJSON_CreateArray();
    
    /* System prompt */
    cJSON *sys_msg = cJSON_CreateObject();
    cJSON_AddStringToObject(sys_msg, "role", "system");
    cJSON_AddStringToObject(sys_msg, "content", 
        "You are AI-OS, an AI assistant integrated into the operating system. "
        "You can control hardware and system settings. When you need to perform an action, "
        "respond with JSON: {\"action\": \"name\", \"param\": value}. "
        "Actions: brightness, volume, mute, wifi, bluetooth, shutdown, reboot, suspend, launch, info");
    cJSON_AddItemToArray(messages, sys_msg);
    
    /* History */
    pthread_mutex_lock(&g_history_mutex);
    for (int i = 0; i < g_history_count; i++) {
        cJSON *msg = cJSON_CreateObject();
        cJSON_AddStringToObject(msg, "role", g_history[i].role);
        cJSON_AddStringToObject(msg, "content", g_history[i].content);
        cJSON_AddItemToArray(messages, msg);
    }
    pthread_mutex_unlock(&g_history_mutex);
    
    /* User message */
    cJSON *user_msg = cJSON_CreateObject();
    cJSON_AddStringToObject(user_msg, "role", "user");
    cJSON_AddStringToObject(user_msg, "content", user_message);
    cJSON_AddItemToArray(messages, user_msg);
    
    cJSON_AddItemToObject(root, "messages", messages);
    cJSON_AddNumberToObject(root, "max_tokens", 1024);
    
    char *post_data = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    
    /* Setup request */
    struct curl_slist *headers = NULL;
    char auth_header[300];
    snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", g_config.openai_api_key);
    headers = curl_slist_append(headers, auth_header);
    headers = curl_slist_append(headers, "Content-Type: application/json");
    
    struct response_buffer resp = {0};
    
    curl_easy_setopt(curl, CURLOPT_URL, "https://api.openai.com/v1/chat/completions");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_data);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &resp);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
    
    CURLcode res = curl_easy_perform(curl);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    free(post_data);
    
    if (res != CURLE_OK) {
        LOG_ERROR("HTTP request failed: %s", curl_easy_strerror(res));
        free(resp.data);
        return -1;
    }
    
    /* Parse response */
    cJSON *json = cJSON_Parse(resp.data);
    free(resp.data);
    
    if (!json) {
        LOG_ERROR("Failed to parse response");
        return -1;
    }
    
    cJSON *choices = cJSON_GetObjectItem(json, "choices");
    if (choices && cJSON_GetArraySize(choices) > 0) {
        cJSON *choice = cJSON_GetArrayItem(choices, 0);
        cJSON *message = cJSON_GetObjectItem(choice, "message");
        cJSON *content = cJSON_GetObjectItem(message, "content");
        
        if (content && content->valuestring) {
            strncpy(response, content->valuestring, response_size - 1);
            response[response_size - 1] = '\0';
        }
    }
    
    cJSON_Delete(json);
    return 0;
}

static int process_local_fallback(const char *input, char *response, size_t response_size) {
    char lower[256];
    strncpy(lower, input, sizeof(lower) - 1);
    for (char *p = lower; *p; p++) *p = (*p >= 'A' && *p <= 'Z') ? *p + 32 : *p;
    
    if (strstr(lower, "brightness")) {
        int level = -1;
        if (strstr(lower, "up") || strstr(lower, "increase")) level = hal_brightness_get() + 20;
        else if (strstr(lower, "down") || strstr(lower, "decrease")) level = hal_brightness_get() - 20;
        else sscanf(lower, "%*[^0-9]%d", &level);
        
        if (level >= 0) {
            if (level > 100) level = 100;
            hal_brightness_set(level);
            snprintf(response, response_size, "{\"action\":\"brightness\",\"level\":%d}", level);
            return 0;
        }
    }
    else if (strstr(lower, "volume")) {
        int level = -1;
        if (strstr(lower, "up")) level = hal_volume_get() + 10;
        else if (strstr(lower, "down")) level = hal_volume_get() - 10;
        else if (strstr(lower, "mute")) {
            hal_mute_set(true);
            snprintf(response, response_size, "{\"action\":\"mute\",\"muted\":true}");
            return 0;
        }
        else sscanf(lower, "%*[^0-9]%d", &level);
        
        if (level >= 0) {
            if (level > 100) level = 100;
            hal_volume_set(level);
            snprintf(response, response_size, "{\"action\":\"volume\",\"level\":%d}", level);
            return 0;
        }
    }
    else if (strstr(lower, "battery")) {
        battery_info_t bat;
        hal_battery_get(&bat);
        snprintf(response, response_size, 
            "Battery: %d%%, Status: %s", bat.level, bat.status);
        return 0;
    }
    else if (strstr(lower, "time") || strstr(lower, "clock")) {
        time_t now = time(NULL);
        struct tm *tm = localtime(&now);
        strftime(response, response_size, "The time is %H:%M:%S", tm);
        return 0;
    }
    else if (strstr(lower, "date")) {
        time_t now = time(NULL);
        struct tm *tm = localtime(&now);
        strftime(response, response_size, "Today is %A, %B %d, %Y", tm);
        return 0;
    }
    else if (strstr(lower, "shutdown") || strstr(lower, "power off")) {
        snprintf(response, response_size, "{\"action\":\"shutdown\"}");
        return 0;
    }
    else if (strstr(lower, "reboot") || strstr(lower, "restart")) {
        snprintf(response, response_size, "{\"action\":\"reboot\"}");
        return 0;
    }
    else if (strstr(lower, "wifi")) {
        bool enable = strstr(lower, "on") || strstr(lower, "enable");
        bool disable = strstr(lower, "off") || strstr(lower, "disable");
        if (enable || disable) {
            hal_wifi_set(enable);
            snprintf(response, response_size, "{\"action\":\"wifi\",\"enabled\":%s}", enable ? "true" : "false");
            return 0;
        }
    }
    
    snprintf(response, response_size, "I can help with: brightness, volume, battery, time, date, wifi, shutdown, reboot");
    return 0;
}

/* ==================== Action Execution ==================== */

int agent_execute_action(const char *action_json, action_result_t *result) {
    result->success = false;
    strcpy(result->message, "Unknown action");
    result->data = NULL;
    
    cJSON *json = cJSON_Parse(action_json);
    if (!json) return -1;
    
    cJSON *action = cJSON_GetObjectItem(json, "action");
    if (!action || !action->valuestring) {
        cJSON_Delete(json);
        return -1;
    }
    
    const char *act = action->valuestring;
    
    if (strcmp(act, "brightness") == 0) {
        cJSON *level = cJSON_GetObjectItem(json, "level");
        if (level) {
            int ret = hal_brightness_set(level->valueint);
            result->success = (ret == 0);
            snprintf(result->message, sizeof(result->message), 
                "Brightness set to %d%%", level->valueint);
        }
    }
    else if (strcmp(act, "volume") == 0) {
        cJSON *level = cJSON_GetObjectItem(json, "level");
        if (level) {
            int ret = hal_volume_set(level->valueint);
            result->success = (ret == 0);
            snprintf(result->message, sizeof(result->message), 
                "Volume set to %d%%", level->valueint);
        }
    }
    else if (strcmp(act, "mute") == 0) {
        cJSON *muted = cJSON_GetObjectItem(json, "muted");
        bool m = muted ? cJSON_IsTrue(muted) : true;
        hal_mute_set(m);
        result->success = true;
        strcpy(result->message, m ? "Muted" : "Unmuted");
    }
    else if (strcmp(act, "wifi") == 0) {
        cJSON *enabled = cJSON_GetObjectItem(json, "enabled");
        hal_wifi_set(cJSON_IsTrue(enabled));
        result->success = true;
        strcpy(result->message, cJSON_IsTrue(enabled) ? "WiFi enabled" : "WiFi disabled");
    }
    else if (strcmp(act, "bluetooth") == 0) {
        cJSON *enabled = cJSON_GetObjectItem(json, "enabled");
        hal_bluetooth_set(cJSON_IsTrue(enabled));
        result->success = true;
        strcpy(result->message, cJSON_IsTrue(enabled) ? "Bluetooth enabled" : "Bluetooth disabled");
    }
    else if (strcmp(act, "shutdown") == 0) {
        result->success = true;
        strcpy(result->message, "Shutting down...");
        /* Delayed shutdown */
        system("shutdown -h +1 &");
    }
    else if (strcmp(act, "reboot") == 0) {
        result->success = true;
        strcpy(result->message, "Rebooting...");
        system("shutdown -r +1 &");
    }
    else if (strcmp(act, "suspend") == 0) {
        hal_suspend();
        result->success = true;
        strcpy(result->message, "Suspended");
    }
    else if (strcmp(act, "launch") == 0) {
        cJSON *app = cJSON_GetObjectItem(json, "app");
        if (app && app->valuestring) {
            int ret = hal_app_launch(app->valuestring);
            result->success = (ret == 0);
            snprintf(result->message, sizeof(result->message),
                ret == 0 ? "Launched %s" : "Failed to launch %s", app->valuestring);
        }
    }
    else if (strcmp(act, "info") == 0) {
        system_info_t info;
        hal_system_info(&info);
        
        cJSON *data = cJSON_CreateObject();
        cJSON_AddStringToObject(data, "hostname", info.hostname);
        cJSON_AddStringToObject(data, "kernel", info.kernel);
        cJSON_AddNumberToObject(data, "memory_mb", info.memory_total_kb / 1024);
        cJSON_AddNumberToObject(data, "memory_free_mb", info.memory_free_kb / 1024);
        cJSON_AddNumberToObject(data, "uptime_hours", info.uptime_seconds / 3600);
        
        result->success = true;
        result->data = cJSON_PrintUnformatted(data);
        strcpy(result->message, "System info retrieved");
        cJSON_Delete(data);
    }
    
    cJSON_Delete(json);
    return 0;
}

/* ==================== Chat Processing ==================== */

int agent_chat(const char *input, char *response, size_t response_size, 
               action_result_t *action_result) {
    char ai_response[4096] = {0};
    
    /* Call AI or local fallback */
    if (g_config.provider == AI_PROVIDER_OPENAI && g_config.openai_api_key[0]) {
        if (call_openai(input, ai_response, sizeof(ai_response)) < 0) {
            process_local_fallback(input, ai_response, sizeof(ai_response));
        }
    } else {
        process_local_fallback(input, ai_response, sizeof(ai_response));
    }
    
    /* Copy response */
    strncpy(response, ai_response, response_size - 1);
    response[response_size - 1] = '\0';
    
    /* Check for action in response */
    if (action_result) {
        char *json_start = strchr(ai_response, '{');
        char *json_end = strrchr(ai_response, '}');
        
        if (json_start && json_end && json_end > json_start) {
            char action_json[1024];
            size_t len = json_end - json_start + 1;
            if (len < sizeof(action_json)) {
                memcpy(action_json, json_start, len);
                action_json[len] = '\0';
                agent_execute_action(action_json, action_result);
            }
        }
    }
    
    /* Add to history */
    pthread_mutex_lock(&g_history_mutex);
    if (g_history_count >= MAX_HISTORY_SIZE) {
        free(g_history[0].content);
        memmove(&g_history[0], &g_history[1], sizeof(chat_message_t) * (MAX_HISTORY_SIZE - 1));
        g_history_count--;
    }
    strcpy(g_history[g_history_count].role, "user");
    g_history[g_history_count].content = strdup(input);
    g_history_count++;
    
    if (g_history_count < MAX_HISTORY_SIZE) {
        strcpy(g_history[g_history_count].role, "assistant");
        g_history[g_history_count].content = strdup(ai_response);
        g_history_count++;
    }
    pthread_mutex_unlock(&g_history_mutex);
    
    return 0;
}

/* ==================== IPC Server ==================== */

static void *client_handler(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);
    
    while (1) {
        /* Read message length */
        uint32_t length;
        if (recv(client_fd, &length, 4, 0) != 4) break;
        length = ntohl(length);
        
        if (length > MAX_MESSAGE_SIZE) break;
        
        /* Read message */
        char *msg = malloc(length + 1);
        if (!msg) break;
        
        ssize_t received = 0;
        while (received < length) {
            ssize_t n = recv(client_fd, msg + received, length - received, 0);
            if (n <= 0) break;
            received += n;
        }
        if (received != length) {
            free(msg);
            break;
        }
        msg[length] = '\0';
        
        /* Parse request */
        cJSON *request = cJSON_Parse(msg);
        free(msg);
        
        if (!request) break;
        
        cJSON *cmd = cJSON_GetObjectItem(request, "cmd");
        cJSON *response = cJSON_CreateObject();
        
        if (cmd && cmd->valuestring) {
            if (strcmp(cmd->valuestring, "chat") == 0) {
                cJSON *text = cJSON_GetObjectItem(request, "text");
                if (text && text->valuestring) {
                    char resp[4096];
                    action_result_t action = {0};
                    
                    agent_chat(text->valuestring, resp, sizeof(resp), &action);
                    
                    cJSON_AddStringToObject(response, "status", "ok");
                    cJSON_AddStringToObject(response, "response", resp);
                    
                    if (action.message[0]) {
                        cJSON *act_result = cJSON_CreateObject();
                        cJSON_AddBoolToObject(act_result, "success", action.success);
                        cJSON_AddStringToObject(act_result, "message", action.message);
                        if (action.data) {
                            cJSON_AddRawToObject(act_result, "data", action.data);
                            free(action.data);
                        }
                        cJSON_AddItemToObject(response, "action_result", act_result);
                    }
                }
            }
            else if (strcmp(cmd->valuestring, "action") == 0) {
                cJSON *action = cJSON_GetObjectItem(request, "action");
                if (action) {
                    char *action_str = cJSON_PrintUnformatted(action);
                    action_result_t result = {0};
                    agent_execute_action(action_str, &result);
                    free(action_str);
                    
                    cJSON *res = cJSON_CreateObject();
                    cJSON_AddBoolToObject(res, "success", result.success);
                    cJSON_AddStringToObject(res, "message", result.message);
                    cJSON_AddItemToObject(response, "result", res);
                }
            }
            else if (strcmp(cmd->valuestring, "status") == 0) {
                system_info_t info;
                hal_system_info(&info);
                
                cJSON_AddStringToObject(response, "status", "ok");
                cJSON_AddBoolToObject(response, "running", true);
                cJSON_AddBoolToObject(response, "ai_configured", 
                    g_config.openai_api_key[0] || g_config.anthropic_api_key[0]);
                
                cJSON *sys = cJSON_CreateObject();
                cJSON_AddStringToObject(sys, "hostname", info.hostname);
                cJSON_AddStringToObject(sys, "kernel", info.kernel);
                cJSON_AddNumberToObject(sys, "memory_mb", info.memory_total_kb / 1024);
                cJSON_AddNumberToObject(sys, "memory_free_mb", info.memory_free_kb / 1024);
                cJSON_AddItemToObject(response, "system", sys);
            }
            else if (strcmp(cmd->valuestring, "clear") == 0) {
                pthread_mutex_lock(&g_history_mutex);
                for (int i = 0; i < g_history_count; i++) {
                    free(g_history[i].content);
                }
                g_history_count = 0;
                pthread_mutex_unlock(&g_history_mutex);
                cJSON_AddStringToObject(response, "status", "ok");
            }
        }
        
        cJSON_Delete(request);
        
        /* Send response */
        char *resp_str = cJSON_PrintUnformatted(response);
        cJSON_Delete(response);
        
        uint32_t resp_len = htonl(strlen(resp_str));
        send(client_fd, &resp_len, 4, 0);
        send(client_fd, resp_str, strlen(resp_str), 0);
        free(resp_str);
    }
    
    close(client_fd);
    return NULL;
}

int agent_run(void) {
    /* Create socket */
    g_server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (g_server_fd < 0) {
        LOG_ERROR("Failed to create socket: %s", strerror(errno));
        return -1;
    }
    
    /* Setup address */
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, AGENT_SOCKET_PATH, sizeof(addr.sun_path) - 1);
    
    /* Remove old socket */
    unlink(AGENT_SOCKET_PATH);
    
    /* Bind */
    if (bind(g_server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        LOG_ERROR("Failed to bind: %s", strerror(errno));
        return -1;
    }
    
    chmod(AGENT_SOCKET_PATH, 0666);
    
    /* Listen */
    if (listen(g_server_fd, 5) < 0) {
        LOG_ERROR("Failed to listen: %s", strerror(errno));
        return -1;
    }
    
    LOG_INFO("Agent listening on %s", AGENT_SOCKET_PATH);
    g_running = true;
    
    while (g_running) {
        int *client_fd = malloc(sizeof(int));
        *client_fd = accept(g_server_fd, NULL, NULL);
        
        if (*client_fd < 0) {
            free(client_fd);
            continue;
        }
        
        pthread_t thread;
        pthread_create(&thread, NULL, client_handler, client_fd);
        pthread_detach(thread);
    }
    
    return 0;
}

/* ==================== Initialization ==================== */

int agent_init(void) {
    /* Create directories */
    mkdir("/run/aios", 0755);
    mkdir("/var/log/aios", 0755);
    
    /* Open log file */
    g_log_file = fopen(AGENT_LOG_PATH, "a");
    
    /* Initialize libcurl */
    curl_global_init(CURL_GLOBAL_ALL);
    
    /* Load configuration */
    load_config();
    
    LOG_INFO("AI-OS Agent initialized");
    return 0;
}

void agent_cleanup(void) {
    g_running = false;
    
    if (g_server_fd >= 0) {
        close(g_server_fd);
        unlink(AGENT_SOCKET_PATH);
    }
    
    /* Free history */
    for (int i = 0; i < g_history_count; i++) {
        free(g_history[i].content);
    }
    
    curl_global_cleanup();
    
    if (g_log_file) fclose(g_log_file);
    
    LOG_INFO("Agent cleanup complete");
}

/* ==================== Signal Handlers ==================== */

static void signal_handler(int sig) {
    LOG_INFO("Received signal %d", sig);
    g_running = false;
}

/* ==================== Main ==================== */

int main(int argc, char *argv[]) {
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    LOG_INFO("Starting AI-OS Agent Daemon");
    
    if (agent_init() < 0) {
        LOG_ERROR("Failed to initialize agent");
        return 1;
    }
    
    int ret = agent_run();
    
    agent_cleanup();
    
    return ret;
}
