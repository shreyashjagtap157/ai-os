CC = gcc
CFLAGS = -Wall -Wextra -I. -pthread
LDFLAGS = -pthread

SERVICES = aios-display aios-input aios-network aios-notify aios-power aios-voice
BIN_DIR = bin

.PHONY: all clean $(SERVICES)

all: $(SERVICES)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

aios-display: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-display/display.c -o $(BIN_DIR)/aios-display $(LDFLAGS)

aios-input: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-input/input.c -o $(BIN_DIR)/aios-input $(LDFLAGS)

aios-network: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-network/network.c -o $(BIN_DIR)/aios-network $(LDFLAGS)

aios-notify: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-notify/notify.c -o $(BIN_DIR)/aios-notify $(LDFLAGS)

aios-power: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-power/power.c -o $(BIN_DIR)/aios-power $(LDFLAGS)

aios-voice: | $(BIN_DIR)
	$(CC) $(CFLAGS) aios-voice/voice.c -o $(BIN_DIR)/aios-voice $(LDFLAGS)

clean:
	rm -rf $(BIN_DIR)
