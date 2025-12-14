/**
 * AI-OS Hardware Abstraction Layer (HAL) Implementation
 * Direct hardware control via sysfs and system calls.
 * 
 * Compile: gcc -o libaios-hal.so -shared -fPIC hal.c -lasound
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <sys/statvfs.h>
#include <sys/utsname.h>
#include <sys/reboot.h>
#include <linux/reboot.h>
#include <errno.h>

#include "hal.h"

/* ==================== Helper Functions ==================== */

static int read_sysfs_int(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    
    int value;
    if (fscanf(f, "%d", &value) != 1) {
        fclose(f);
        return -1;
    }
    fclose(f);
    return value;
}

static int write_sysfs_int(const char *path, int value) {
    FILE *f = fopen(path, "w");
    if (!f) return -1;
    
    fprintf(f, "%d", value);
    fclose(f);
    return 0;
}

static int read_sysfs_str(const char *path, char *buf, size_t len) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    
    if (!fgets(buf, len, f)) {
        fclose(f);
        return -1;
    }
    
    /* Remove trailing newline */
    size_t l = strlen(buf);
    if (l > 0 && buf[l-1] == '\n') buf[l-1] = '\0';
    
    fclose(f);
    return 0;
}

static char *find_backlight_device(void) {
    static char path[256];
    DIR *dir = opendir("/sys/class/backlight");
    if (!dir) return NULL;
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] != '.') {
            snprintf(path, sizeof(path), "/sys/class/backlight/%s", entry->d_name);
            closedir(dir);
            return path;
        }
    }
    closedir(dir);
    return NULL;
}

static char *find_battery_device(void) {
    static char path[256];
    DIR *dir = opendir("/sys/class/power_supply");
    if (!dir) return NULL;
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "BAT", 3) == 0) {
            snprintf(path, sizeof(path), "/sys/class/power_supply/%s", entry->d_name);
            closedir(dir);
            return path;
        }
    }
    closedir(dir);
    return NULL;
}

/* ==================== Display Implementation ==================== */

int hal_brightness_get(void) {
    char *device = find_backlight_device();
    if (!device) return -1;
    
    char brightness_path[512], max_path[512];
    snprintf(brightness_path, sizeof(brightness_path), "%s/brightness", device);
    snprintf(max_path, sizeof(max_path), "%s/max_brightness", device);
    
    int current = read_sysfs_int(brightness_path);
    int max = read_sysfs_int(max_path);
    
    if (current < 0 || max <= 0) return -1;
    
    return (current * 100) / max;
}

int hal_brightness_set(int level) {
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    
    char *device = find_backlight_device();
    if (!device) return -1;
    
    char brightness_path[512], max_path[512];
    snprintf(brightness_path, sizeof(brightness_path), "%s/brightness", device);
    snprintf(max_path, sizeof(max_path), "%s/max_brightness", device);
    
    int max = read_sysfs_int(max_path);
    if (max <= 0) return -1;
    
    int value = (max * level) / 100;
    return write_sysfs_int(brightness_path, value);
}

/* ==================== Audio Implementation ==================== */

int hal_volume_get(void) {
    /* Use amixer to get volume */
    FILE *fp = popen("amixer get Master 2>/dev/null | grep -o '[0-9]*%' | head -1 | tr -d '%'", "r");
    if (!fp) return -1;
    
    int volume = -1;
    fscanf(fp, "%d", &volume);
    pclose(fp);
    
    return volume;
}

int hal_volume_set(int level) {
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    
    char cmd[128];
    snprintf(cmd, sizeof(cmd), "amixer set Master %d%% >/dev/null 2>&1", level);
    return system(cmd) == 0 ? 0 : -1;
}

int hal_mute_get(void) {
    FILE *fp = popen("amixer get Master 2>/dev/null | grep -o '\\[off\\]'", "r");
    if (!fp) return -1;
    
    char buf[16];
    int muted = (fgets(buf, sizeof(buf), fp) != NULL);
    pclose(fp);
    
    return muted ? 1 : 0;
}

int hal_mute_set(bool mute) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "amixer set Master %s >/dev/null 2>&1", mute ? "mute" : "unmute");
    return system(cmd) == 0 ? 0 : -1;
}

/* ==================== Power Implementation ==================== */

int hal_battery_get(battery_info_t *info) {
    if (!info) return -1;
    memset(info, 0, sizeof(*info));
    
    char *device = find_battery_device();
    if (!device) {
        info->present = false;
        return 0;
    }
    
    char path[512];
    
    /* Check if present */
    snprintf(path, sizeof(path), "%s/present", device);
    info->present = (read_sysfs_int(path) == 1);
    if (!info->present) return 0;
    
    /* Get capacity */
    snprintf(path, sizeof(path), "%s/capacity", device);
    info->level = read_sysfs_int(path);
    if (info->level < 0) info->level = 0;
    
    /* Get status */
    snprintf(path, sizeof(path), "%s/status", device);
    if (read_sysfs_str(path, info->status, sizeof(info->status)) < 0) {
        strcpy(info->status, "Unknown");
    }
    
    /* Calculate time estimates */
    snprintf(path, sizeof(path), "%s/energy_now", device);
    int energy_now = read_sysfs_int(path);
    snprintf(path, sizeof(path), "%s/energy_full", device);
    int energy_full = read_sysfs_int(path);
    snprintf(path, sizeof(path), "%s/power_now", device);
    int power_now = read_sysfs_int(path);
    
    if (power_now > 0) {
        if (strcmp(info->status, "Discharging") == 0) {
            info->time_to_empty = (energy_now * 60) / power_now;
        } else if (strcmp(info->status, "Charging") == 0) {
            info->time_to_full = ((energy_full - energy_now) * 60) / power_now;
        }
    }
    
    return 0;
}

