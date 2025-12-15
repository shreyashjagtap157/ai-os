/**
 * AI-OS Display Service Header
 * Wayland compositor and display management
 */

#ifndef AIOS_DISPLAY_H
#define AIOS_DISPLAY_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    DISPLAY_STATE_OFF = 0,
    DISPLAY_STATE_ON,
    DISPLAY_STATE_DIM,
    DISPLAY_STATE_STANDBY
} DisplayState;

typedef enum {
    ORIENTATION_LANDSCAPE = 0,
    ORIENTATION_PORTRAIT,
    ORIENTATION_LANDSCAPE_FLIPPED,
    ORIENTATION_PORTRAIT_FLIPPED
} DisplayOrientation;

typedef struct {
    int width;
    int height;
    int refresh_rate;
    int bits_per_pixel;
} DisplayMode;

typedef struct {
    char name[64];
    char connector[32];
    DisplayMode current_mode;
    DisplayMode *available_modes;
    int num_modes;
    bool is_primary;
    bool is_connected;
    DisplayOrientation orientation;
    int brightness;  // 0-100
} DisplayInfo;

typedef void (*DisplayEventCallback)(int event_type, void *data);

// ==================== Initialization ====================

/**
 * Initialize display subsystem
 * @return 0 on success, negative error code on failure
 */
int display_init(void);

/**
 * Shutdown display subsystem
 */
void display_shutdown(void);

// ==================== Display Control ====================

/**
 * Get number of connected displays
 */
int display_get_count(void);

/**
 * Get display information
 * @param index Display index
 * @param info Pointer to DisplayInfo structure
 * @return 0 on success
 */
int display_get_info(int index, DisplayInfo *info);

/**
 * Set display mode
 * @param index Display index
 * @param mode Mode to set
 * @return 0 on success
 */
int display_set_mode(int index, const DisplayMode *mode);

/**
 * Set display brightness
 * @param index Display index
 * @param brightness Brightness level (0-100)
 * @return 0 on success
 */
int display_set_brightness(int index, int brightness);

/**
 * Get current brightness
 * @param index Display index
 * @return Brightness level (0-100), negative on error
 */
int display_get_brightness(int index);

/**
 * Set display state (on/off/dim)
 * @param index Display index
 * @param state Target state
 * @return 0 on success
 */
int display_set_state(int index, DisplayState state);

/**
 * Set display orientation
 * @param index Display index
 * @param orientation Target orientation
 * @return 0 on success
 */
int display_set_orientation(int index, DisplayOrientation orientation);

// ==================== Compositor ====================

/**
 * Start the Wayland compositor
 * @return 0 on success
 */
int compositor_start(void);

/**
 * Stop the compositor
 */
void compositor_stop(void);

/**
 * Check if compositor is running
 * @return true if running
 */
bool compositor_is_running(void);

// ==================== Event Handling ====================

/**
 * Register event callback
 * @param callback Function to call on display events
 */
void display_register_callback(DisplayEventCallback callback);

// ==================== Utility ====================

/**
 * Take a screenshot
 * @param filename Output filename
 * @return 0 on success
 */
int display_screenshot(const char *filename);

#ifdef __cplusplus
}
#endif

#endif // AIOS_DISPLAY_H
