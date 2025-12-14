/**
 * AI-OS CLI Tool
 * Command-line interface for AI-OS in C.
 * 
 * Compile: gcc -o aios cli.c -lcjson
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <readline/readline.h>
#include <readline/history.h>

#define AGENT_SOCKET "/run/aios/agent.sock"
#define VERSION "1.0.0"

/* ==================== Colors ==================== */

#define COLOR_RESET  "\033[0m"
#define COLOR_RED    "\033[31m"
#define COLOR_GREEN  "\033[32m"
#define COLOR_YELLOW "\033[33m"
#define COLOR_BLUE   "\033[34m"
#define COLOR_CYAN   "\033[36m"

/* ==================== IPC ==================== */

static int send_to_agent(const char *message, char *response, size_t response_size) {
    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) {
        strcpy(response, "{\"error\":\"Failed to create socket\"}");
        return -1;
    }
    
    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, AGENT_SOCKET, sizeof(addr.sun_path) - 1);
    
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        strcpy(response, "{\"error\":\"Agent not running\"}");
        return -1;
    }
    
    /* Send message */
    uint32_t len = htonl(strlen(message));
    send(sock, &len, 4, 0);
    send(sock, message, strlen(message), 0);
    
    /* Receive response */
    if (recv(sock, &len, 4, 0) != 4) {
        close(sock);
        strcpy(response, "{\"error\":\"No response\"}");
        return -1;
    }
    len = ntohl(len);
    
    if (len >= response_size) len = response_size - 1;
    
    size_t received = 0;
    while (received < len) {
        ssize_t n = recv(sock, response + received, len - received, 0);
        if (n <= 0) break;
        received += n;
    }
    response[received] = '\0';
    
    close(sock);
    return 0;
}

/* ==================== Commands ==================== */

static void cmd_status(void) {
    char response[4096];
    send_to_agent("{\"cmd\":\"status\"}", response, sizeof(response));
    
    /* Parse and display */
    printf("\n");
    printf("┌─────────────────────────────────────┐\n");
    printf("│         " COLOR_CYAN "AI-OS Status" COLOR_RESET "                │\n");
    printf("├─────────────────────────────────────┤\n");
    
    /* Simple JSON parsing */
    char *p;
    if ((p = strstr(response, "\"running\":"))) {
        printf("│ Running:        %18s │\n", 
            strstr(p, "true") ? "true" : "false");
    }
    if ((p = strstr(response, "\"ai_configured\":"))) {
        printf("│ AI Configured:  %18s │\n", 
            strstr(p, "true") ? "true" : "false");
    }
    if ((p = strstr(response, "\"hostname\":\""))) {
        char hostname[32];
        sscanf(p, "\"hostname\":\"%31[^\"]\"", hostname);
        printf("│ Hostname:       %18s │\n", hostname);
    }
    if ((p = strstr(response, "\"kernel\":\""))) {
        char kernel[32];
        sscanf(p, "\"kernel\":\"%31[^\"]\"", kernel);
        printf("│ Kernel:         %18s │\n", kernel);
    }
    
    printf("└─────────────────────────────────────┘\n\n");
}

static void cmd_chat(const char *text) {
    char message[4096];
    snprintf(message, sizeof(message), "{\"cmd\":\"chat\",\"text\":\"%s\"}", text);
    
    char response[8192];
    if (send_to_agent(message, response, sizeof(response)) < 0) {
        printf(COLOR_RED "Error: %s" COLOR_RESET "\n", response);
        return;
    }
    
    /* Extract response text */
    char *p = strstr(response, "\"response\":\"");
    if (p) {
        p += 12;
        char *end = strchr(p, '"');
        if (end) {
            *end = '\0';
            printf("\n" COLOR_GREEN "%s" COLOR_RESET "\n", p);
        }
    }
    
    /* Check for action result */
    p = strstr(response, "\"action_result\":");
    if (p) {
        if (strstr(p, "\"success\":true")) {
            char *msg = strstr(p, "\"message\":\"");
            if (msg) {
                msg += 11;
                char *end = strchr(msg, '"');
                if (end) {
                    *end = '\0';
                    printf(COLOR_YELLOW "✓ %s" COLOR_RESET "\n", msg);
                }
            }
        }
    }
    printf("\n");
}

static void cmd_action(const char *action, const char *params) {
    char message[1024];
    if (params && params[0]) {
        snprintf(message, sizeof(message), 
            "{\"cmd\":\"action\",\"action\":{\"action\":\"%s\",%s}}", action, params);
    } else {
        snprintf(message, sizeof(message), 
            "{\"cmd\":\"action\",\"action\":{\"action\":\"%s\"}}", action);
    }
    
    char response[4096];
    send_to_agent(message, response, sizeof(response));
    
    if (strstr(response, "\"success\":true")) {
        printf(COLOR_GREEN "✓ Action completed" COLOR_RESET "\n");
    } else {
        printf(COLOR_RED "✗ Action failed" COLOR_RESET "\n");
    }
}

