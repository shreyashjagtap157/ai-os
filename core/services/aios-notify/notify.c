/**
 * AI-OS Notification Daemon
 * Desktop notification service in C.
 * 
 * Compile: gcc -o aios-notify notify.c -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>
#include <time.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCKET_PATH "/run/aios/notify.sock"
#define MAX_NOTIFICATIONS 100
#define MAX_SUMMARY_LEN 256
#define MAX_BODY_LEN 1024

/* ==================== Types ==================== */

typedef enum {
    URGENCY_LOW = 0,
    URGENCY_NORMAL = 1,
    URGENCY_CRITICAL = 2
} urgency_t;

typedef struct {
    int id;
    char app_name[64];
    char summary[MAX_SUMMARY_LEN];
    char body[MAX_BODY_LEN];
    urgency_t urgency;
    int timeout;        /* ms, -1 for persistent */
    time_t timestamp;
    int read;
} notification_t;

/* ==================== Globals ==================== */

static volatile int g_running = 1;
static int g_server_fd = -1;
static notification_t g_notifications[MAX_NOTIFICATIONS];
static int g_notification_count = 0;
static int g_next_id = 1;
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;

/* ==================== Notification Functions ==================== */

static int create_notification(const char *app, const char *summary, 
                              const char *body, urgency_t urgency, int timeout) {
    pthread_mutex_lock(&g_lock);
    
    int id = g_next_id++;
    
    /* Find slot */
    int slot = -1;
    for (int i = 0; i < MAX_NOTIFICATIONS; i++) {
        if (g_notifications[i].id == 0) {
            slot = i;
            break;
        }
    }
    
    if (slot < 0) {
        /* Remove oldest */
        memmove(&g_notifications[0], &g_notifications[1], 
                sizeof(notification_t) * (MAX_NOTIFICATIONS - 1));
        slot = MAX_NOTIFICATIONS - 1;
    }
    
    notification_t *n = &g_notifications[slot];
    n->id = id;
    strncpy(n->app_name, app ? app : "AI-OS", sizeof(n->app_name) - 1);
    strncpy(n->summary, summary ? summary : "", sizeof(n->summary) - 1);
    strncpy(n->body, body ? body : "", sizeof(n->body) - 1);
    n->urgency = urgency;
    n->timeout = timeout;
    n->timestamp = time(NULL);
    n->read = 0;
    
    g_notification_count++;
    
    pthread_mutex_unlock(&g_lock);
    
    /* Display notification */
    const char *urg_str = urgency == URGENCY_CRITICAL ? "critical" :
                          urgency == URGENCY_LOW ? "low" : "normal";
    
    char cmd[2048];
    snprintf(cmd, sizeof(cmd), "notify-send -u %s", urg_str);
    
    if (timeout > 0) {
        char timeout_str[32];
        snprintf(timeout_str, sizeof(timeout_str), " -t %d", timeout);
        strcat(cmd, timeout_str);
    }
    
    strcat(cmd, " \"");
    strcat(cmd, summary);
    strcat(cmd, "\"");
    
    if (body && body[0]) {
        strcat(cmd, " \"");
        strcat(cmd, body);
        strcat(cmd, "\"");
    }
    
    strcat(cmd, " &");
    system(cmd);
    
    printf("[NOTIFY] %d: %s\n", id, summary);
    
    return id;
}

static void close_notification(int id) {
    pthread_mutex_lock(&g_lock);
    
    for (int i = 0; i < MAX_NOTIFICATIONS; i++) {
        if (g_notifications[i].id == id) {
            g_notifications[i].id = 0;
            g_notification_count--;
            break;
        }
    }
    
    pthread_mutex_unlock(&g_lock);
}

/* ==================== IPC Server ==================== */

