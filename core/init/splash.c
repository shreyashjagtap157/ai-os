/**
 * AI-OS Boot Splash
 * Framebuffer-based boot animation.
 * 
 * Compile: gcc -o aios-splash splash.c -lpthread
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fb.h>
#include <math.h>

#define FB_DEVICE "/dev/fb0"

/* ==================== Framebuffer ==================== */

static int fb_fd = -1;
static char *fb_mem = NULL;
static struct fb_var_screeninfo vinfo;
static struct fb_fix_screeninfo finfo;
static int screen_width, screen_height, bpp, line_length;

static int fb_init(void) {
    fb_fd = open(FB_DEVICE, O_RDWR);
    if (fb_fd < 0) {
        perror("Cannot open framebuffer");
        return -1;
    }
    
    if (ioctl(fb_fd, FBIOGET_VSCREENINFO, &vinfo) < 0) {
        perror("FBIOGET_VSCREENINFO");
        close(fb_fd);
        return -1;
    }
    
    if (ioctl(fb_fd, FBIOGET_FSCREENINFO, &finfo) < 0) {
        perror("FBIOGET_FSCREENINFO");
        close(fb_fd);
        return -1;
    }
    
    screen_width = vinfo.xres;
    screen_height = vinfo.yres;
    bpp = vinfo.bits_per_pixel / 8;
    line_length = finfo.line_length;
    
    fb_mem = mmap(NULL, finfo.smem_len, PROT_READ | PROT_WRITE, MAP_SHARED, fb_fd, 0);
    if (fb_mem == MAP_FAILED) {
        perror("mmap");
        close(fb_fd);
        return -1;
    }
    
    printf("[SPLASH] Framebuffer: %dx%d, %d bpp\n", screen_width, screen_height, bpp * 8);
    return 0;
}

static void fb_cleanup(void) {
    if (fb_mem && fb_mem != MAP_FAILED) {
        munmap(fb_mem, finfo.smem_len);
    }
    if (fb_fd >= 0) {
        close(fb_fd);
    }
}

static void put_pixel(int x, int y, unsigned int color) {
    if (x < 0 || x >= screen_width || y < 0 || y >= screen_height) return;
    
    long offset = y * line_length + x * bpp;
    
    if (bpp == 4) {
        *((unsigned int *)(fb_mem + offset)) = color;
    } else if (bpp == 3) {
        fb_mem[offset] = color & 0xFF;
        fb_mem[offset + 1] = (color >> 8) & 0xFF;
        fb_mem[offset + 2] = (color >> 16) & 0xFF;
    } else if (bpp == 2) {
        *((unsigned short *)(fb_mem + offset)) = 
            ((color >> 8) & 0xF800) | ((color >> 5) & 0x07E0) | ((color >> 3) & 0x001F);
    }
}

static void fill_rect(int x, int y, int w, int h, unsigned int color) {
    for (int j = y; j < y + h; j++) {
        for (int i = x; i < x + w; i++) {
            put_pixel(i, j, color);
        }
    }
}

static void fill_screen(unsigned int color) {
    fill_rect(0, 0, screen_width, screen_height, color);
}

static void draw_circle(int cx, int cy, int r, unsigned int color) {
    for (int y = -r; y <= r; y++) {
        for (int x = -r; x <= r; x++) {
            if (x * x + y * y <= r * r) {
                put_pixel(cx + x, cy + y, color);
            }
        }
    }
}

/* ==================== Logo Drawing ==================== */