int hal_on_ac_power(void) {
    DIR *dir = opendir("/sys/class/power_supply");
    if (!dir) return -1;
    
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "AC", 2) == 0 || 
            strncmp(entry->d_name, "ADP", 3) == 0) {
            char path[512];
            snprintf(path, sizeof(path), "/sys/class/power_supply/%s/online", entry->d_name);
            int online = read_sysfs_int(path);
            if (online == 1) {
                closedir(dir);
                return 1;
            }
        }
    }
    closedir(dir);
    return 0;
}

int hal_suspend(void) {
    return system("systemctl suspend") == 0 ? 0 : -1;
}

int hal_hibernate(void) {
    return system("systemctl hibernate") == 0 ? 0 : -1;
}

int hal_poweroff(void) {
    sync();
    return reboot(LINUX_REBOOT_CMD_POWER_OFF);
}

int hal_reboot(void) {
    sync();
    return reboot(LINUX_REBOOT_CMD_RESTART);
}

/* ==================== Network Implementation ==================== */

int hal_wifi_enabled(void) {
    FILE *fp = popen("nmcli radio wifi 2>/dev/null", "r");
    if (!fp) return -1;
    
    char buf[32];
    if (fgets(buf, sizeof(buf), fp) == NULL) {
        pclose(fp);
        return -1;
    }
    pclose(fp);
    
    return (strstr(buf, "enabled") != NULL) ? 1 : 0;
}

int hal_wifi_set(bool enabled) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "nmcli radio wifi %s >/dev/null 2>&1", enabled ? "on" : "off");
    return system(cmd) == 0 ? 0 : -1;
}

int hal_bluetooth_enabled(void) {
    FILE *fp = popen("bluetoothctl show 2>/dev/null | grep 'Powered: yes'", "r");
    if (!fp) return -1;
    
    char buf[64];
    int enabled = (fgets(buf, sizeof(buf), fp) != NULL);
    pclose(fp);
    
    return enabled ? 1 : 0;
}

int hal_bluetooth_set(bool enabled) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "bluetoothctl power %s >/dev/null 2>&1", enabled ? "on" : "off");
    return system(cmd) == 0 ? 0 : -1;
}

/* ==================== System Info Implementation ==================== */

int hal_system_info(system_info_t *info) {
    if (!info) return -1;
    memset(info, 0, sizeof(*info));
    
    /* Hostname */
    gethostname(info->hostname, sizeof(info->hostname));
    
    /* Kernel */
    struct utsname uts;
    if (uname(&uts) == 0) {
        snprintf(info->kernel, sizeof(info->kernel), "%s %s", uts.sysname, uts.release);
    }
    
    /* System info */
    struct sysinfo si;
    if (sysinfo(&si) == 0) {
        info->memory_total_kb = si.totalram / 1024;
        info->memory_free_kb = si.freeram / 1024;
        info->uptime_seconds = si.uptime;
        
        /* CPU load (1 minute average) */
        info->cpu_load = si.loads[0] / 65536.0;
    }
    
    /* Disk info */
    struct statvfs vfs;
    if (statvfs("/", &vfs) == 0) {
        info->disk_total_kb = (vfs.f_blocks * vfs.f_frsize) / 1024;
        info->disk_free_kb = (vfs.f_bavail * vfs.f_frsize) / 1024;
    }
    
    return 0;
}

/* ==================== Applications Implementation ==================== */

int hal_app_launch(const char *name) {
    if (!name) return -1;
    
    char cmd[512];
    
    /* Try direct command first */
    snprintf(cmd, sizeof(cmd), "%s >/dev/null 2>&1 &", name);
    if (system(cmd) == 0) return 0;
    
    /* Try gtk-launch */
    snprintf(cmd, sizeof(cmd), "gtk-launch %s >/dev/null 2>&1 &", name);
    if (system(cmd) == 0) return 0;
    
    /* Search in applications directory */
    DIR *dir = opendir("/usr/share/applications");
    if (dir) {
        struct dirent *entry;
        while ((entry = readdir(dir)) != NULL) {
            if (strstr(entry->d_name, name) && strstr(entry->d_name, ".desktop")) {
                snprintf(cmd, sizeof(cmd), "gtk-launch %s >/dev/null 2>&1 &", entry->d_name);
                closedir(dir);
                return system(cmd) == 0 ? 0 : -1;
            }
        }
        closedir(dir);
    }
    
    return -1;
}

int hal_app_list(char names[][256], int max_count) {
    DIR *dir = opendir("/usr/share/applications");
    if (!dir) return 0;
    
    int count = 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL && count < max_count) {
        if (strstr(entry->d_name, ".desktop")) {
            /* Remove .desktop extension */
            strncpy(names[count], entry->d_name, 255);
            char *ext = strstr(names[count], ".desktop");
            if (ext) *ext = '\0';
            count++;
        }
    }
    closedir(dir);
    
    return count;
}
