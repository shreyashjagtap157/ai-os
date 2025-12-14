/**
 * AI-OS Agent Daemon
 * Core AI agent service in C for direct hardware control.
 * 
 * Dependencies: libcurl, cjson
 * Compile: gcc -o aios-agent agent.c common.c hal.c -lcurl -lcjson -lpthread
 */

#ifndef AIOS_AGENT_H
#define AIOS_AGENT_H

#include <stdbool.h>
#include <stddef.h>

/* Configuration */
#define AGENT_SOCKET_PATH   "/run/aios/agent.sock"
#define AGENT_CONFIG_PATH   "/etc/aios/agent.json"
#define AGENT_LOG_PATH      "/var/log/aios/agent.log"
#define MAX_MESSAGE_SIZE    65536
#define MAX_HISTORY_SIZE    20

/* AI Providers */
typedef enum {
    AI_PROVIDER_OPENAI,
    AI_PROVIDER_ANTHROPIC,
    AI_PROVIDER_LOCAL
} ai_provider_t;

/* Agent configuration */
typedef struct {
    ai_provider_t provider;
    char openai_api_key[256];
    char anthropic_api_key[256];
    char model[64];
    bool confirm_dangerous;
} agent_config_t;

/* Message types */
typedef struct {
    char role[16];      /* "user", "assistant", "system" */
    char *content;
} chat_message_t;

/* Action result */
typedef struct {
    bool success;
    char message[256];
    char *data;         /* JSON data, optional */
} action_result_t;

/* Initialize agent */
int agent_init(void);

/* Cleanup agent */
void agent_cleanup(void);

/* Start agent daemon (blocks) */
int agent_run(void);

/* Process chat message */
int agent_chat(const char *input, char *response, size_t response_size, 
               action_result_t *action_result);

/* Execute action directly */
int agent_execute_action(const char *action_json, action_result_t *result);

/* Get system status */
int agent_status(char *status_json, size_t size);

#endif /* AIOS_AGENT_H */
