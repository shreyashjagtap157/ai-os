/**
 * AI-OS Network Manager
 * WiFi, Bluetooth, and network management in C.
 * 
 * Compile: gcc -o aios-network network.c -lpthread
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>
#include <errno.h>
#include <dirent.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <arpa/inet.h>

#define SOCKET_PATH "/run/aios/network.sock"

/* ==================== Types ==================== */

typedef struct {
    char name[32];
    char type[16];      /* wifi, ethernet, loopback */
    char state[16];     /* up, down */
    char mac[32];
    char ip[32];
} interface_t;

typedef struct {
    char ssid[64];
    int signal;
    char security[32];
    int connected;
} wifi_network_t;

/* ==================== Globals ==================== */

static volatile int g_running = 1;
static int g_server_fd = -1;

/* ==================== Interface Functions ==================== */

static int get_interfaces(interface_t *ifaces, int max_count) {
    DIR *dir = opendir("/sys/class/net");
    if (!dir) return 0;
    
    int count = 0;
    struct dirent *entry;
    
    while ((entry = readdir(dir)) && count < max_count) {
        if (entry->d_name[0] == '.') continue;
        
        interface_t *iface = &ifaces[count];
        strncpy(iface->name, entry->d_name, sizeof(iface->name) - 1);
        
        /* Get type */
        char path[256];
        snprintf(path, sizeof(path), "/sys/class/net/%s/wireless", entry->d_name);
        if (access(path, F_OK) == 0) {
            strcpy(iface->type, "wifi");
        } else if (strcmp(entry->d_name, "lo") == 0) {
            strcpy(iface->type, "loopback");
        } else if (strncmp(entry->d_name, "eth", 3) == 0 || 
                   strncmp(entry->d_name, "en", 2) == 0) {
            strcpy(iface->type, "ethernet");
        } else {
            strcpy(iface->type, "unknown");
        }
        
        /* Get state */
        snprintf(path, sizeof(path), "/sys/class/net/%s/operstate", entry->d_name);
        FILE *f = fopen(path, "r");
        if (f) {
            fgets(iface->state, sizeof(iface->state), f);
            iface->state[strcspn(iface->state, "\n")] = '\0';
            fclose(f);
        }
        
        /* Get MAC */
        snprintf(path, sizeof(path), "/sys/class/net/%s/address", entry->d_name);
        f = fopen(path, "r");
        if (f) {
            fgets(iface->mac, sizeof(iface->mac), f);
            iface->mac[strcspn(iface->mac, "\n")] = '\0';
            fclose(f);
        }
        
        /* Get IP via ioctl */
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock >= 0) {
            struct ifreq ifr;
            strncpy(ifr.ifr_name, iface->name, IFNAMSIZ - 1);
            if (ioctl(sock, SIOCGIFADDR, &ifr) == 0) {
                struct sockaddr_in *addr = (struct sockaddr_in *)&ifr.ifr_addr;
                inet_ntop(AF_INET, &addr->sin_addr, iface->ip, sizeof(iface->ip));
            }
            close(sock);
        }
        
        count++;
    }
    
    closedir(dir);
    return count;
}

/* ==================== WiFi Functions ==================== */

static int wifi_enabled(void) {
    FILE *fp = popen("nmcli radio wifi 2>/dev/null", "r");
    if (!fp) return -1;
    
    char buf[32];
    fgets(buf, sizeof(buf), fp);
    pclose(fp);
    
    return strstr(buf, "enabled") ? 1 : 0;
}

static int wifi_set_enabled(int enabled) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "nmcli radio wifi %s >/dev/null 2>&1", 
             enabled ? "on" : "off");
    return system(cmd) == 0 ? 0 : -1;
}

static int wifi_scan(wifi_network_t *networks, int max_count) {
    /* Trigger scan */
    system("nmcli device wifi rescan 2>/dev/null");
    usleep(500000);
    
    FILE *fp = popen("nmcli -t -f ACTIVE,SSID,SIGNAL,SECURITY device wifi list 2>/dev/null", "r");
    if (!fp) return 0;
    
    int count = 0;
    char line[256];
    
    while (fgets(line, sizeof(line), fp) && count < max_count) {
        line[strcspn(line, "\n")] = '\0';
        
        char *active = strtok(line, ":");
        char *ssid = strtok(NULL, ":");
        char *signal = strtok(NULL, ":");
        char *security = strtok(NULL, ":");
        
        if (!ssid || !ssid[0]) continue;
        
        wifi_network_t *net = &networks[count];
        strncpy(net->ssid, ssid, sizeof(net->ssid) - 1);
        net->signal = signal ? atoi(signal) : 0;
        strncpy(net->security, security ? security : "Open", sizeof(net->security) - 1);
        net->connected = (active && strcmp(active, "yes") == 0);
        
        count++;
    }
    
    pclose(fp);
    return count;
}

static int wifi_connect(const char *ssid, const char *password) {
    char cmd[512];
    if (password && password[0]) {
        snprintf(cmd, sizeof(cmd), 
            "nmcli device wifi connect \"%s\" password \"%s\" >/dev/null 2>&1",
            ssid, password);
    } else {
        snprintf(cmd, sizeof(cmd), 
            "nmcli device wifi connect \"%s\" >/dev/null 2>&1", ssid);
    }
    return system(cmd) == 0 ? 0 : -1;
}

static int wifi_disconnect(void) {
    return system("nmcli device disconnect wlan0 >/dev/null 2>&1") == 0 ? 0 : -1;
}

/* ==================== Bluetooth Functions ==================== */

