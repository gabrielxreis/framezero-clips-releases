#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/installers/FrameZero_Installer_1.0_Mac.command" 2>/dev/null || true
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
exec "$DIR/installers/FrameZero_Installer_1.0_Mac.command"
