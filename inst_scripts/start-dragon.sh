#!/bin/bash  
#  
# DragonDesktop Session Launcher  
# Handles Polybar, Picom, Settings Daemons, and Window Manager startup  
#  
# Location : /usr/local/bin/start-dragon.sh
#
# ============================================  
# Configuration  
# ============================================  
INSTALL_DIR="${INSTALL_DIR:-/opt/dragondesktop}"  
LOG_FILE="/tmp/dragon-session.log"  
PICOM_CONFIG="$HOME/opt/dragondesktop/app_configs/picom.conf"  
PICOM_LOG="/tmp/picom.log"  
  
# ============================================  
# Logging Setup  
# ============================================  
exec > "$LOG_FILE" 2>&1  
echo "========================================"  
echo "DragonDesktop Session Started: $(date)"  
echo "========================================"  
echo "Install Directory: $INSTALL_DIR"  
echo "User: $USER (UID: $UID)"  
echo "Display: $DISPLAY"  
echo ""  
  
# ============================================  
# Helper Functions  
# ============================================  
  
log_info() {  
    echo "[INFO] $1"  
}  
  
log_warn() {  
    echo "[WARN] $1"  
}  
  
log_error() {  
    echo "[ERROR] $1"  
}  
  
check_command() {  
    if command -v "$1" &> /dev/null; then  
        log_info "✓ Found: $1"  
        return 0  
    else  
        log_warn "✗ Missing: $1"  
        return 1  
    fi  
}  
  
kill_process() {  
    local proc_name=$1  
    local timeout=${2:-5}  
      
    if pgrep -x "$proc_name" > /dev/null; then  
        log_info "Killing existing $proc_name instances..."  
        killall -q "$proc_name"  
          
        # Wait for process to die  
        local count=0  
        while pgrep -u $UID -x "$proc_name" >/dev/null; do  
            sleep 1  
            count=$((count + 1))  
            if [ $count -ge $timeout ]; then  
                log_warn "$proc_name didn't exit gracefully, forcing..."  
                killall -9 "$proc_name" 2>/dev/null  
                sleep 1  
                break  
            fi  
        done  
          
        if pgrep -x "$proc_name" > /dev/null; then  
            log_error "Failed to kill $proc_name"  
            return 1  
        else  
            log_info "✓ $proc_name terminated"  
            return 0  
        fi  
    else  
        log_info "$proc_name not running"  
        return 0  
    fi  
}  
  
# ============================================  
# Environment Setup  
# ============================================  
  
log_info "Setting up environment..."  
  
# Set background color to avoid black screen flashing  
if check_command xsetroot; then  
    xsetroot -solid "#282A36"  
    log_info "✓ Background color set"  
else  
    log_warn "xsetroot not found, skipping background setup"  
fi  
  
# Ensure X11 cursor is visible (some WMs hide it)  
if check_command xsetroot; then  
    xsetroot -cursor_name left_ptr  
fi  
  
# ============================================  
# Cleanup Existing Processes  
# ============================================  
  
log_info "Cleaning up existing processes..."  
  
# Kill old WM instances (python processes running main.py)  
if pgrep -f "python.*main.py" > /dev/null; then  
    log_info "Killing existing DragonDesktop instances..."  
    pkill -9 -f "python.*main.py"  
    sleep 1  
fi  
  
# Kill Polybar  
kill_process polybar 5  
  
# Kill Picom (we'll restart it fresh)  
kill_process picom 5

# Kill Settings Daemons (Refresh them)
kill_process xfsettingsd 2
kill_process xfce4-power-manager 2
  
# ============================================
# Start Settings Daemons (XFCE Integration)
# ============================================

log_info "Starting Settings Daemons..."

# 1. Ensure D-Bus is running (Required for xfconfd to auto-start)
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    log_warn "D-Bus address not set. Attempting to launch dbus-launch..."
    if check_command dbus-launch; then
        eval $(dbus-launch --sh-syntax --exit-with-session)
        log_info "✓ D-Bus session started: $DBUS_SESSION_BUS_ADDRESS"
    else
        log_error "✗ dbus-launch not found. Settings daemons may fail."
    fi
fi

# 2. Start xfsettingsd (Applies themes, fonts, settings)
if check_command xfsettingsd; then
    xfsettingsd --daemon &
    log_info "✓ xfsettingsd started (Theme/Font daemon)"
else
    log_warn "✗ xfsettingsd not found. Themes/Settings will not apply."
fi

# 3. Start Power Manager (Optional but recommended)
if check_command xfce4-power-manager; then
    xfce4-power-manager &
    log_info "✓ xfce4-power-manager started"
else
    log_warn "✗ xfce4-power-manager not found."
fi

# ============================================  
# Start Picom (Compositor)  
# ============================================  
  