static int bluetooth_enabled(void) {
    FILE *fp = popen("bluetoothctl show 2>/dev/null | grep 'Powered: yes'", "r");
    if (!fp) return -1;
    
    char buf[64];
    int enabled = (fgets(buf, sizeof(buf), fp) != NULL);
    pclose(fp);
    
    return enabled;
}

static int bluetooth_set_enabled(int enabled) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "bluetoothctl power %s >/dev/null 2>&1",
             enabled ? "on" : "off");
    return system(cmd) == 0 ? 0 : -1;
}

/* ==================== IPC Server ==================== */

static void handle_request(int client_fd, const char *msg) {
    char response[8192] = "{\"status\":\"ok\"}";
    
    if (strstr(msg, "\"cmd\":\"interfaces\"")) {
        interface_t ifaces[16];
        int count = get_interfaces(ifaces, 16);
        
        char *ptr = response;
        ptr += sprintf(ptr, "{\"status\":\"ok\",\"interfaces\":[");
        
        for (int i = 0; i < count; i++) {
            if (i > 0) ptr += sprintf(ptr, ",");
            ptr += sprintf(ptr, 
                "{\"name\":\"%s\",\"type\":\"%s\",\"state\":\"%s\",\"mac\":\"%s\",\"ip\":\"%s\"}",
                ifaces[i].name, ifaces[i].type, ifaces[i].state, 
                ifaces[i].mac, ifaces[i].ip);
        }
        ptr += sprintf(ptr, "]}");
    }
    else if (strstr(msg, "\"cmd\":\"wifi_status\"")) {
        int enabled = wifi_enabled();
        snprintf(response, sizeof(response), 
            "{\"status\":\"ok\",\"wifi_enabled\":%s}", 
            enabled ? "true" : "false");
    }
    else if (strstr(msg, "\"cmd\":\"wifi_enable\"")) {
        int enable = strstr(msg, "\"enable\":true") != NULL;
        wifi_set_enabled(enable);
        snprintf(response, sizeof(response), 
            "{\"status\":\"ok\",\"wifi_enabled\":%s}", enable ? "true" : "false");
    }
    else if (strstr(msg, "\"cmd\":\"wifi_scan\"")) {
        wifi_network_t networks[32];
        int count = wifi_scan(networks, 32);
        
        char *ptr = response;
        ptr += sprintf(ptr, "{\"status\":\"ok\",\"networks\":[");
        
        for (int i = 0; i < count; i++) {
            if (i > 0) ptr += sprintf(ptr, ",");
            ptr += sprintf(ptr, 
                "{\"ssid\":\"%s\",\"signal\":%d,\"security\":\"%s\",\"connected\":%s}",
                networks[i].ssid, networks[i].signal, networks[i].security,
                networks[i].connected ? "true" : "false");
        }
        ptr += sprintf(ptr, "]}");
    }
    else if (strstr(msg, "\"cmd\":\"wifi_connect\"")) {
        char ssid[64] = "", password[128] = "";
        char *p;
        
        if ((p = strstr(msg, "\"ssid\":\""))) {
            sscanf(p, "\"ssid\":\"%63[^\"]\"", ssid);
        }
        if ((p = strstr(msg, "\"password\":\""))) {
            sscanf(p, "\"password\":\"%127[^\"]\"", password);
        }
        
        int result = wifi_connect(ssid, password);
        snprintf(response, sizeof(response), 
            "{\"status\":\"%s\",\"message\":\"%s\"}", 
            result == 0 ? "ok" : "error",
            result == 0 ? "Connected" : "Connection failed");
    }
    else if (strstr(msg, "\"cmd\":\"wifi_disconnect\"")) {
        wifi_disconnect();
    }
    else if (strstr(msg, "\"cmd\":\"bluetooth_status\"")) {
        int enabled = bluetooth_enabled();
        snprintf(response, sizeof(response), 
            "{\"status\":\"ok\",\"bluetooth_enabled\":%s}", 
            enabled ? "true" : "false");
    }
    else if (strstr(msg, "\"cmd\":\"bluetooth_enable\"")) {
        int enable = strstr(msg, "\"enable\":true") != NULL;
        bluetooth_set_enabled(enable);
    }
    
    /* Send response */
    uint32_t len = htonl(strlen(response));
    send(client_fd, &len, 4, 0);
    send(client_fd, response, strlen(response), 0);
}

static void *client_handler(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);
    
    while (1) {
        uint32_t length;
        if (recv(client_fd, &length, 4, 0) != 4) break;
        length = ntohl(length);
        
        if (length > 4096) break;
        
        char *msg = malloc(length + 1);
        if (!msg) break;
        
        if (recv(client_fd, msg, length, 0) != length) {
            free(msg);
            break;
        }
        msg[length] = '\0';
        
        handle_request(client_fd, msg);
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
    
    printf("[NETWORK] Listening on %s\n", SOCKET_PATH);
    
    while (g_running) {
        int *client = malloc(sizeof(int));
        *client = accept(g_server_fd, NULL, NULL);
        
        if (*client < 0) {
            free(client);
            continue;
        }
        
        pthread_t thread;
        pthread_create(&thread, NULL, client_handler, client);
        pthread_detach(thread);
    }
    
    return 0;
}

/* ==================== Main ==================== */

static void signal_handler(int sig) {
    g_running = 0;
}

int main(int argc, char *argv[]) {
    printf("[NETWORK] AI-OS Network Manager starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    mkdir("/run/aios", 0755);
    
    run_server();
    
    if (g_server_fd >= 0) {
        close(g_server_fd);
        unlink(SOCKET_PATH);
    }
    
    printf("[NETWORK] Network manager stopped\n");
    return 0;
}
