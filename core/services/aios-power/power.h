/**
 * AI-OS Power Service Header
 * Power management and battery monitoring
 */

#ifndef AIOS_POWER_H
#define AIOS_POWER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    POWER_SOURCE_BATTERY = 0,
    POWER_SOURCE_AC,
    POWER_SOURCE_USB,
    POWER_SOURCE_WIRELESS,
    POWER_SOURCE_UNKNOWN
} PowerSource;

typedef enum {
    BATTERY_STATUS_UNKNOWN = 0,
    BATTERY_STATUS_CHARGING,
    BATTERY_STATUS_DISCHARGING,
    BATTERY_STATUS_FULL,
    BATTERY_STATUS_NOT_CHARGING,
    BATTERY_STATUS_CRITICAL
} BatteryStatus;

typedef enum {
    POWER_PROFILE_PERFORMANCE = 0,
    POWER_PROFILE_BALANCED,
    POWER_PROFILE_POWER_SAVER,
    POWER_PROFILE_ULTRA_SAVER
} PowerProfile;

typedef enum {
    POWER_ACTION_SUSPEND = 0,
    POWER_ACTION_HIBERNATE,
    POWER_ACTION_SHUTDOWN,
    POWER_ACTION_REBOOT
} PowerAction;

typedef struct {
    bool present;
    int capacity;           // 0-100 percent
    int voltage_mv;         // Voltage in millivolts
    int current_ma;         // Current in milliamps (neg = discharging)
    int temperature_c;      // Temperature in Celsius * 10
    int cycle_count;
    int design_capacity_mah;
    int full_capacity_mah;
    BatteryStatus status;
    int time_to_empty_min;  // Minutes until empty (-1 if charging)
    int time_to_full_min;   // Minutes until full (-1 if discharging)
    char technology[32];    // "Li-ion", "Li-poly", etc.
    char health[32];        // "Good", "Degraded", etc.
} BatteryInfo;

typedef struct {
    PowerSource source;
    PowerProfile profile;
    bool low_power_mode;
    int screen_timeout_sec;
    int sleep_timeout_sec;
    bool auto_brightness;
    int cpu_governor;  // 0=powersave, 1=ondemand, 2=performance
} PowerSettings;

typedef void (*PowerEventCallback)(int event_type, void *data);
typedef void (*BatteryCallback)(const BatteryInfo *info);

// ==================== Initialization ====================

/**
 * Initialize power service
 * @return 0 on success
 */
int power_init(void);

/**
 * Shutdown power service
 */
void power_shutdown(void);

// ==================== Battery ====================

/**
 * Get battery information
 * @param info Pointer to battery info structure
 * @return 0 on success
 */
int power_get_battery(BatteryInfo *info);

/**
 * Check if on battery power
 */
bool power_is_on_battery(void);

/**
 * Get battery percentage
 * @return 0-100, negative on error
 */
int power_get_battery_percent(void);

/**
 * Check if battery is charging
 */
bool power_is_charging(void);

// ==================== Power Profile ====================

/**
 * Get current power profile
 */
PowerProfile power_get_profile(void);

/**
 * Set power profile
 * @param profile Profile to set
 * @return 0 on success
 */
int power_set_profile(PowerProfile profile);

/**
 * Enable/disable low power mode
 * @param enable True to enable
 */
void power_set_low_power_mode(bool enable);

/**
 * Check if low power mode is active
 */
bool power_is_low_power_mode(void);

// ==================== Power Actions ====================

/**
 * Request system suspend
 * @return 0 on success
 */
int power_suspend(void);

/**
 * Request system hibernate
 * @return 0 on success
 */
int power_hibernate(void);

/**
 * Request system shutdown
 * @param delay_sec Delay in seconds (0 for immediate)
 * @return 0 on success
 */
int power_shutdown_system(int delay_sec);

/**
 * Request system reboot
 * @param delay_sec Delay in seconds (0 for immediate)
 * @return 0 on success
 */
int power_reboot(int delay_sec);

/**
 * Cancel pending power action
 */
void power_cancel_action(void);

// ==================== Screen Power ====================

/**
 * Turn screen on
 */
void power_screen_on(void);

/**
 * Turn screen off
 */
void power_screen_off(void);

/**
 * Keep screen on (prevent timeout)
 * @param keep True to keep on
 */
void power_keep_screen_on(bool keep);

// ==================== Settings ====================

/**
 * Get power settings
 * @param settings Pointer to settings structure
 * @return 0 on success
 */
int power_get_settings(PowerSettings *settings);

/**
 * Update power settings
 * @param settings New settings
 * @return 0 on success
 */
int power_set_settings(const PowerSettings *settings);

// ==================== Events ====================

/**
 * Register power event callback
 */
void power_register_callback(PowerEventCallback callback);

/**
 * Register battery change callback
 */
void power_register_battery_callback(BatteryCallback callback);

#ifdef __cplusplus
}
#endif

#endif // AIOS_POWER_H
