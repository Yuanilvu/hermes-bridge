#!/bin/bash
# Hermes Bridge launcher — detects XAUTHORITY for Wayland+XWayland
# Called by systemd; sources .env then detects the X11 auth cookie.

# Load .env
set -a
source /home/yuan/hermes-bridge/.env
set +a

# Detect XAUTHORITY (the random suffix changes per login on Wayland/XWayland)
XAUTH_FILE=$(ls /run/user/1000/.mutter-Xwaylandauth.* 2>/dev/null | head -1)
if [ -n "$XAUTH_FILE" ] && [ -r "$XAUTH_FILE" ]; then
    export XAUTHORITY="$XAUTH_FILE"
fi

# Ensure these are set for cua-driver
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"

# Start cua-driver daemon for stateful operations (mouse-down/drag/up, gaming)
CUA_DRIVER="$HOME/.local/bin/cua-driver"
if [ -x "$CUA_DRIVER" ]; then
    # Kill any stale daemon first, then start fresh
    "$CUA_DRIVER" stop 2>/dev/null || true
    "$CUA_DRIVER" serve --no-overlay --cursor-id hermes-bridge &
    # Wait for daemon socket to be ready (up to 10 seconds)
    for i in $(seq 1 20); do
        if "$CUA_DRIVER" status 2>/dev/null | grep -q "is running"; then
            break
        fi
        sleep 0.5
    done
fi

cd /home/yuan/hermes-bridge
exec /home/yuan/hermes-bridge/.venv/bin/uvicorn server:app --host "${BRIDGE_HOST:-127.0.0.1}" --port "${BRIDGE_PORT:-8199}"
