/**
 * AI-OS Hardware Abstraction Layer (HAL)
 * Direct hardware control without interpreter overhead.
 * 
 * Compile: gcc -o libaios-hal.so -shared -fPIC hal.c
 */

#ifndef AIOS_HAL_H
#define AIOS_HAL_H

#include <stdint.h>
#include <stdbool.h>

/* ==================== Display ==================== */

/**
 * Get current screen brightness (0-100)
 * Returns -1 on error
 */
int hal_brightness_get(void);

/**
 * Set screen brightness (0-100)
 * Returns 0 on success, -1 on error
 */
int hal_brightness_set(int level);

/* ==================== Audio ==================== */

/**
 * Get current volume (0-100)
 * Returns -1 on error
 */
int hal_volume_get(void);

/**
 * Set volume (0-100)
 * Returns 0 on success, -1 on error
 */
int hal_volume_set(int level);

/**
 * Get mute state
 * Returns 1 if muted, 0 if not, -1 on error
 */
int hal_mute_get(void);

/**
 * Set mute state
 * Returns 0 on success, -1 on error
 */
int hal_mute_set(bool mute);

/* ==================== Power ==================== */

typedef struct {
    bool present;
    int level;          /* 0-100 */
    char status[32];    /* Charging, Discharging, Full */
    int time_to_empty;  /* minutes */
    int time_to_full;   /* minutes */
} battery_info_t;

/**
 * Get battery information
 * Returns 0 on success, -1 on error
 */
int hal_battery_get(battery_info_t *info);

/**
 * Check if on AC power
 * Returns 1 if on AC, 0 if on battery, -1 on error
 */
int hal_on_ac_power(void);

/**
 * Suspend to RAM
 */
int hal_suspend(void);

/**
 * Hibernate to disk
 */
int hal_hibernate(void);

/**
 * Power off
 */
int hal_poweroff(void);

/**
 * Reboot
 */
int hal_reboot(void);

/* ==================== Network ==================== */

/**
 * Check if WiFi is enabled
 * Returns 1 if enabled, 0 if disabled, -1 on error
 */
int hal_wifi_enabled(void);

/**
 * Enable/disable WiFi
 */
int hal_wifi_set(bool enabled);

/**
 * Check if Bluetooth is enabled
 */
int hal_bluetooth_enabled(void);

/**
 * Enable/disable Bluetooth
 */
int hal_bluetooth_set(bool enabled);

/* ==================== System Info ==================== */

typedef struct {
    char hostname[64];
    char kernel[64];
    double cpu_load;
    uint64_t memory_total_kb;
    uint64_t memory_free_kb;
    uint64_t disk_total_kb;
    uint64_t disk_free_kb;
    uint64_t uptime_seconds;
} system_info_t;

/**
 * Get system information
 */
int hal_system_info(system_info_t *info);

/* ==================== Applications ==================== */

/**
 * Launch an application by name
 */
int hal_app_launch(const char *name);

/**
 * List installed applications
 * Returns number of apps, fills names array
 */
int hal_app_list(char names[][256], int max_count);

#endif /* AIOS_HAL_H */
