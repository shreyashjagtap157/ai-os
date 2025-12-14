#!/bin/bash
#
# AI-OS Post-image script for Raspberry Pi 4
# Creates bootable SD card image
#

BOARD_DIR="$(dirname $0)"
GENIMAGE_CFG="${BOARD_DIR}/genimage.cfg"
GENIMAGE_TMP="${BUILD_DIR}/genimage.tmp"

# Generate boot config
cat > "${BINARIES_DIR}/config.txt" << EOF
# AI-OS Raspberry Pi 4 Configuration
arm_64bit=1
enable_uart=1
dtoverlay=vc4-kms-v3d
max_framebuffers=2
disable_overscan=1
gpu_mem=256
EOF

cat > "${BINARIES_DIR}/cmdline.txt" << EOF
root=/dev/mmcblk0p2 rootwait console=ttyAMA0,115200 console=tty1 quiet
EOF

# Generate SD card image
rm -rf "${GENIMAGE_TMP}"

genimage \
    --rootpath "${TARGET_DIR}" \
    --tmppath "${GENIMAGE_TMP}" \
    --inputpath "${BINARIES_DIR}" \
    --outputpath "${BINARIES_DIR}" \
    --config "${GENIMAGE_CFG}"

exit $?