static void handle_request(int client_fd, const char *msg, size_t len) {
    char response[4096] = "{\"status\":\"ok\"}";
    
    /* Parse command */
    if (strstr(msg, "\"cmd\":\"notify\"")) {
        char summary[256] = "";
        char body[1024] = "";
        char app[64] = "AI-OS";
        urgency_t urgency = URGENCY_NORMAL;
        int timeout = 5000;
        
        /* Extract fields (simple parsing) */
        char *p;
        if ((p = strstr(msg, "\"summary\":\""))) {
            sscanf(p, "\"summary\":\"%255[^\"]\"", summary);
        }
        if ((p = strstr(msg, "\"body\":\""))) {
            sscanf(p, "\"body\":\"%1023[^\"]\"", body);
        }
        if ((p = strstr(msg, "\"app_name\":\""))) {
            sscanf(p, "\"app_name\":\"%63[^\"]\"", app);
        }
        if (strstr(msg, "\"urgency\":\"critical\"")) {
            urgency = URGENCY_CRITICAL;
        } else if (strstr(msg, "\"urgency\":\"low\"")) {
            urgency = URGENCY_LOW;
        }
        if ((p = strstr(msg, "\"timeout\":"))) {
            sscanf(p, "\"timeout\":%d", &timeout);
        }
        
        int id = create_notification(app, summary, body, urgency, timeout);
        snprintf(response, sizeof(response), "{\"status\":\"ok\",\"id\":%d}", id);
    }
    else if (strstr(msg, "\"cmd\":\"close\"")) {
        int id = 0;
        char *p = strstr(msg, "\"id\":");
        if (p) sscanf(p, "\"id\":%d", &id);
        close_notification(id);
    }
    else if (strstr(msg, "\"cmd\":\"list\"")) {
        pthread_mutex_lock(&g_lock);
        
        char *ptr = response;
        ptr += sprintf(ptr, "{\"status\":\"ok\",\"notifications\":[");
        
        int first = 1;
        for (int i = 0; i < MAX_NOTIFICATIONS; i++) {
            if (g_notifications[i].id == 0) continue;
            
            notification_t *n = &g_notifications[i];
            if (!first) ptr += sprintf(ptr, ",");
            first = 0;
            
            ptr += sprintf(ptr, 
                "{\"id\":%d,\"app\":\"%s\",\"summary\":\"%s\",\"read\":%s}",
                n->id, n->app_name, n->summary, n->read ? "true" : "false");
        }
        
        ptr += sprintf(ptr, "]}");
        
        pthread_mutex_unlock(&g_lock);
    }
    else if (strstr(msg, "\"cmd\":\"clear\"")) {
        pthread_mutex_lock(&g_lock);
        memset(g_notifications, 0, sizeof(g_notifications));
        g_notification_count = 0;
        pthread_mutex_unlock(&g_lock);
    }
    
    /* Send response */
    uint32_t resp_len = htonl(strlen(response));
    send(client_fd, &resp_len, 4, 0);
    send(client_fd, response, strlen(response), 0);
}

static void *client_handler(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);
    
    while (1) {
        uint32_t length;
        if (recv(client_fd, &length, 4, 0) != 4) break;
        length = ntohl(length);
        
        if (length > 8192) break;
        
        char *msg = malloc(length + 1);
        if (!msg) break;
        
        if (recv(client_fd, msg, length, 0) != length) {
            free(msg);
            break;
        }
        msg[length] = '\0';
        
        handle_request(client_fd, msg, length);
        free(msg);
    }
    
    close(client_fd);
    return NULL;
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
    
    printf("[NOTIFY] Listening on %s\n", SOCKET_PATH);
    
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

/* ==================== Main ==================== */

static void signal_handler(int sig) {
    g_running = 0;
}

int main(int argc, char *argv[]) {
    printf("[NOTIFY] AI-OS Notification Daemon starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    mkdir("/run/aios", 0755);
    
    run_server();
    
    if (g_server_fd >= 0) {
        close(g_server_fd);
        unlink(SOCKET_PATH);
    }
    
    printf("[NOTIFY] Notification daemon stopped\n");
    return 0;
}
