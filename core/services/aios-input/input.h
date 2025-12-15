/**
 * AI-OS Input Service Header
 * Keyboard, mouse, touch, and gesture input handling
 */

#ifndef AIOS_INPUT_H
#define AIOS_INPUT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    INPUT_TYPE_KEYBOARD = 0,
    INPUT_TYPE_MOUSE,
    INPUT_TYPE_TOUCH,
    INPUT_TYPE_GAMEPAD,
    INPUT_TYPE_UNKNOWN
} InputDeviceType;

typedef enum {
    KEY_STATE_RELEASED = 0,
    KEY_STATE_PRESSED,
    KEY_STATE_REPEAT
} KeyState;

typedef enum {
    MOUSE_BUTTON_LEFT = 0,
    MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_MIDDLE,
    MOUSE_BUTTON_SIDE,
    MOUSE_BUTTON_EXTRA
} MouseButton;

typedef struct {
    int x;
    int y;
    int pressure;  // 0-1000 for touch
    int slot;      // For multi-touch
} TouchPoint;

typedef struct {
    char name[64];
    char path[128];
    InputDeviceType type;
    bool is_active;
    int vendor_id;
    int product_id;
} InputDevice;

typedef struct {
    uint32_t keycode;
    KeyState state;
    uint32_t modifiers;  // Shift, Ctrl, Alt flags
    uint64_t timestamp;
} KeyEvent;

typedef struct {
    int x;
    int y;
    int dx;  // Delta x
    int dy;  // Delta y
    MouseButton button;
    KeyState state;
    int scroll_x;
    int scroll_y;
    uint64_t timestamp;
} MouseEvent;

typedef struct {
    TouchPoint points[10];
    int num_points;
    uint64_t timestamp;
} TouchEvent;

typedef void (*KeyEventCallback)(const KeyEvent *event);
typedef void (*MouseEventCallback)(const MouseEvent *event);
typedef void (*TouchEventCallback)(const TouchEvent *event);

// ==================== Initialization ====================

/**
 * Initialize input subsystem
 * @return 0 on success
 */
int input_init(void);

/**
 * Shutdown input subsystem
 */
void input_shutdown(void);

// ==================== Device Management ====================

/**
 * Get number of input devices
 */
int input_get_device_count(void);

/**
 * Get input device info
 * @param index Device index
 * @param device Pointer to device info structure
 * @return 0 on success
 */
int input_get_device(int index, InputDevice *device);

/**
 * Enable/disable input device
 * @param path Device path
 * @param enable True to enable
 * @return 0 on success
 */
int input_set_device_enabled(const char *path, bool enable);

// ==================== Event Callbacks ====================

/**
 * Register keyboard event callback
 */
void input_register_key_callback(KeyEventCallback callback);

/**
 * Register mouse event callback
 */
void input_register_mouse_callback(MouseEventCallback callback);

/**
 * Register touch event callback
 */
void input_register_touch_callback(TouchEventCallback callback);

// ==================== Input Injection ====================

/**
 * Inject a key event (for automation)
 * @param keycode Key code to inject
 * @param state Key state
 * @return 0 on success
 */
int input_inject_key(uint32_t keycode, KeyState state);

/**
 * Inject mouse movement
 * @param x X coordinate
 * @param y Y coordinate
 * @return 0 on success
 */
int input_inject_mouse_move(int x, int y);

/**
 * Inject mouse click
 * @param button Button to click
 * @param state Button state
 * @return 0 on success
 */
int input_inject_mouse_click(MouseButton button, KeyState state);

/**
 * Inject touch event
 * @param x X coordinate
 * @param y Y coordinate
 * @param pressure Touch pressure
 * @return 0 on success
 */
int input_inject_touch(int x, int y, int pressure);

// ==================== Configuration ====================

/**
 * Set keyboard repeat rate
 * @param delay_ms Delay before repeat starts
 * @param rate_ms Time between repeats
 */
void input_set_keyboard_repeat(int delay_ms, int rate_ms);

/**
 * Set mouse sensitivity
 * @param sensitivity Sensitivity multiplier (0.1 - 10.0)
 */
void input_set_mouse_sensitivity(float sensitivity);

/**
 * Swap mouse buttons (left-handed mode)
 */
void input_set_left_handed(bool enabled);

#ifdef __cplusplus
}
#endif

#endif // AIOS_INPUT_H
