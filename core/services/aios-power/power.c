/**
 * AI-OS Power Manager
 * Battery monitoring and power management in C.
 * 
 * Compile: gcc -o aios-power power.c hal.c -lpthread
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

#include "hal.h"

/* ==================== Configuration ==================== */

#define SOCKET_PATH "/run/aios/power.sock"
#define CONFIG_PATH "/etc/aios/power.json"

typedef struct {
    int low_battery_threshold;      /* 15% */
    int critical_battery_threshold; /* 5% */
    int auto_suspend_minutes;       /* 0 = disabled */
    int dim_on_battery;             /* 1 = yes */
} power_config_t;

/* ==================== Globals ==================== */

static volatile int g_running = 1;
static int g_server_fd = -1;
static power_config_t g_config = {15, 5, 0, 1};
static int g_last_battery_level = -1;

/* ==================== Power Profiles ==================== */

typedef enum {
    PROFILE_PERFORMANCE,
    PROFILE_BALANCED,
    PROFILE_POWERSAVE
} power_profile_t;

static power_profile_t g_current_profile = PROFILE_BALANCED;

static int set_power_profile(power_profile_t profile) {
    const char *governor;
    
    switch (profile) {
        case PROFILE_PERFORMANCE:
            governor = "performance";
            break;
        case PROFILE_POWERSAVE:
            governor = "powersave";
            break;
        default:
            governor = "schedutil";
            break;
    }
    
    /* Set CPU governor */
    char cmd[128];
    snprintf(cmd, sizeof(cmd), 
        "for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do "
        "echo %s > $cpu 2>/dev/null; done", governor);
    system(cmd);
    
    g_current_profile = profile;
    printf("[POWER] Profile set to: %s\n", governor);
    
    return 0;
}

/* ==================== Battery Monitoring ==================== */

static void check_battery(void) {
    battery_info_t bat;
    
    if (hal_battery_get(&bat) < 0 || !bat.present) {
        return;
    }
    
    /* Check for state changes */
    if (g_last_battery_level != bat.level) {
        g_last_battery_level = bat.level;
        
        /* Critical battery */
        if (bat.level <= g_config.critical_battery_threshold &&
            strcmp(bat.status, "Discharging") == 0) {
            printf("[POWER] CRITICAL battery: %d%%\n", bat.level);
            
            /* Notify user */
            char cmd[256];
            snprintf(cmd, sizeof(cmd),
                "notify-send -u critical 'Critical Battery' 'Battery at %d%%. Suspending in 30 seconds.'",
                bat.level);
            system(cmd);
            
            /* Wait then suspend */
            sleep(30);
            
            battery_info_t check;
            hal_battery_get(&check);
            if (check.level <= g_config.critical_battery_threshold &&
                strcmp(check.status, "Discharging") == 0) {
                hal_suspend();
            }
        }
        /* Low battery warning */
        else if (bat.level <= g_config.low_battery_threshold &&
                 strcmp(bat.status, "Discharging") == 0) {
            printf("[POWER] Low battery: %d%%\n", bat.level);
            
            char cmd[256];
            snprintf(cmd, sizeof(cmd),
                "notify-send -u normal 'Low Battery' 'Battery at %d%%. Please connect charger.'",
                bat.level);
            system(cmd);
        }
    }
    
    /* Auto-adjust profile based on power source */
    int on_ac = hal_on_ac_power();
    if (on_ac == 1 && g_current_profile == PROFILE_POWERSAVE) {
        set_power_profile(PROFILE_BALANCED);
    } else if (on_ac == 0 && g_current_profile == PROFILE_PERFORMANCE) {
        set_power_profile(PROFILE_BALANCED);
    }
}

static void *battery_monitor_thread(void *arg) {
    while (g_running) {
        check_battery();
        sleep(60);  /* Check every minute */
    }
    return NULL;
}

/* ==================== IPC Server ==================== */

