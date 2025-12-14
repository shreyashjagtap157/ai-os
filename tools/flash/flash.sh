#!/bin/bash
#
# AI-OS Flash Tool
# Flash AI-OS image to USB drive or SD card
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/buildroot/output/images"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "Usage: $0 <device> [image]"
    echo ""
    echo "Arguments:"
    echo "  device    Target device (e.g., /dev/sdc, /dev/mmcblk0)"
    echo "  image     Optional image file (default: auto-detect from build)"
    echo ""
    echo "Examples:"
    echo "  $0 /dev/sdc                 # Flash to USB drive"
    echo "  $0 /dev/mmcblk0             # Flash to SD card"
    echo "  $0 /dev/sdc my-image.img    # Flash specific image"
}

list_devices() {
    echo "Available devices:"
    echo ""
    lsblk -d -o NAME,SIZE,MODEL,TRAN | grep -v "^loop"
    echo ""
    echo "Use /dev/<NAME> as the device argument"
}

check_device() {
    local device=$1
    
    if [ ! -b "$device" ]; then
        error "Device not found: $device"
        exit 1
    fi
    
    # Check if it's a system device
    local root_device=$(df / | tail -1 | awk '{print $1}' | sed 's/[0-9]*$//')
    if [[ "$device" == "$root_device"* ]]; then
        error "Cannot flash to system device!"
        exit 1
    fi
    
    # Check if mounted
    if mount | grep -q "^$device"; then
        warn "Device has mounted partitions. Unmounting..."
        sudo umount ${device}* 2>/dev/null || true
    fi
}

find_image() {
    # Try various image locations
    local images=(
        "$BUILD_DIR/sdcard.img"
        "$BUILD_DIR/disk.img"
        "$BUILD_DIR/aios.img"
    )
    
    for img in "${images[@]}"; do
        if [ -f "$img" ]; then
            echo "$img"
            return 0
        fi
    done
    
    # Try to create from rootfs
    if [ -f "$BUILD_DIR/rootfs.ext4" ]; then
        log "Creating disk image from rootfs..."
        create_image "$BUILD_DIR/aios.img"
        echo "$BUILD_DIR/aios.img"
        return 0
    fi
    
    return 1
}

create_image() {
    local output=$1
    local rootfs="$BUILD_DIR/rootfs.ext4"
    local kernel="$BUILD_DIR/bzImage"
    
    if [ ! -f "$rootfs" ]; then
        error "Rootfs not found"
        exit 1
    fi
    
    local rootfs_size=$(stat -f%z "$rootfs" 2>/dev/null || stat -c%s "$rootfs")
    local image_size=$((rootfs_size + 512*1024*1024))  # Add 512MB for boot + overhead
    
    log "Creating ${image_size} byte image..."
    
    dd if=/dev/zero of="$output" bs=1M count=$((image_size / 1048576)) status=progress
    
    # Create partition table
    parted -s "$output" mklabel gpt
    parted -s "$output" mkpart primary fat32 1MiB 257MiB
    parted -s "$output" mkpart primary ext4 257MiB 100%
    parted -s "$output" set 1 boot on
    
    # Setup loop device
    local loop=$(sudo losetup -f --show -P "$output")
    
    # Format partitions
    sudo mkfs.vfat -F 32 "${loop}p1"
    sudo mkfs.ext4 -F "${loop}p2"
    
    # Mount and copy
    local boot_mount=$(mktemp -d)
    local root_mount=$(mktemp -d)
    
    sudo mount "${loop}p1" "$boot_mount"
    sudo mount "${loop}p2" "$root_mount"
    
    # Copy kernel
    if [ -f "$kernel" ]; then
        sudo cp "$kernel" "$boot_mount/vmlinuz"
    fi
    
    # Copy rootfs
    sudo cp "$rootfs" "$root_mount/rootfs.ext4"
    
    # Install bootloader (GRUB for UEFI)
    sudo grub-install --target=x86_64-efi --efi-directory="$boot_mount" --boot-directory="$boot_mount" --removable 2>/dev/null || true
    
    # Create grub config
    sudo tee "$boot_mount/grub/grub.cfg" > /dev/null << 'EOF'
set timeout=3
set default=0

menuentry "AI-OS" {
    linux /vmlinuz root=/dev/sda2 quiet
}
EOF
    
    # Cleanup
    sudo umount "$boot_mount"
    sudo umount "$root_mount"
    sudo losetup -d "$loop"
    rmdir "$boot_mount" "$root_mount"
    
    log "Image created: $output"
}

flash() {
    local device=$1
    local image=$2
    
    echo ""
    warn "This will ERASE ALL DATA on $device"
    echo ""
    lsblk "$device"
    echo ""
    read -p "Are you sure you want to continue? (yes/no) " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Cancelled"
        exit 0
    fi
    
    log "Flashing $image to $device..."
    
    sudo dd if="$image" of="$device" bs=4M status=progress conv=fsync
    sync
    
    log "Flash complete!"
    echo ""
    log "You can now boot from $device"
}

# Main
if [ $# -lt 1 ]; then
    usage
    echo ""
    list_devices
    exit 1
fi

DEVICE=$1
IMAGE=${2:-}

check_device "$DEVICE"

if [ -z "$IMAGE" ]; then
    IMAGE=$(find_image) || {
        error "No image found. Build AI-OS first."
        exit 1
    }
fi

if [ ! -f "$IMAGE" ]; then
    error "Image not found: $IMAGE"
    exit 1
fi

flash "$DEVICE" "$IMAGE"
