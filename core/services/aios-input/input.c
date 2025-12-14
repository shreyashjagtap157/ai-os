/**
 * AI-OS Input Service
 * Handles keyboard input, hotkeys, and global shortcuts.
 * Uses libevdev for direct input device access.
 * 
 * Compile: gcc -o aios-input input.c hal.c -levdev -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <signal.h>
#include <pthread.h>
#include <errno.h>
#include <linux/input.h>
#include <libevdev/libevdev.h>
#include <sys/socket.h>
#include <sys/un.h>

#include "hal.h"

/* ==================== Configuration ==================== */

#define MAX_DEVICES 8
#define AGENT_SOCKET "/run/aios/agent.sock"

typedef struct {
    int ctrl;
    int alt;
    int shift;
    int super;
    int key;
    const char *action;
    const char *description;
} hotkey_t;

/* Default hotkeys */
static hotkey_t hotkeys[] = {
    {0, 0, 0, 1, KEY_SPACE,    "agent_activate", "Activate AI Agent"},
    {0, 0, 0, 1, KEY_T,        "terminal",       "Open Terminal"},
    {0, 0, 0, 1, KEY_L,        "lock",           "Lock Screen"},
    {0, 0, 0, 1, KEY_Q,        "close_window",   "Close Window"},
    {1, 1, 0, 0, KEY_T,        "terminal",       "Open Terminal"},
    {1, 1, 0, 0, KEY_DELETE,   "system_menu",    "System Menu"},
    {0, 1, 0, 0, KEY_F4,       "close_window",   "Close Window"},
    {0, 0, 0, 0, KEY_PRINT,    "screenshot",     "Take Screenshot"},
    {0, 0, 0, 0, KEY_VOLUMEUP,     "volume_up",      "Volume Up"},
    {0, 0, 0, 0, KEY_VOLUMEDOWN,   "volume_down",    "Volume Down"},
    {0, 0, 0, 0, KEY_MUTE,         "volume_mute",    "Mute"},
    {0, 0, 0, 0, KEY_BRIGHTNESSUP,   "brightness_up",   "Brightness Up"},
    {0, 0, 0, 0, KEY_BRIGHTNESSDOWN, "brightness_down", "Brightness Down"},
    {0, 0, 0, 0, 0, NULL, NULL}  /* End marker */
};

/* ==================== Globals ==================== */

static volatile int g_running = 1;
static int g_device_fds[MAX_DEVICES];
static struct libevdev *g_devices[MAX_DEVICES];
static int g_device_count = 0;

/* Modifier states */
static int g_ctrl_pressed = 0;
static int g_alt_pressed = 0;
static int g_shift_pressed = 0;
static int g_super_pressed = 0;

/* ==================== Actions ==================== */

static void execute_action(const char *action) {
    printf("[INPUT] Executing action: %s\n", action);
    
    if (strcmp(action, "agent_activate") == 0) {
        /* Send activation to agent */
        int sock = socket(AF_UNIX, SOCK_STREAM, 0);
        if (sock >= 0) {
            struct sockaddr_un addr = {0};
            addr.sun_family = AF_UNIX;
            strcpy(addr.sun_path, AGENT_SOCKET);
            
            if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
                const char *msg = "{\"cmd\":\"activate\"}";
                uint32_t len = htonl(strlen(msg));
                send(sock, &len, 4, 0);
                send(sock, msg, strlen(msg), 0);
            }
            close(sock);
        }
    }
    else if (strcmp(action, "terminal") == 0) {
        if (fork() == 0) {
            execlp("weston-terminal", "weston-terminal", NULL);
            execlp("xterm", "xterm", NULL);
            exit(1);
        }
    }
    else if (strcmp(action, "lock") == 0) {
        system("loginctl lock-session");
    }
    else if (strcmp(action, "screenshot") == 0) {
        char cmd[256];
        snprintf(cmd, sizeof(cmd), "grim /tmp/screenshot-%ld.png &", time(NULL));
        system(cmd);
    }
    else if (strcmp(action, "volume_up") == 0) {
        int vol = hal_volume_get();
        if (vol >= 0) hal_volume_set(vol + 5);
    }
    else if (strcmp(action, "volume_down") == 0) {
        int vol = hal_volume_get();
        if (vol >= 0) hal_volume_set(vol - 5);
    }
    else if (strcmp(action, "volume_mute") == 0) {
        int muted = hal_mute_get();
        hal_mute_set(!muted);
    }
    else if (strcmp(action, "brightness_up") == 0) {
        int level = hal_brightness_get();
        if (level >= 0) hal_brightness_set(level + 10);
    }
    else if (strcmp(action, "brightness_down") == 0) {
        int level = hal_brightness_get();
        if (level >= 0) hal_brightness_set(level - 10);
    }
    else if (strcmp(action, "close_window") == 0) {
        /* Would need compositor integration */
    }
}

