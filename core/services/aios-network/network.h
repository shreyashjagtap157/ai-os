/**
 * AI-OS Network Service Header
 * Network connectivity and management
 */

#ifndef AIOS_NETWORK_H
#define AIOS_NETWORK_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ==================== Types ====================

typedef enum {
    NETWORK_STATE_DISCONNECTED = 0,
    NETWORK_STATE_CONNECTING,
    NETWORK_STATE_CONNECTED,
    NETWORK_STATE_DISCONNECTING,
    NETWORK_STATE_ERROR
} NetworkState;

typedef enum {
    CONNECTION_TYPE_UNKNOWN = 0,
    CONNECTION_TYPE_ETHERNET,
    CONNECTION_TYPE_WIFI,
    CONNECTION_TYPE_CELLULAR,
    CONNECTION_TYPE_VPN
} ConnectionType;

typedef enum {
    WIFI_SECURITY_NONE = 0,
    WIFI_SECURITY_WEP,
    WIFI_SECURITY_WPA,
    WIFI_SECURITY_WPA2,
    WIFI_SECURITY_WPA3,
    WIFI_SECURITY_ENTERPRISE
} WifiSecurity;

typedef struct {
    char ssid[64];
    char bssid[18];
    int signal_strength;  // dBm
    int frequency;        // MHz
    WifiSecurity security;
    bool is_saved;
    bool is_connected;
} WifiNetwork;

typedef struct {
    char interface[32];
    char ip_address[46];
    char netmask[46];
    char gateway[46];
    char dns_primary[46];
    char dns_secondary[46];
    char mac_address[18];
    ConnectionType type;
    NetworkState state;
    int speed_mbps;
    uint64_t rx_bytes;
    uint64_t tx_bytes;
} NetworkInterface;

typedef struct {
    bool is_online;
    ConnectionType active_type;
    int signal_strength;
    char active_ssid[64];
    char public_ip[46];
} NetworkStatus;

typedef void (*NetworkStateCallback)(NetworkState state, const char *interface);
typedef void (*WifiScanCallback)(WifiNetwork *networks, int count);

// ==================== Initialization ====================

/**
 * Initialize network subsystem
 * @return 0 on success
 */
int network_init(void);

/**
 * Shutdown network subsystem
 */
void network_shutdown(void);

// ==================== Status ====================

/**
 * Get overall network status
 * @param status Pointer to status structure
 * @return 0 on success
 */
int network_get_status(NetworkStatus *status);

/**
 * Check if device is online
 * @return true if connected to internet
 */
bool network_is_online(void);

/**
 * Get interface count
 */
int network_get_interface_count(void);

/**
 * Get interface info
 * @param index Interface index
 * @param info Pointer to interface info structure
 * @return 0 on success
 */
int network_get_interface(int index, NetworkInterface *info);

// ==================== WiFi ====================

/**
 * Enable/disable WiFi
 * @param enable True to enable
 * @return 0 on success
 */
int wifi_set_enabled(bool enable);

/**
 * Check if WiFi is enabled
 */
bool wifi_is_enabled(void);

/**
 * Start WiFi scan
 * @param callback Function to call with results
 * @return 0 on success
 */
int wifi_scan(WifiScanCallback callback);

/**
 * Connect to WiFi network
 * @param ssid Network SSID
 * @param password Network password (NULL for open)
 * @return 0 on success
 */
int wifi_connect(const char *ssid, const char *password);

/**
 * Disconnect from current WiFi
 * @return 0 on success
 */
int wifi_disconnect(void);

/**
 * Forget a saved network
 * @param ssid Network SSID
 * @return 0 on success
 */
int wifi_forget(const char *ssid);

/**
 * Get current WiFi info
 * @param network Pointer to network info
 * @return 0 on success
 */
int wifi_get_current(WifiNetwork *network);

// ==================== Ethernet ====================

/**
 * Enable/disable ethernet
 */
int ethernet_set_enabled(bool enable);

/**
 * Configure static IP
 * @param interface Interface name
 * @param ip IP address
 * @param netmask Netmask
 * @param gateway Gateway
 * @return 0 on success
 */
int ethernet_set_static(const char *interface, const char *ip, 
                        const char *netmask, const char *gateway);

/**
 * Enable DHCP
 * @param interface Interface name
 * @return 0 on success
 */
int ethernet_set_dhcp(const char *interface);

// ==================== DNS ====================

/**
 * Set DNS servers
 * @param primary Primary DNS
 * @param secondary Secondary DNS (can be NULL)
 * @return 0 on success
 */
int network_set_dns(const char *primary, const char *secondary);

/**
 * Resolve hostname
 * @param hostname Hostname to resolve
 * @param ip_out Buffer for IP address
 * @param ip_len Buffer length
 * @return 0 on success
 */
int network_resolve(const char *hostname, char *ip_out, size_t ip_len);

// ==================== Events ====================

/**
 * Register network state callback
 */
void network_register_callback(NetworkStateCallback callback);

// ==================== Diagnostics ====================

/**
 * Ping a host
 * @param host Host to ping
 * @param timeout_ms Timeout in milliseconds
 * @return Round-trip time in ms, negative on error
 */
int network_ping(const char *host, int timeout_ms);

/**
 * Get current speed test results
 * @param download_mbps Pointer for download speed
 * @param upload_mbps Pointer for upload speed
 * @return 0 on success
 */
int network_speed_test(float *download_mbps, float *upload_mbps);

#ifdef __cplusplus
}
#endif

#endif // AIOS_NETWORK_H