/* Simple AI-OS logo: stylized brain/circuit pattern */
static void draw_logo(int cx, int cy, float scale, unsigned int color) {
    int size = (int)(80 * scale);
    
    /* Outer circle */
    for (int a = 0; a < 360; a += 5) {
        float rad = a * 3.14159 / 180;
        int x = cx + (int)(size * cos(rad));
        int y = cy + (int)(size * sin(rad));
        draw_circle(x, y, 3, color);
    }
    
    /* Inner pattern - neural network nodes */
    int nodes[][2] = {
        {0, 0},
        {-30, -30}, {30, -30}, {-30, 30}, {30, 30},
        {-50, 0}, {50, 0}, {0, -50}, {0, 50}
    };
    
    for (int i = 0; i < 9; i++) {
        int x = cx + (int)(nodes[i][0] * scale);
        int y = cy + (int)(nodes[i][1] * scale);
        draw_circle(x, y, (int)(8 * scale), color);
    }
    
    /* Connections */
    unsigned int line_color = (color & 0xFEFEFE) >> 1;  /* Dimmer */
    for (int i = 1; i < 9; i++) {
        int x1 = cx;
        int y1 = cy;
        int x2 = cx + (int)(nodes[i][0] * scale);
        int y2 = cy + (int)(nodes[i][1] * scale);
        
        /* Simple line drawing */
        int dx = abs(x2 - x1), sx = x1 < x2 ? 1 : -1;
        int dy = -abs(y2 - y1), sy = y1 < y2 ? 1 : -1;
        int err = dx + dy, e2;
        
        while (1) {
            put_pixel(x1, y1, line_color);
            if (x1 == x2 && y1 == y2) break;
            e2 = 2 * err;
            if (e2 >= dy) { err += dy; x1 += sx; }
            if (e2 <= dx) { err += dx; y1 += sy; }
        }
    }
}

/* ==================== Text Drawing (Simple) ==================== */

/* 5x7 font data for basic characters */
static const unsigned char font_data[][7] = {
    /* A */ {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11},
    /* I */ {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1F},
    /* - */ {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00},
    /* O */ {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E},
    /* S */ {0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E},
};

static void draw_char(int x, int y, int ch_idx, int scale, unsigned int color) {
    for (int row = 0; row < 7; row++) {
        unsigned char line = font_data[ch_idx][row];
        for (int col = 0; col < 5; col++) {
            if (line & (0x10 >> col)) {
                fill_rect(x + col * scale, y + row * scale, scale, scale, color);
            }
        }
    }
}

static void draw_text_aios(int x, int y, int scale, unsigned int color) {
    int spacing = 6 * scale;
    draw_char(x, y, 0, scale, color);             /* A */
    draw_char(x + spacing, y, 1, scale, color);   /* I */
    draw_char(x + spacing * 2, y, 2, scale, color); /* - */
    draw_char(x + spacing * 3, y, 3, scale, color); /* O */
    draw_char(x + spacing * 4, y, 4, scale, color); /* S */
}

/* ==================== Animation ==================== */

static volatile int g_running = 1;

static void signal_handler(int sig) {
    g_running = 0;
}

static void run_animation(void) {
    int cx = screen_width / 2;
    int cy = screen_height / 2 - 50;
    
    /* Background color: dark blue gradient simulated */
    unsigned int bg_color = 0xFF1a1a2e;
    fill_screen(bg_color);
    
    /* Logo color: purple/blue gradient effect */
    unsigned int logo_color = 0xFF667eea;
    
    /* Draw static logo */
    draw_logo(cx, cy, 1.0, logo_color);
    
    /* Draw "AI-OS" text below */
    int text_x = cx - 75;
    int text_y = cy + 120;
    draw_text_aios(text_x, text_y, 5, 0xFFFFFFFF);
    
    /* Animated loading bar */
    int bar_width = 300;
    int bar_height = 8;
    int bar_x = cx - bar_width / 2;
    int bar_y = text_y + 80;
    
    /* Bar background */
    fill_rect(bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4, 0xFF333355);
    
    /* Animate progress */
    for (int progress = 0; progress <= 100 && g_running; progress += 2) {
        int filled = (bar_width * progress) / 100;
        fill_rect(bar_x, bar_y, filled, bar_height, logo_color);
        usleep(50000);  /* 50ms */
    }
    
    /* Hold for a moment */
    sleep(1);
}

/* ==================== Main ==================== */

int main(int argc, char *argv[]) {
    printf("[SPLASH] AI-OS Boot Splash starting...\n");
    
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    if (fb_init() < 0) {
        fprintf(stderr, "Framebuffer not available, skipping splash\n");
        return 0;
    }
    
    run_animation();
    
    fb_cleanup();
    
    printf("[SPLASH] Boot splash complete\n");
    return 0;
}