static void handle_client(int client_fd) {
    uint32_t length;
    if (recv(client_fd, &length, 4, 0) != 4) return;
    length = ntohl(length);
    
    if (length > 4096) return;
    
    char *msg = malloc(length + 1);
    if (!msg) return;
    
    if (recv(client_fd, msg, length, 0) != length) {
        free(msg);
        return;
    }
    msg[length] = '\0';
    
    char response[1024] = "{\"status\":\"ok\"}";
    
    /* Parse command */
    if (strstr(msg, "\"cmd\":\"battery\"")) {
        battery_info_t bat;
        hal_battery_get(&bat);
        
        snprintf(response, sizeof(response),
            "{\"status\":\"ok\",\"battery\":{"
            "\"present\":%s,\"level\":%d,\"status\":\"%s\","
            "\"time_to_empty\":%d,\"time_to_full\":%d}}",
            bat.present ? "true" : "false",
            bat.level, bat.status,
            bat.time_to_empty, bat.time_to_full);
    }
    else if (strstr(msg, "\"cmd\":\"profile\"")) {
        if (strstr(msg, "\"set\":\"performance\"")) {
            set_power_profile(PROFILE_PERFORMANCE);
        } else if (strstr(msg, "\"set\":\"powersave\"")) {
            set_power_profile(PROFILE_POWERSAVE);
        } else if (strstr(msg, "\"set\":\"balanced\"")) {
            set_power_profile(PROFILE_BALANCED);
        }
        
        const char *profile_name = "balanced";
        if (g_current_profile == PROFILE_PERFORMANCE) profile_name = "performance";
        else if (g_current_profile == PROFILE_POWERSAVE) profile_name = "powersave";
        
        snprintf(response, sizeof(response),
            "{\"status\":\"ok\",\"profile\":\"%s\"}", profile_name);
    }
    else if (strstr(msg, "\"cmd\":\"suspend\"")) {
        hal_suspend();
    }
    else if (strstr(msg, "\"cmd\":\"hibernate\"")) {
        hal_hibernate();
    }
    else if (strstr(msg, "\"cmd\":\"poweroff\"")) {
        hal_poweroff();
    }
    else if (strstr(msg, "\"cmd\":\"reboot\"")) {
        hal_reboot();
    }
    else if (strstr(msg, "\"cmd\":\"brightness\"")) {
        char *set_ptr = strstr(msg, "\"set\":");
        if (set_ptr) {
            int level;
            if (sscanf(set_ptr, "\"set\":%d", &level) == 1) {
                hal_brightness_set(level);
            }
        }
        int brightness = hal_brightness_get();
        snprintf(response, sizeof(response),
            "{\"status\":\"ok\",\"brightness\":%d}", brightness);
    }
    
    free(msg);
    
    /* Send response */
    uint32_t resp_len = htonl(strlen(response));
    send(client_fd, &resp_len, 4, 0);
    send(client_fd, response, strlen(response), 0);
}

static int run_server(void) {
    g_server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (g_server_fd < 0) {
        perror("socket");
        return -1;
    }
    
    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
    
    unlink(SOCKET_PATH);
    
    if (bind(g_server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return -1;
    }
    
    chmod(SOCKET_PATH, 0666);
    listen(g_server_fd, 5);
    
    printf("[POWER] Listening on %s\n", SOCKET_PATH);
    
    while (g_running) {
        int client = accept(g_server_fd, NULL, NULL);
        if (client < 0) continue;
        
        handle_client(client);
        close(client);
    }
    
    return 0;
}

/* ==================== Main ==================== */

static void signal_handler(int sig) {
    g_running = 0;
}

int main(int argc, char *argv[]) {
    printf("[POWER] AI-OS Power Manager starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    mkdir("/run/aios", 0755);
    
    /* Set initial profile */
    set_power_profile(PROFILE_BALANCED);
    
    /* Start battery monitor thread */
    pthread_t battery_thread;
    pthread_create(&battery_thread, NULL, battery_monitor_thread, NULL);
    
    /* Run IPC server */
    run_server();
    
    /* Cleanup */
    pthread_join(battery_thread, NULL);
    
    if (g_server_fd >= 0) {
        close(g_server_fd);
        unlink(SOCKET_PATH);
    }
    
    printf("[POWER] Power manager stopped\n");
    return 0;
}
