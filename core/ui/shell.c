/**
 * AI-OS Shell UI
 * GTK4-based desktop shell in C.
 * 
 * Compile: gcc -o aios-shell shell.c `pkg-config --cflags --libs gtk4` -lpthread
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <pthread.h>
#include <gtk/gtk.h>

#define AGENT_SOCKET "/run/aios/agent.sock"

/* ==================== Globals ==================== */

static GtkWidget *g_window;
static GtkWidget *g_clock_label;
static GtkWidget *g_date_label;
static GtkWidget *g_input_entry;
static GtkWidget *g_response_label;
static GtkWidget *g_status_bar;

/* ==================== Agent Communication ==================== */

static int send_to_agent(const char *text, char *response, size_t response_size) {
    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) return -1;
    
    struct sockaddr_un addr = {0};
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, AGENT_SOCKET);
    
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(sock);
        strcpy(response, "Agent not running");
        return -1;
    }
    
    char msg[2048];
    snprintf(msg, sizeof(msg), "{\"cmd\":\"chat\",\"text\":\"%s\"}", text);
    
    uint32_t len = htonl(strlen(msg));
    send(sock, &len, 4, 0);
    send(sock, msg, strlen(msg), 0);
    
    if (recv(sock, &len, 4, 0) != 4) {
        close(sock);
        return -1;
    }
    len = ntohl(len);
    
    if (len < response_size) {
        recv(sock, response, len, 0);
        response[len] = '\0';
    }
    
    close(sock);
    return 0;
}

/* ==================== Clock Update ==================== */

static gboolean update_clock(gpointer data) {
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    
    char time_str[32], date_str[64];
    strftime(time_str, sizeof(time_str), "%H:%M", tm);
    strftime(date_str, sizeof(date_str), "%A, %B %d", tm);
    
    gtk_label_set_text(GTK_LABEL(g_clock_label), time_str);
    gtk_label_set_text(GTK_LABEL(g_date_label), date_str);
    
    return G_SOURCE_CONTINUE;
}

/* ==================== Input Handling ==================== */

static void on_input_activate(GtkEntry *entry, gpointer user_data) {
    GtkEntryBuffer *buffer = gtk_entry_get_buffer(entry);
    const char *text = gtk_entry_buffer_get_text(buffer);
    
    if (!text || !text[0]) return;
    
    gtk_label_set_text(GTK_LABEL(g_response_label), "Thinking...");
    
    char response[4096] = {0};
    if (send_to_agent(text, response, sizeof(response)) == 0) {
        /* Extract response text */
        char *p = strstr(response, "\"response\":\"");
        if (p) {
            p += 12;
            char *end = strchr(p, '"');
            if (end) {
                *end = '\0';
                gtk_label_set_text(GTK_LABEL(g_response_label), p);
            }
        } else {
            gtk_label_set_text(GTK_LABEL(g_response_label), response);
        }
    } else {
        gtk_label_set_text(GTK_LABEL(g_response_label), response);
    }
    
    gtk_entry_buffer_set_text(buffer, "", 0);
}

/* ==================== CSS Styling ==================== */

