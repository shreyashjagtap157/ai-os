/**
 * AI-OS Notification Service Header
 * System and application notifications
 */

#ifndef AIOS_NOTIFY_H
#define AIOS_NOTIFY_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    NOTIFY_PRIORITY_LOW = 0,
    NOTIFY_PRIORITY_NORMAL,
    NOTIFY_PRIORITY_HIGH,
    NOTIFY_PRIORITY_URGENT
} NotifyPriority;

typedef enum {
    NOTIFY_CATEGORY_SYSTEM = 0,
    NOTIFY_CATEGORY_MESSAGE,
    NOTIFY_CATEGORY_CALL,
    NOTIFY_CATEGORY_EMAIL,
    NOTIFY_CATEGORY_REMINDER,
    NOTIFY_CATEGORY_SOCIAL,
    NOTIFY_CATEGORY_PROMO,
    NOTIFY_CATEGORY_OTHER
} NotifyCategory;

typedef struct {
    uint32_t id;
    char app_id[64];
    char title[128];
    char body[512];
    char icon_path[256];
    char action_url[256];
    NotifyPriority priority;
    NotifyCategory category;
    uint64_t timestamp;
    bool is_persistent;
    bool is_silent;
    int timeout_ms;  // 0 for no timeout
} Notification;

typedef struct {
    char app_id[64];
    bool enabled;
    bool show_on_lockscreen;
    bool show_badge;
    bool allow_sound;
    bool allow_vibration;
    NotifyPriority min_priority;
} NotifySettings;

typedef void (*NotifyCallback)(const Notification *notification);
typedef void (*NotifyActionCallback)(uint32_t notification_id, const char *action);

// ==================== Initialization ====================

/**
 * Initialize notification service
 * @return 0 on success
 */
int notify_init(void);

/**
 * Shutdown notification service
 */
void notify_shutdown(void);

// ==================== Sending Notifications ====================

/**
 * Show a notification
 * @param notification Notification to show
 * @return Notification ID, or negative on error
 */
int notify_show(const Notification *notification);

/**
 * Show a simple notification
 * @param title Notification title
 * @param body Notification body
 * @param priority Priority level
 * @return Notification ID
 */
int notify_simple(const char *title, const char *body, NotifyPriority priority);

/**
 * Update an existing notification
 * @param id Notification ID
 * @param notification Updated notification
 * @return 0 on success
 */
int notify_update(uint32_t id, const Notification *notification);

/**
 * Dismiss a notification
 * @param id Notification ID
 * @return 0 on success
 */
int notify_dismiss(uint32_t id);

/**
 * Dismiss all notifications
 */
void notify_dismiss_all(void);

/**
 * Dismiss all notifications from an app
 * @param app_id Application ID
 */
void notify_dismiss_app(const char *app_id);

// ==================== Notification History ====================

/**
 * Get notification count
 * @return Number of notifications
 */
int notify_get_count(void);

/**
 * Get notification by ID
 * @param id Notification ID
 * @param notification Pointer to notification structure
 * @return 0 on success
 */
int notify_get(uint32_t id, Notification *notification);

/**
 * Get all notifications
 * @param notifications Array to fill
 * @param max_count Maximum notifications to return
 * @return Number of notifications returned
 */
int notify_get_all(Notification *notifications, int max_count);

// ==================== Settings ====================

/**
 * Get notification settings for an app
 * @param app_id Application ID
 * @param settings Pointer to settings structure
 * @return 0 on success
 */
int notify_get_settings(const char *app_id, NotifySettings *settings);

/**
 * Update notification settings for an app
 * @param settings Updated settings
 * @return 0 on success
 */
int notify_set_settings(const NotifySettings *settings);

/**
 * Enable/disable Do Not Disturb mode
 * @param enable True to enable
 */
void notify_set_dnd(bool enable);

/**
 * Check if DND is active
 */
bool notify_is_dnd(void);

// ==================== Events ====================

/**
 * Register notification callback
 */
void notify_register_callback(NotifyCallback callback);

/**
 * Register action callback
 */
void notify_register_action_callback(NotifyActionCallback callback);

#ifdef __cplusplus
}
#endif

#endif // AIOS_NOTIFY_H
