#!/bin/bash
# Setup script for AI-OS prototype (no-op safe)

echo "[AI-OS] Setting up prototype directories and permissions..."
if ls userland/*.sh >/dev/null 2>&1; then
	chmod +x userland/*.sh
fi
echo "[AI-OS] Done."