static void load_css(void) {
    GtkCssProvider *provider = gtk_css_provider_new();
    
    const char *css = 
        "window {"
        "  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);"
        "}"
        ".clock {"
        "  font-size: 96px;"
        "  font-weight: 200;"
        "  color: white;"
        "  text-shadow: 0 2px 10px rgba(0,0,0,0.3);"
        "}"
        ".date {"
        "  font-size: 24px;"
        "  color: #a0a0c0;"
        "}"
        ".ai-input {"
        "  background: rgba(255,255,255,0.1);"
        "  border: 2px solid rgba(255,255,255,0.2);"
        "  border-radius: 25px;"
        "  padding: 12px 24px;"
        "  font-size: 18px;"
        "  color: white;"
        "  min-width: 500px;"
        "}"
        ".ai-input:focus {"
        "  border-color: #667eea;"
        "  box-shadow: 0 0 20px rgba(102,126,234,0.3);"
        "}"
        ".response {"
        "  font-size: 20px;"
        "  color: #c0c0e0;"
        "  padding: 20px;"
        "}"
        ".status-bar {"
        "  background: rgba(0,0,0,0.3);"
        "  padding: 8px 16px;"
        "}"
        ".status-item {"
        "  color: #a0a0c0;"
        "  font-size: 14px;"
        "  margin: 0 8px;"
        "}";
    
    gtk_css_provider_load_from_string(provider, css);
    
    GdkDisplay *display = gdk_display_get_default();
    gtk_style_context_add_provider_for_display(display, 
        GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
}

/* ==================== UI Building ==================== */

static void build_status_bar(GtkWidget *parent) {
    GtkWidget *bar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_widget_add_css_class(bar, "status-bar");
    gtk_widget_set_valign(bar, GTK_ALIGN_END);
    
    /* Left section */
    GtkWidget *left = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_widget_set_hexpand(left, TRUE);
    gtk_widget_set_halign(left, GTK_ALIGN_START);
    
    GtkWidget *logo = gtk_label_new("🤖 AI-OS");
    gtk_widget_add_css_class(logo, "status-item");
    gtk_box_append(GTK_BOX(left), logo);
    
    gtk_box_append(GTK_BOX(bar), left);
    
    /* Right section */
    GtkWidget *right = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 16);
    gtk_widget_set_halign(right, GTK_ALIGN_END);
    
    GtkWidget *wifi = gtk_label_new("📶 Connected");
    gtk_widget_add_css_class(wifi, "status-item");
    gtk_box_append(GTK_BOX(right), wifi);
    
    GtkWidget *battery = gtk_label_new("🔋 100%");
    gtk_widget_add_css_class(battery, "status-item");
    gtk_box_append(GTK_BOX(right), battery);
    
    GtkWidget *volume = gtk_label_new("🔊 80%");
    gtk_widget_add_css_class(volume, "status-item");
    gtk_box_append(GTK_BOX(right), volume);
    
    gtk_box_append(GTK_BOX(bar), right);
    
    gtk_box_append(GTK_BOX(parent), bar);
    g_status_bar = bar;
}

static void activate(GtkApplication *app, gpointer user_data) {
    load_css();
    
    /* Main window */
    g_window = gtk_application_window_new(app);
    gtk_window_set_title(GTK_WINDOW(g_window), "AI-OS");
    gtk_window_set_default_size(GTK_WINDOW(g_window), 1920, 1080);
    gtk_window_fullscreen(GTK_WINDOW(g_window));
    
    /* Main layout */
    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_window_set_child(GTK_WINDOW(g_window), main_box);
    
    /* Center content */
    GtkWidget *center = gtk_box_new(GTK_ORIENTATION_VERTICAL, 20);
    gtk_widget_set_vexpand(center, TRUE);
    gtk_widget_set_valign(center, GTK_ALIGN_CENTER);
    gtk_widget_set_halign(center, GTK_ALIGN_CENTER);
    gtk_box_append(GTK_BOX(main_box), center);
    
    /* Clock */
    g_clock_label = gtk_label_new("00:00");
    gtk_widget_add_css_class(g_clock_label, "clock");
    gtk_box_append(GTK_BOX(center), g_clock_label);
    
    /* Date */
    g_date_label = gtk_label_new("Loading...");
    gtk_widget_add_css_class(g_date_label, "date");
    gtk_box_append(GTK_BOX(center), g_date_label);
    
    /* Spacer */
    GtkWidget *spacer = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_size_request(spacer, -1, 60);
    gtk_box_append(GTK_BOX(center), spacer);
    
    /* AI Input */
    g_input_entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(g_input_entry), "Ask AI anything...");
    gtk_widget_add_css_class(g_input_entry, "ai-input");
    g_signal_connect(g_input_entry, "activate", G_CALLBACK(on_input_activate), NULL);
    gtk_box_append(GTK_BOX(center), g_input_entry);
    
    /* Response */
    g_response_label = gtk_label_new("Press Enter to ask the AI");
    gtk_widget_add_css_class(g_response_label, "response");
    gtk_label_set_wrap(GTK_LABEL(g_response_label), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(g_response_label), 80);
    gtk_box_append(GTK_BOX(center), g_response_label);
    
    /* Status bar */
    build_status_bar(main_box);
    
    /* Start clock update */
    g_timeout_add_seconds(1, update_clock, NULL);
    update_clock(NULL);
    
    gtk_window_present(GTK_WINDOW(g_window));
}

/* ==================== Main ==================== */

int main(int argc, char *argv[]) {
    GtkApplication *app = gtk_application_new("com.aios.shell", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
    
    int status = g_application_run(G_APPLICATION(app), argc, argv);
    g_object_unref(app);
    
    return status;
}
