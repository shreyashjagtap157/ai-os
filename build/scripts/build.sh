#!/bin/bash
#
# AI-OS Build System
# Complete build script for creating bootable AI-OS images
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
OUTPUT_DIR="$BUILD_DIR/output"
BUILDROOT_DIR="$BUILD_DIR/buildroot"
BUILDROOT_VERSION="2024.02"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_banner() {
    echo ""
    echo "    _    ___       ___  ____  "
    echo "   / \  |_ _|     / _ \/ ___| "
    echo "  / _ \  | |_____| | | \___ \ "
    echo " / ___ \ | |_____| |_| |___) |"
    echo "/_/   \_\___|     \___/|____/ "
    echo ""
    echo "AI-OS Build System v1.0.0"
    echo ""
}

check_dependencies() {
    log_info "Checking build dependencies..."
    
    local missing=()
    
    for cmd in wget git make gcc g++ python3 rsync cpio unzip bc; do
        if ! command -v $cmd &> /dev/null; then
            missing+=($cmd)
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Install with: sudo apt-get install build-essential git wget cpio unzip rsync bc python3"
        exit 1
    fi
    
    log_success "All dependencies found"
}

download_buildroot() {
    if [ -d "$BUILDROOT_DIR" ]; then
        log_info "Buildroot already downloaded"
        return
    fi
    
    log_info "Downloading Buildroot $BUILDROOT_VERSION..."
    
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    
    wget -q "https://buildroot.org/downloads/buildroot-$BUILDROOT_VERSION.tar.gz" -O buildroot.tar.gz
    tar xf buildroot.tar.gz
    mv "buildroot-$BUILDROOT_VERSION" buildroot
    rm buildroot.tar.gz
    
    log_success "Buildroot downloaded"
}

select_config() {
    local target=$1
    
    case $target in
        x86_64|pc)
            CONFIG="aios_x86_64_defconfig"
            ;;
        rpi4|raspberry)
            CONFIG="aios_rpi4_defconfig"
            ;;
        arm64|aarch64)
            CONFIG="aios_arm64_defconfig"
            ;;
        qemu|test)
            CONFIG="aios_x86_64_defconfig"
            ;;
        *)
            log_error "Unknown target: $target"
            log_info "Available targets: x86_64, rpi4, arm64, qemu"
            exit 1
            ;;
    esac
    
    log_info "Using configuration: $CONFIG"
}

configure_buildroot() {
    log_info "Configuring Buildroot..."
    
    cd "$BUILDROOT_DIR"
    
    # Copy configuration
    cp "$BUILD_DIR/configs/$CONFIG" .config
    
    # Set external tree
    echo "BR2_EXTERNAL=$BUILD_DIR/external" >> .config
    
    # Apply configuration
    make olddefconfig
    
    log_success "Buildroot configured"
}