log_info "Starting compositor (picom)..."  
  start_picom() {  
    if ! check_command picom; then  
        log_warn "Picom not installed - falling back to CPU rendering"  
        log_warn "To install: sudo apt install picom (Debian/Ubuntu)"  
        log_warn "           sudo pacman -S picom (Arch)"  
        return 1  
    fi  
      
    # Check if config exists  
    if [ ! -f "$PICOM_CONFIG" ]; then  
        log_warn "Picom config not found: $PICOM_CONFIG"  
        log_info "Creating default picom config..."  
          
        mkdir -p "$(dirname "$PICOM_CONFIG")"  
          
        cat > "$PICOM_CONFIG" << 'EOF'
# DragonDesktop Default Picom Config  
backend = "glx";  
vsync = true;  
use-damage = true;  
  
# Shadows  
shadow = true;  
shadow-radius = 12;  
shadow-opacity = 0.5;  
shadow-offset-x = -12;  
shadow-offset-y = -12;  
  
# Fading (disabled for performance during zoom)  
fading = false;  
  
# Opacity  
inactive-opacity = 0.95;  
active-opacity = 1.0;  
  
# Performance  
unredir-if-possible = true;  
detect-rounded-corners = true;  
detect-client-opacity = true;  
detect-transient = true;  
detect-client-leader = true;  
  
# Window types  
wintypes: {  
    tooltip = { fade = true; shadow = false; opacity = 0.95; };  
    dock = { shadow = false; };  
    dnd = { shadow = false; };  
};  
EOF
        log_info "✓ Created default config at $PICOM_CONFIG"  
    fi  
      
    # Start picom  
    log_info "Launching picom with config: $PICOM_CONFIG"  
    
    picom --config "$PICOM_CONFIG" --log-file "$PICOM_LOG" --log-level=INFO --daemon 2>&1

    # Wait for picom to register (up to 5 seconds)
    log_info "Waiting for compositor registration..."
    local count=0
    while [ $count -lt 10 ]; do
        if xprop -root _NET_WM_CM_S0 2>/dev/null | grep -q "window id"; then
            log_info "✓ Picom registered successfully"
            return 0
        fi
        sleep 0.5
        count=$((count + 1))
    done

    # If we get here, it timed out or failed
    if pgrep -x picom > /dev/null; then
        log_warn "Picom is running (PID: $(pgrep -x picom)) but failed to register with X11."
        log_warn "Check /tmp/picom.log for errors."
        # Don't return 1, because it IS running, just maybe sluggish or bugged
        return 0 
    else
        log_error "Picom failed to start"
        if [ -f "$PICOM_LOG" ]; then
            log_error "Picom log tail:"
            tail -n 5 "$PICOM_LOG" | while read line; do echo "  | $line"; done
        fi
        return 1
    fi
}
  
# Try to start picom (non-fatal if it fails)  
if start_picom; then  
    log_info "✓ Compositor mode enabled"  
else  
    log_warn "⚠ Compositor disabled - using CPU rendering mode"  
    log_warn "  Performance may be reduced (no VSync, possible tearing)"  
fi  
  
# ============================================  
# Start Polybar  
# ============================================  
  
log_info "Starting Polybar..."  
  
start_polybar() {  
    local polybar_launch="$HOME/.config/polybar/launch.sh"  
      
    if [ ! -f "$polybar_launch" ]; then  
        log_warn "Polybar launch script not found: $polybar_launch"  
        return 1  
    fi  
      
    if ! check_command polybar; then  
        log_warn "Polybar not installed"  
        return 1  
    fi  
      
    log_info "Executing: bash $polybar_launch --hack"  
    bash "$polybar_launch" --hack &  
      
    # Wait a moment and verify  
    sleep 1  
      
    if pgrep -x polybar > /dev/null; then  
        log_info "✓ Polybar started successfully"  
        return 0  
    else  
        log_error "Polybar failed to start"  
        return 1  
    fi  
}  
  
if start_polybar; then  
    :  # Success  
else  
    log_warn "⚠ Polybar startup failed - continuing without panel"  
fi  
  
# ============================================  
# Start Window Manager  
# ============================================  
  
log_info "Starting DragonDesktop Window Manager..."  
  
# Verify install directory exists  
if [ ! -d "$INSTALL_DIR" ]; then  
    log_error "Install directory not found: $INSTALL_DIR"  
    log_error "Please set INSTALL_DIR environment variable correctly"  
    exit 1  
fi  
  
# Navigate to install directory so Python finds local imports  
cd "$INSTALL_DIR" || {  
    log_error "Failed to cd to $INSTALL_DIR"  
    exit 1  
}  
  
# Verify main.py exists  
if [ ! -f "main.py" ]; then  
    log_error "main.py not found in $INSTALL_DIR"  
    log_error "Contents of $INSTALL_DIR:"  
    ls -la "$INSTALL_DIR" | head -n 20  
    exit 1  
fi  
  
# Check Python version  
if check_command python3; then  
    PYTHON_VERSION=$(python3 --version 2>&1)  
    log_info "Python version: $PYTHON_VERSION"  
else  
    log_error "Python3 not found"  
    exit 1  
fi  
  
# Verify required Python modules  
log_info "Checking Python dependencies..."  
python3 -c "import Xlib" 2>/dev/null && log_info "✓ python-xlib installed" || log_warn "✗ python-xlib missing"  
python3 -c "import PIL" 2>/dev/null && log_info "✓ Pillow installed" || log_warn "✗ Pillow missing"  
  
# Start the Window Manager with unbuffered output  
log_info "========================================"  
log_info "Launching Window Manager..."  
log_info "========================================"  
echo ""  
  
# Use exec to replace the shell with Python (cleaner process tree)  
# -u flag: unbuffered stdout/stderr for real-time logging  
exec /usr/bin/python3 -u main.py  
  
# If we reach here, exec failed  
log_error "Failed to start window manager"  
exit 1