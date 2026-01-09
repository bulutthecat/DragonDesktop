#!/bin/bash

# Stop on any error
set -e

# 1. Check for Root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./install_dragon.sh)"
    exit 1
fi

# Get the actual username and Home Directory
REAL_USER=$SUDO_USER
if [ -z "$REAL_USER" ]; then
    echo "Could not detect actual user. Are you running under sudo?"
    exit 1
fi

# Get the absolute path to the user's home directory
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "Installing DragonDesktop for user: $REAL_USER (Home: $USER_HOME)"

# 2. Install System Dependencies
echo ">>> Updating Apt and installing dependencies..."
apt update
apt install -y \
    python3 \
    python3-pip \
    python3-xlib \
    python3-pil \
    python3-tk \
    git \
    xorg \
    x11-xserver-utils \
    network-manager-gnome \
    feh \
    firefox \
    polybar \
    brightnessctl \
    rofi \
    calc \
    fonts-font-awesome \
    jq \
    alacritty \
    picom \
    feh

# Note: 'pywal' is best installed via pip to get the latest version, 
# but apt is fine if the package exists in your distro. 
# Attempting pip install as user just in case:
sudo -u "$REAL_USER" pip3 install pywal --break-system-packages 2>/dev/null || true

# 3. Clone DragonDesktop Repository
INSTALL_DIR="/opt/dragondesktop"

echo ">>> Setting up directory: $INSTALL_DIR"
if [ -d "$INSTALL_DIR" ]; then
    echo "    Removing existing installation..."
    rm -rf "$INSTALL_DIR"
fi

echo ">>> Cloning DragonDesktop Repository..."
git clone https://github.com/bulutthecat/DragonDesktop.git "$INSTALL_DIR"

# 4. Fix Permissions for DragonDesktop
echo ">>> Setting permissions..."
chown -R $REAL_USER:$REAL_USER "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# =======================================================
# 4.5 Install Polybar Themes (Run as REAL_USER)
# =======================================================
echo ">>> Installing Polybar Themes (adi1090x)..."

# We run a block of commands as the real user to ensure 
# files end up in ~/.config and are owned by the user.
sudo -u "$REAL_USER" bash << EOF
    # Go to a temporary directory
    mkdir -p /tmp/polybar-install
    cd /tmp/polybar-install

    # Clone the repo
    if [ -d "polybar-themes" ]; then rm -rf polybar-themes; fi
    git clone --depth=1 https://github.com/adi1090x/polybar-themes.git
    cd polybar-themes

    chmod +x setup.sh

    # Run setup.sh and pipe "1" into it to select "Simple" style automatically
    # The script asks: [?] Select Option : 
    # We feed it '1'
    echo "1" | ./setup.sh

    # Clean up temp files
    cd ..
    rm -rf polybar-themes
EOF

echo ">>> Polybar themes installed successfully."
# =======================================================


# 5. Create Startup Wrapper
WRAPPER_PATH="/usr/local/bin/start-dragon.sh"
echo ">>> Creating startup wrapper at $WRAPPER_PATH"

# Note: In the wrapper below, we updated the Polybar launch command
cat > $WRAPPER_PATH <<EOF
#!/bin/bash

# Redirect stdout and stderr to a log file in the user's home
exec > /tmp/dragon-session.log 2>&1

echo "DragonDesktop Session Started: \$(date)"

# Set background color to avoid black screen
if command -v xsetroot &> /dev/null; then
    xsetroot -solid "#282A36"
fi

# 1. Kill existing Polybar instances
killall -q polybar

# Wait a moment for them to shut down
while pgrep -u \$UID -x polybar >/dev/null; do sleep 1; done

# 2. Launch Polybar with the installed theme
# We use 'hack' as requested in your example, but you can change --hack to --forest, --cuts, etc.
bash \$HOME/.config/polybar/launch.sh --hack &

# 3. Navigate to install dir so Python finds local imports
cd $INSTALL_DIR

# 4. Start the Window Manager (Unbuffered output)
/usr/bin/python3 -u main.py
EOF

chmod +x $WRAPPER_PATH

# 6. Register XSession
SESSION_FILE="/usr/share/xsessions/dragon.desktop"
echo ">>> Registering Desktop Session at $SESSION_FILE"

cat > $SESSION_FILE <<EOF
[Desktop Entry]
Name=DragonDesktop
Comment=Infinite Canvas Window Manager
Exec=$WRAPPER_PATH
Type=Application
DesktopNames=Dragon
EOF

echo "======================================================="
echo "INSTALLATION COMPLETE!"
echo "======================================================="
echo "1. Log out of your current session."
echo "2. Select 'DragonDesktop' at the login screen."
echo ""
echo "Note: Polybar 'Simple' style installed."
echo "      Default theme set to '--hack' in startup script."
echo "      Logs: /tmp/dragon-session.log"