install_aios_components() {
    log_info "Installing AI-OS components..."
    
    local STAGING="$BUILDROOT_DIR/output/target"
    
    # Create directories
    mkdir -p "$STAGING/usr/lib/aios/services/agent"
    mkdir -p "$STAGING/usr/lib/aios/services/display"
    mkdir -p "$STAGING/usr/lib/aios/services/voice"
    mkdir -p "$STAGING/usr/lib/aios/services/input"
    mkdir -p "$STAGING/usr/lib/aios/services/power"
    mkdir -p "$STAGING/usr/lib/aios/services/notify"
    mkdir -p "$STAGING/usr/lib/aios/services/network"
    mkdir -p "$STAGING/usr/lib/aios/ui"
    mkdir -p "$STAGING/usr/lib/aios/apps"
    mkdir -p "$STAGING/usr/lib/aios/plugins"
    mkdir -p "$STAGING/usr/lib/aios/security"
    mkdir -p "$STAGING/usr/lib/aios/theming"
    mkdir -p "$STAGING/usr/bin"
    mkdir -p "$STAGING/etc/aios"
    mkdir -p "$STAGING/etc/systemd/system"
    mkdir -p "$STAGING/var/lib/aios"
    mkdir -p "$STAGING/var/log/aios"
    
    # Copy services
    cp "$PROJECT_ROOT/core/services/aios-agent/agent.py" "$STAGING/usr/lib/aios/services/agent/"
    cp "$PROJECT_ROOT/core/services/aios-display/compositor.py" "$STAGING/usr/lib/aios/services/display/"
    cp "$PROJECT_ROOT/core/services/aios-voice/voice.py" "$STAGING/usr/lib/aios/services/voice/"
    cp "$PROJECT_ROOT/core/services/aios-input/input.py" "$STAGING/usr/lib/aios/services/input/"
    cp "$PROJECT_ROOT/core/services/aios-power/power.py" "$STAGING/usr/lib/aios/services/power/"
    cp "$PROJECT_ROOT/core/services/aios-notify/notify.py" "$STAGING/usr/lib/aios/services/notify/"
    cp "$PROJECT_ROOT/core/services/aios-network/network.py" "$STAGING/usr/lib/aios/services/network/"
    
    # Copy UI
    cp "$PROJECT_ROOT/core/ui/shell.py" "$STAGING/usr/lib/aios/ui/"
    
    # Copy other modules
    cp "$PROJECT_ROOT/core/apps/framework.py" "$STAGING/usr/lib/aios/apps/"
    cp "$PROJECT_ROOT/core/plugins/plugin_manager.py" "$STAGING/usr/lib/aios/plugins/"
    cp "$PROJECT_ROOT/core/security/security.py" "$STAGING/usr/lib/aios/security/"
    cp "$PROJECT_ROOT/core/theming/theme_manager.py" "$STAGING/usr/lib/aios/theming/"
    
    # Copy CLI
    cp "$PROJECT_ROOT/core/cli/aios" "$STAGING/usr/bin/aios"
    chmod +x "$STAGING/usr/bin/aios"
    
    # Copy init
    if [ -f "$PROJECT_ROOT/core/init/init" ]; then
        cp "$PROJECT_ROOT/core/init/init" "$STAGING/init"
        chmod +x "$STAGING/init"
    fi
    
    # Copy systemd services
    cp "$PROJECT_ROOT/core/services/aios-agent/aios-agent.service" "$STAGING/etc/systemd/system/"
    cp "$PROJECT_ROOT/core/services/aios-display/aios-display.service" "$STAGING/etc/systemd/system/"
    cp "$PROJECT_ROOT/core/services/aios-voice/aios-voice.service" "$STAGING/etc/systemd/system/"
    cp "$PROJECT_ROOT/core/services/aios-input/aios-input.service" "$STAGING/etc/systemd/system/"
    cp "$PROJECT_ROOT/core/services/aios-power/aios-power.service" "$STAGING/etc/systemd/system/"
    cp "$PROJECT_ROOT/core/services/aios-notify/aios-notify.service" "$STAGING/etc/systemd/system/"
    
    # Copy configs
    cp -r "$PROJECT_ROOT/rootfs/etc/aios/"* "$STAGING/etc/aios/" 2>/dev/null || true
    
    # Enable services (create symlinks)
    mkdir -p "$STAGING/etc/systemd/system/multi-user.target.wants"
    ln -sf ../aios-agent.service "$STAGING/etc/systemd/system/multi-user.target.wants/"
    ln -sf ../aios-voice.service "$STAGING/etc/systemd/system/multi-user.target.wants/"
    ln -sf ../aios-input.service "$STAGING/etc/systemd/system/multi-user.target.wants/"
    ln -sf ../aios-power.service "$STAGING/etc/systemd/system/multi-user.target.wants/"
    ln -sf ../aios-notify.service "$STAGING/etc/systemd/system/multi-user.target.wants/"
    
    mkdir -p "$STAGING/etc/systemd/system/graphical.target.wants"
    ln -sf ../aios-display.service "$STAGING/etc/systemd/system/graphical.target.wants/"
    
    log_success "AI-OS components installed"
}

build() {
    log_info "Building AI-OS..."
    
    cd "$BUILDROOT_DIR"
    
    # Build with parallel jobs
    local JOBS=$(nproc)
    make -j$JOBS
    
    log_success "Build complete!"
}

create_iso() {
    log_info "Creating ISO image..."
    
    local ISO_DIR="$OUTPUT_DIR/iso"
    mkdir -p "$ISO_DIR/boot/grub"
    
    # Copy kernel and rootfs
    cp "$BUILDROOT_DIR/output/images/bzImage" "$ISO_DIR/boot/"
    cp "$BUILDROOT_DIR/output/images/rootfs.cpio.gz" "$ISO_DIR/boot/"
    
    # Create GRUB config
    cat > "$ISO_DIR/boot/grub/grub.cfg" << 'EOF'
set timeout=5
set default=0

menuentry "AI-OS" {
    linux /boot/bzImage quiet
    initrd /boot/rootfs.cpio.gz
}

menuentry "AI-OS (Debug)" {
    linux /boot/bzImage debug
    initrd /boot/rootfs.cpio.gz
}
EOF
    
    # Create ISO
    grub-mkrescue -o "$OUTPUT_DIR/aios.iso" "$ISO_DIR" 2>/dev/null || {
        log_warn "grub-mkrescue not available, skipping ISO creation"
        return
    }
    
    log_success "Created: $OUTPUT_DIR/aios.iso"
}

