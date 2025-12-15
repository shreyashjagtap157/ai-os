#!/bin/bash
# Setup script for AI-OS Voice Service
# Downloads and installs Vosk model for offline speech recognition

MODEL_VERSION="vosk-model-small-en-us-0.15"
DOWNLOAD_URL="https://alphacephei.com/vosk/models/${MODEL_VERSION}.zip"
INSTALL_DIR="/usr/share/vosk-models"
TARGET_DIR="${INSTALL_DIR}/small-en-us"

# Check for root
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root"
  exit 1
fi

echo "AI-OS Voice Model Setup"
echo "======================="

# Install dependencies
echo "[*] checking dependencies..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3-pip python3-dev libasound2-dev espeak unzip wget
elif command -v pacman &> /dev/null; then
    pacman -S --noconfirm python-pip alsa-lib espeak unzip wget
fi

# Install Python packages
echo "[*] Installing Python packages..."
pip3 install vosk speechrecognition pyttsx3 pyaudio

# Create model directory
mkdir -p "${INSTALL_DIR}"

# Download model
if [ -d "${TARGET_DIR}" ]; then
    echo "[*] Model already exists at ${TARGET_DIR}"
else
    echo "[*] Downloading model from ${DOWNLOAD_URL}..."
    wget -q --show-progress "${DOWNLOAD_URL}" -O /tmp/model.zip
    
    echo "[*] Extracting model..."
    unzip -q /tmp/model.zip -d "${INSTALL_DIR}"
    mv "${INSTALL_DIR}/${MODEL_VERSION}" "${TARGET_DIR}"
    rm /tmp/model.zip
    
    echo "[+] Model installed successfully"
fi

# Verify permissions
chown -R root:root "${INSTALL_DIR}"
chmod -R 755 "${INSTALL_DIR}"

echo ""
echo "Setup complete! You can now start the voice service:"
echo "systemctl start aios-voice"