static void cmd_help(void) {
    printf("\n" COLOR_CYAN "AI-OS CLI Commands:" COLOR_RESET "\n\n");
    printf("  " COLOR_GREEN "<text>" COLOR_RESET "        Chat with AI agent\n");
    printf("  " COLOR_GREEN "!status" COLOR_RESET "      Show system status\n");
    printf("  " COLOR_GREEN "!brightness N" COLOR_RESET " Set brightness (0-100)\n");
    printf("  " COLOR_GREEN "!volume N" COLOR_RESET "    Set volume (0-100)\n");
    printf("  " COLOR_GREEN "!wifi on|off" COLOR_RESET " Toggle WiFi\n");
    printf("  " COLOR_GREEN "!launch APP" COLOR_RESET "  Launch application\n");
    printf("  " COLOR_GREEN "!clear" COLOR_RESET "       Clear conversation\n");
    printf("  " COLOR_GREEN "help" COLOR_RESET "         Show this help\n");
    printf("  " COLOR_GREEN "exit" COLOR_RESET "         Exit shell\n\n");
}

/* ==================== Interactive Shell ==================== */

static void run_shell(void) {
    printf("\n");
    printf("┌─────────────────────────────────────────────────┐\n");
    printf("│            " COLOR_CYAN "AI-OS Interactive Shell" COLOR_RESET "              │\n");
    printf("├─────────────────────────────────────────────────┤\n");
    printf("│  Type commands to chat with AI.                 │\n");
    printf("│  Use !<cmd> for direct actions.                 │\n");
    printf("│  Type 'help' for commands, 'exit' to quit.      │\n");
    printf("└─────────────────────────────────────────────────┘\n\n");
    
    /* Setup history */
    using_history();
    read_history("~/.aios_history");
    
    char *line;
    while ((line = readline(COLOR_CYAN "AI-OS> " COLOR_RESET)) != NULL) {
        /* Trim whitespace */
        char *p = line;
        while (*p == ' ') p++;
        
        if (!*p) {
            free(line);
            continue;
        }
        
        add_history(p);
        
        if (strcmp(p, "exit") == 0 || strcmp(p, "quit") == 0) {
            free(line);
            break;
        }
        else if (strcmp(p, "help") == 0) {
            cmd_help();
        }
        else if (strncmp(p, "!status", 7) == 0) {
            cmd_status();
        }
        else if (strncmp(p, "!brightness ", 12) == 0) {
            char params[64];
            snprintf(params, sizeof(params), "\"level\":%s", p + 12);
            cmd_action("brightness", params);
        }
        else if (strncmp(p, "!volume ", 8) == 0) {
            char params[64];
            snprintf(params, sizeof(params), "\"level\":%s", p + 8);
            cmd_action("volume", params);
        }
        else if (strcmp(p, "!wifi on") == 0) {
            cmd_action("wifi", "\"enabled\":true");
        }
        else if (strcmp(p, "!wifi off") == 0) {
            cmd_action("wifi", "\"enabled\":false");
        }
        else if (strncmp(p, "!launch ", 8) == 0) {
            char params[256];
            snprintf(params, sizeof(params), "\"app\":\"%s\"", p + 8);
            cmd_action("launch", params);
        }
        else if (strcmp(p, "!clear") == 0) {
            send_to_agent("{\"cmd\":\"clear\"}", (char[256]){0}, 256);
            printf("Conversation cleared.\n");
        }
        else if (p[0] == '!') {
            printf(COLOR_RED "Unknown command: %s" COLOR_RESET "\n", p);
        }
        else {
            cmd_chat(p);
        }
        
        free(line);
    }
    
    write_history("~/.aios_history");
    printf("Goodbye!\n");
}

/* ==================== Main ==================== */

static void usage(void) {
    printf("Usage: aios [command] [args]\n\n");
    printf("Commands:\n");
    printf("  shell          Interactive shell (default)\n");
    printf("  status         Show system status\n");
    printf("  chat <text>    Chat with AI\n");
    printf("  action <type>  Execute action\n");
    printf("  --version      Show version\n");
    printf("  --help         Show this help\n");
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        run_shell();
        return 0;
    }
    
    if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
        printf("AI-OS CLI v%s\n", VERSION);
        return 0;
    }
    
    if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        usage();
        return 0;
    }
    
    if (strcmp(argv[1], "shell") == 0) {
        run_shell();
    }
    else if (strcmp(argv[1], "status") == 0) {
        cmd_status();
    }
    else if (strcmp(argv[1], "chat") == 0 && argc > 2) {
        /* Concatenate remaining args */
        char text[1024] = "";
        for (int i = 2; i < argc; i++) {
            if (i > 2) strcat(text, " ");
            strcat(text, argv[i]);
        }
        cmd_chat(text);
    }
    else if (strcmp(argv[1], "action") == 0 && argc > 2) {
        const char *params = argc > 3 ? argv[3] : "";
        cmd_action(argv[2], params);
    }
    else {
        /* Treat as chat */
        char text[1024] = "";
        for (int i = 1; i < argc; i++) {
            if (i > 1) strcat(text, " ");
            strcat(text, argv[i]);
        }
        cmd_chat(text);
    }
    
    return 0;
}
