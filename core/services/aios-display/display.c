/**
 * AI-OS Display Compositor Launcher
 * Starts Wayland compositor and shell.
 * 
 * Compile: gcc -o aios-display display.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/stat.h>

#define WESTON_CONFIG "/etc/aios/weston.ini"

static volatile int g_running = 1;
static pid_t g_weston_pid = 0;
static pid_t g_shell_pid = 0;

static void signal_handler(int sig) {
    g_running = 0;
}

static const char *detect_backend(void) {
    /* Check for DRM */
    if (access("/dev/dri/card0", F_OK) == 0) {
        return "drm-backend.so";
    }
    /* Check for framebuffer */
    if (access("/dev/fb0", F_OK) == 0) {
        return "fbdev-backend.so";
    }
    /* Fallback to headless */
    return "headless-backend.so";
}

static void create_weston_config(void) {
    FILE *f = fopen(WESTON_CONFIG, "w");
    if (!f) return;
    
    fprintf(f,
        "[core]\n"
        "shell=desktop-shell.so\n"
        "require-input=false\n"
        "\n"
        "[shell]\n"
        "background-color=0xff1a1a2e\n"
        "panel-position=none\n"
        "locking=true\n"
        "\n"
        "[output]\n"
        "name=*\n"
        "mode=preferred\n"
        "transform=normal\n"
        "\n"
        "[keyboard]\n"
        "keymap_layout=us\n"
        "\n"
        "[input-method]\n"
        "path=/usr/libexec/weston-keyboard\n"
        "\n"
        "[libinput]\n"
        "enable-tap=true\n"
        "natural-scroll=false\n"
    );
    
    fclose(f);
}

static void start_weston(void) {
    const char *backend = detect_backend();
    printf("[DISPLAY] Using backend: %s\n", backend);
    
    create_weston_config();
    
    g_weston_pid = fork();
    if (g_weston_pid == 0) {
        /* Child: start weston */
        setenv("XDG_RUNTIME_DIR", "/run/user/0", 1);
        
        char backend_arg[64];
        snprintf(backend_arg, sizeof(backend_arg), "--backend=%s", backend);
        
        execlp("weston", "weston",
            backend_arg,
            "--config=" WESTON_CONFIG,
            "--log=/var/log/weston.log",
            NULL);
        
        perror("execlp weston");
        exit(1);
    }
    
    printf("[DISPLAY] Weston started (PID %d)\n", g_weston_pid);
    
    /* Wait for Weston to initialize */
    sleep(2);
}

static void start_shell(void) {
    g_shell_pid = fork();
    if (g_shell_pid == 0) {
        /* Child: start shell */
        setenv("XDG_RUNTIME_DIR", "/run/user/0", 1);
        setenv("WAYLAND_DISPLAY", "wayland-0", 1);
        
        execlp("/usr/bin/aios-shell", "aios-shell", NULL);
        
        /* Fallback to weston-terminal */
        execlp("weston-terminal", "weston-terminal", NULL);
        
        perror("execlp shell");
        exit(1);
    }
    
    printf("[DISPLAY] Shell started (PID %d)\n", g_shell_pid);
}

int main(int argc, char *argv[]) {
    printf("[DISPLAY] AI-OS Display Service starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    signal(SIGCHLD, SIG_IGN);
    
    /* Create runtime directory */
    mkdir("/run/user", 0755);
    mkdir("/run/user/0", 0700);
    
    /* Start Weston compositor */
    start_weston();
    
    /* Start AI-OS shell */
    start_shell();
    
    /* Wait for processes */
    while (g_running) {
        int status;
        pid_t pid = waitpid(-1, &status, WNOHANG);
        
        if (pid == g_weston_pid) {
            printf("[DISPLAY] Weston exited, restarting...\n");
            sleep(1);
            start_weston();
            start_shell();
        } else if (pid == g_shell_pid) {
            printf("[DISPLAY] Shell exited, restarting...\n");
            sleep(1);
            start_shell();
        }
        
        sleep(1);
    }
    
    /* Cleanup */
    if (g_shell_pid > 0) kill(g_shell_pid, SIGTERM);
    if (g_weston_pid > 0) kill(g_weston_pid, SIGTERM);
    
    printf("[DISPLAY] Display service stopped\n");
    return 0;
}