run_qemu() {
    log_info "Starting QEMU..."
    
    local KERNEL="$BUILDROOT_DIR/output/images/bzImage"
    local ROOTFS="$BUILDROOT_DIR/output/images/rootfs.ext4"
    
    if [ ! -f "$KERNEL" ] || [ ! -f "$ROOTFS" ]; then
        log_error "Build images not found. Run 'build' first."
        exit 1
    fi
    
    qemu-system-x86_64 \
        -enable-kvm \
        -m 2048 \
        -smp 2 \
        -kernel "$KERNEL" \
        -drive file="$ROOTFS",format=raw \
        -append "root=/dev/sda console=ttyS0" \
        -device virtio-net-pci,netdev=net0 \
        -netdev user,id=net0 \
        -device virtio-vga \
        -device usb-ehci \
        -device usb-kbd \
        -device usb-mouse \
        -nographic
}

flash_device() {
    local DEVICE=$1
    
    if [ -z "$DEVICE" ]; then
        log_error "Usage: $0 flash /dev/sdX"
        exit 1
    fi
    
    local IMAGE="$BUILDROOT_DIR/output/images/sdcard.img"
    
    if [ ! -f "$IMAGE" ]; then
        log_error "Image not found: $IMAGE"
        exit 1
    fi
    
    log_warn "This will erase all data on $DEVICE"
    read -p "Continue? (y/N) " confirm
    
    if [ "$confirm" != "y" ]; then
        log_info "Cancelled"
        exit 0
    fi
    
    log_info "Flashing to $DEVICE..."
    sudo dd if="$IMAGE" of="$DEVICE" bs=4M status=progress conv=fsync
    sync
    
    log_success "Flash complete!"
}

clean() {
    log_info "Cleaning build artifacts..."
    
    if [ -d "$BUILDROOT_DIR" ]; then
        cd "$BUILDROOT_DIR"
        make clean
    fi
    
    rm -rf "$OUTPUT_DIR"
    
    log_success "Clean complete"
}

distclean() {
    log_info "Full clean (removing Buildroot)..."
    
    rm -rf "$BUILDROOT_DIR"
    rm -rf "$OUTPUT_DIR"
    
    log_success "Distclean complete"
}

usage() {
    echo "Usage: $0 <command> [target] [options]"
    echo ""
    echo "Commands:"
    echo "  build <target>    Build AI-OS for target (x86_64, rpi4, arm64)"
    echo "  qemu              Build and run in QEMU"
    echo "  iso               Create bootable ISO"
    echo "  flash <device>    Flash image to device"
    echo "  clean             Clean build artifacts"
    echo "  distclean         Remove everything including Buildroot"
    echo "  deps              Check/install dependencies"
    echo ""
    echo "Targets:"
    echo "  x86_64            64-bit PC"
    echo "  rpi4              Raspberry Pi 4"
    echo "  arm64             Generic ARM64"
    echo ""
    echo "Examples:"
    echo "  $0 build x86_64   # Build for PC"
    echo "  $0 qemu           # Test in QEMU"
    echo "  $0 flash /dev/sdc # Flash to USB drive"
}

# Main
show_banner

case ${1:-} in
    build)
        check_dependencies
        download_buildroot
        select_config "${2:-x86_64}"
        configure_buildroot
        build
        install_aios_components
        log_success "Build complete! Output in $BUILDROOT_DIR/output/images/"
        ;;
    
    qemu)
        check_dependencies
        download_buildroot
        select_config "x86_64"
        configure_buildroot
        build
        install_aios_components
        run_qemu
        ;;
    
    iso)
        create_iso
        ;;
    
    flash)
        flash_device "$2"
        ;;
    
    clean)
        clean
        ;;
    
    distclean)
        distclean
        ;;
    
    deps)
        check_dependencies
        ;;
    
    help|--help|-h)
        usage
        ;;
    
    *)
        usage
        exit 1
        ;;
esac
