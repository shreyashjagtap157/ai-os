#!/bin/bash
#
# AI-OS QEMU Emulator Script
# Run AI-OS in a virtual machine for testing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/buildroot/output/images"

# Default settings
MEMORY=2048
CPUS=2
GRAPHICS=true
NETWORK=true

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -m, --memory MB       Memory size (default: 2048)"
    echo "  -c, --cpus N          Number of CPUs (default: 2)"
    echo "  -n, --no-graphics     Run without graphics (serial console only)"
    echo "  -k, --kernel PATH     Use custom kernel"
    echo "  -r, --rootfs PATH     Use custom rootfs"
    echo "  -h, --help            Show this help"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--memory)
            MEMORY="$2"
            shift 2
            ;;
        -c|--cpus)
            CPUS="$2"
            shift 2
            ;;
        -n|--no-graphics)
            GRAPHICS=false
            shift
            ;;
        -k|--kernel)
            KERNEL="$2"
            shift 2
            ;;
        -r|--rootfs)
            ROOTFS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Set defaults if not specified
KERNEL="${KERNEL:-$BUILD_DIR/bzImage}"
ROOTFS="${ROOTFS:-$BUILD_DIR/rootfs.ext4}"

# Check files exist
if [ ! -f "$KERNEL" ]; then
    echo "Kernel not found: $KERNEL"
    echo "Build AI-OS first with: ./build/scripts/build.sh build x86_64"
    exit 1
fi

if [ ! -f "$ROOTFS" ]; then
    echo "Rootfs not found: $ROOTFS"
    exit 1
fi

echo "Starting AI-OS in QEMU..."
echo "  Kernel: $KERNEL"
echo "  Rootfs: $ROOTFS"
echo "  Memory: ${MEMORY}MB"
echo "  CPUs:   $CPUS"
echo ""

# Build QEMU command
QEMU_CMD=(
    qemu-system-x86_64
    -m "$MEMORY"
    -smp "$CPUS"
    -kernel "$KERNEL"
    -drive "file=$ROOTFS,format=raw,if=virtio"
    -append "root=/dev/vda console=ttyS0"
)

# Add KVM if available
if [ -e /dev/kvm ]; then
    QEMU_CMD+=(-enable-kvm -cpu host)
else
    echo "Note: KVM not available, running without acceleration"
fi

# Graphics
if [ "$GRAPHICS" = true ]; then
    QEMU_CMD+=(
        -device virtio-vga-gl
        -display gtk,gl=on
    )
else
    QEMU_CMD+=(-nographic)
fi

# Network
if [ "$NETWORK" = true ]; then
    QEMU_CMD+=(
        -device virtio-net-pci,netdev=net0
        -netdev user,id=net0,hostfwd=tcp::2222-:22
    )
fi

# Input devices
QEMU_CMD+=(
    -device usb-ehci
    -device usb-kbd
    -device usb-mouse
)

# Audio
QEMU_CMD+=(
    -device intel-hda
    -device hda-duplex
)

# Run QEMU
exec "${QEMU_CMD[@]}"