/* ==================== Input Handling ==================== */

static void check_hotkey(int key) {
    for (int i = 0; hotkeys[i].action != NULL; i++) {
        if (hotkeys[i].key == key &&
            hotkeys[i].ctrl == g_ctrl_pressed &&
            hotkeys[i].alt == g_alt_pressed &&
            hotkeys[i].shift == g_shift_pressed &&
            hotkeys[i].super == g_super_pressed) {
            execute_action(hotkeys[i].action);
            return;
        }
    }
}

static void process_event(struct input_event *ev) {
    if (ev->type != EV_KEY) return;
    
    int pressed = (ev->value == 1);  /* 1 = press, 0 = release, 2 = repeat */
    
    /* Update modifier states */
    switch (ev->code) {
        case KEY_LEFTCTRL:
        case KEY_RIGHTCTRL:
            g_ctrl_pressed = pressed;
            break;
        case KEY_LEFTALT:
        case KEY_RIGHTALT:
            g_alt_pressed = pressed;
            break;
        case KEY_LEFTSHIFT:
        case KEY_RIGHTSHIFT:
            g_shift_pressed = pressed;
            break;
        case KEY_LEFTMETA:
        case KEY_RIGHTMETA:
            g_super_pressed = pressed;
            break;
        default:
            if (ev->value == 1) {  /* Only on key press */
                check_hotkey(ev->code);
            }
            break;
    }
}

/* ==================== Device Discovery ==================== */

static int is_keyboard(const char *path) {
    int fd = open(path, O_RDONLY | O_NONBLOCK);
    if (fd < 0) return 0;
    
    struct libevdev *dev = NULL;
    if (libevdev_new_from_fd(fd, &dev) < 0) {
        close(fd);
        return 0;
    }
    
    /* Check if it has keyboard keys */
    int is_kbd = libevdev_has_event_type(dev, EV_KEY) &&
                 libevdev_has_event_code(dev, EV_KEY, KEY_A);
    
    libevdev_free(dev);
    close(fd);
    
    return is_kbd;
}

static int discover_devices(void) {
    DIR *dir = opendir("/dev/input");
    if (!dir) return -1;
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL && g_device_count < MAX_DEVICES) {
        if (strncmp(entry->d_name, "event", 5) != 0) continue;
        
        char path[256];
        snprintf(path, sizeof(path), "/dev/input/%s", entry->d_name);
        
        if (!is_keyboard(path)) continue;
        
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;
        
        struct libevdev *dev = NULL;
        if (libevdev_new_from_fd(fd, &dev) < 0) {
            close(fd);
            continue;
        }
        
        /* Grab device for exclusive input */
        libevdev_grab(dev, LIBEVDEV_GRAB);
        
        g_device_fds[g_device_count] = fd;
        g_devices[g_device_count] = dev;
        g_device_count++;
        
        printf("[INPUT] Found keyboard: %s (%s)\n", 
            libevdev_get_name(dev), path);
    }
    
    closedir(dir);
    return g_device_count;
}

/* ==================== Main Loop ==================== */

static void signal_handler(int sig) {
    g_running = 0;
}

int main(int argc, char *argv[]) {
    printf("[INPUT] AI-OS Input Service starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    if (discover_devices() <= 0) {
        fprintf(stderr, "[INPUT] No input devices found\n");
        return 1;
    }
    
    printf("[INPUT] Monitoring %d keyboard(s)\n", g_device_count);
    
    while (g_running) {
        fd_set fds;
        FD_ZERO(&fds);
        
        int max_fd = 0;
        for (int i = 0; i < g_device_count; i++) {
            FD_SET(g_device_fds[i], &fds);
            if (g_device_fds[i] > max_fd) max_fd = g_device_fds[i];
        }
        
        struct timeval tv = {1, 0};  /* 1 second timeout */
        int ret = select(max_fd + 1, &fds, NULL, NULL, &tv);
        
        if (ret <= 0) continue;
        
        for (int i = 0; i < g_device_count; i++) {
            if (!FD_ISSET(g_device_fds[i], &fds)) continue;
            
            struct input_event ev;
            int rc = libevdev_next_event(g_devices[i], 
                LIBEVDEV_READ_FLAG_NORMAL, &ev);
            
            while (rc == LIBEVDEV_READ_STATUS_SUCCESS ||
                   rc == LIBEVDEV_READ_STATUS_SYNC) {
                process_event(&ev);
                rc = libevdev_next_event(g_devices[i],
                    LIBEVDEV_READ_FLAG_NORMAL, &ev);
            }
        }
    }
    
    /* Cleanup */
    for (int i = 0; i < g_device_count; i++) {
        libevdev_grab(g_devices[i], LIBEVDEV_UNGRAB);
        libevdev_free(g_devices[i]);
        close(g_device_fds[i]);
    }
    
    printf("[INPUT] Input service stopped\n");
    return 0;
}
