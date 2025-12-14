# AI-OS Core Build System
# Builds all native C components for standalone Linux OS

CC = gcc
CFLAGS = -Wall -Wextra -O2 -fPIC
LDFLAGS = -lpthread

# Directories
BUILD_DIR = ../build/output
BIN_DIR = $(BUILD_DIR)/bin
LIB_DIR = $(BUILD_DIR)/lib
SBIN_DIR = $(BUILD_DIR)/sbin

# Package config
GTK4_CFLAGS := $(shell pkg-config --cflags gtk4 2>/dev/null)
GTK4_LIBS := $(shell pkg-config --libs gtk4 2>/dev/null)
CURL_LIBS := $(shell pkg-config --libs libcurl 2>/dev/null || echo "-lcurl")
CJSON_LIBS := $(shell pkg-config --libs libcjson 2>/dev/null || echo "-lcjson")
EVDEV_LIBS := $(shell pkg-config --libs libevdev 2>/dev/null || echo "-levdev")
ALSA_LIBS := $(shell pkg-config --libs alsa 2>/dev/null || echo "-lasound")

# Targets
.PHONY: all dirs hal services ui tools install clean deps

all: dirs hal services ui tools

dirs:
	@mkdir -p $(BIN_DIR) $(LIB_DIR) $(SBIN_DIR)

# ==================== HAL Library ====================
hal: dirs
	$(CC) $(CFLAGS) -shared -fPIC -o $(LIB_DIR)/libaios-hal.so hal/hal.c
	@echo "✓ Built: libaios-hal.so"

# ==================== Core Services ====================
services: hal aios-agent aios-input aios-power aios-notify aios-voice aios-network aios-display

aios-agent:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-agent \
		services/aios-agent/agent.c \
		-Ihal -L$(LIB_DIR) -laios-hal \
		$(CURL_LIBS) $(CJSON_LIBS) $(LDFLAGS)
	@echo "✓ Built: aios-agent"

aios-input:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-input \
		services/aios-input/input.c \
		-Ihal -L$(LIB_DIR) -laios-hal \
		$(EVDEV_LIBS) $(LDFLAGS)
	@echo "✓ Built: aios-input"

aios-power:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-power \
		services/aios-power/power.c \
		-Ihal -L$(LIB_DIR) -laios-hal $(LDFLAGS)
	@echo "✓ Built: aios-power"

aios-notify:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-notify \
		services/aios-notify/notify.c $(LDFLAGS)
	@echo "✓ Built: aios-notify"

aios-voice:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-voice \
		services/aios-voice/voice.c \
		-Ihal -L$(LIB_DIR) -laios-hal \
		$(ALSA_LIBS) $(LDFLAGS)
	@echo "✓ Built: aios-voice"

aios-network:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-network \
		services/aios-network/network.c $(LDFLAGS)
	@echo "✓ Built: aios-network"

aios-display:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-display \
		services/aios-display/display.c $(LDFLAGS)
	@echo "✓ Built: aios-display"

# ==================== UI ====================
ui: dirs
ifdef GTK4_CFLAGS
	$(CC) $(CFLAGS) $(GTK4_CFLAGS) -o $(BIN_DIR)/aios-shell \
		ui/shell.c $(GTK4_LIBS) $(LDFLAGS)
	@echo "✓ Built: aios-shell"
else
	@echo "⚠ Skipped: aios-shell (GTK4 not found)"
endif

# ==================== Tools ====================
tools: dirs aios-cli aios-splash

aios-cli:
	$(CC) $(CFLAGS) -o $(BIN_DIR)/aios cli/cli.c -lreadline $(LDFLAGS) || \
	$(CC) $(CFLAGS) -o $(BIN_DIR)/aios cli/cli.c $(LDFLAGS)
	@echo "✓ Built: aios (CLI)"

aios-splash:
	$(CC) $(CFLAGS) -o $(SBIN_DIR)/aios-splash init/splash.c -lm $(LDFLAGS)
	@echo "✓ Built: aios-splash"

# ==================== Installation ====================
DESTDIR ?= 
PREFIX ?= /usr

install: all
	# Binaries
	install -d $(DESTDIR)$(PREFIX)/bin
	install -d $(DESTDIR)$(PREFIX)/sbin
	install -d $(DESTDIR)$(PREFIX)/lib
	install -m 755 $(BIN_DIR)/aios $(DESTDIR)$(PREFIX)/bin/
	-install -m 755 $(BIN_DIR)/aios-shell $(DESTDIR)$(PREFIX)/bin/ 2>/dev/null
	install -m 755 $(SBIN_DIR)/aios-* $(DESTDIR)$(PREFIX)/sbin/
	install -m 755 $(LIB_DIR)/libaios-hal.so $(DESTDIR)$(PREFIX)/lib/
	
	# Systemd services
	install -d $(DESTDIR)/etc/systemd/system
	install -m 644 systemd/*.service $(DESTDIR)/etc/systemd/system/
	
	# Configuration
	install -d $(DESTDIR)/etc/aios
	cp -r ../rootfs/etc/aios/* $(DESTDIR)/etc/aios/
	
	# Update library cache
	-ldconfig
	
	@echo ""
	@echo "✓ AI-OS installed to $(DESTDIR)$(PREFIX)"
	@echo "  Enable services: systemctl enable aios-agent aios-display"

# ==================== Clean ====================
clean:
	rm -rf $(BUILD_DIR)
	@echo "✓ Cleaned build directory"

# ==================== Dependencies Check ====================
deps:
	@echo "Checking build dependencies..."
	@echo -n "  gcc:      " && (which gcc >/dev/null && echo "✓") || echo "✗ MISSING"
	@echo -n "  pkg-config: " && (which pkg-config >/dev/null && echo "✓") || echo "✗ MISSING"
	@echo -n "  libcurl:  " && (pkg-config --exists libcurl && echo "✓") || echo "✗ MISSING (apt: libcurl4-openssl-dev)"
	@echo -n "  cjson:    " && (pkg-config --exists libcjson && echo "✓") || echo "✗ MISSING (apt: libcjson-dev)"
	@echo -n "  libevdev: " && (pkg-config --exists libevdev && echo "✓") || echo "✗ MISSING (apt: libevdev-dev)"
	@echo -n "  alsa:     " && (pkg-config --exists alsa && echo "✓") || echo "✗ MISSING (apt: libasound2-dev)"
	@echo -n "  gtk4:     " && (pkg-config --exists gtk4 && echo "✓") || echo "⚠ OPTIONAL (apt: libgtk-4-dev)"
	@echo -n "  readline: " && (test -f /usr/include/readline/readline.h && echo "✓") || echo "⚠ OPTIONAL (apt: libreadline-dev)"
	@echo ""
	@echo "Install all: sudo apt install build-essential pkg-config libcurl4-openssl-dev libcjson-dev libevdev-dev libasound2-dev libgtk-4-dev libreadline-dev"
