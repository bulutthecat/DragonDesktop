```
______                                 _           _    _              
|  _  \                               | |         | |  | |             
| | | |_ __ __ _  __ _  ___  _ __   __| | ___  ___| | _| |_ ___  _ __  
| | | | '__/ _` |/ _` |/ _ \| '_ \ / _` |/ _ \/ __| |/ / __/ _ \| '_ \ 
| |/ /| | | (_| | (_| | (_) | | | | (_| |  __/\__ \   <| || (_) | |_) |
|___/ |_|  \__,_|\__, |\___/|_| |_|\__,_|\___||___/_|\_\\__\___/| .__/ 
                  __/ |                                         | |    
                 |___/                                          |_|
```

A next-generation X11 window manager with infinite canvas, semantic zoom, and dynamic rendering modes.

## Overview

DragonDesktop transforms the traditional desktop metaphor into an infinite 2D workspace where windows exist in "world coordinates" and can be positioned anywhere. Navigate freely with camera panning and zooming, save workspace layouts, and switch between CPU and compositor-accelerated rendering modes.

**Key Features**


- Infinite Canvas: Place windows anywhere in unlimited 2D space
- Semantic Zoom: Windows intelligently hide/show content based on zoom level
- CPU and GPU rendering modes
- ICCCM/EWMH Compliant: Full protocol support for modern applications
- Dynamic Theming: Per-application color schemes generated from app names
- Workspace Memory: Save and recall camera positions (F1-F4)
- Alt-Tab Cycling: Traditional window switching in infinite space

(insert gif here)

## Installation ##

**Automatic Installation (Recommended)**

```
# Download and run the installer  
wget https://github.com/bulutthecat/DragonDesktop/releases/download/InfDev/install_dragon.sh  
chmod +x install_dragon.sh  
sudo ./install_dragon.sh  
```

The installer will:

1. Install all system dependencies
2. Clone the repository to /opt/dragondesktop
3. Set up Polybar themes
4. Register DragonDesktop as an X session
5. Create startup wrapper scripts

**Manual Installation**

```
# Install dependencies  
sudo apt update  
sudo apt install -y python3 python3-pip python3-xlib python3-pil \  
    xorg x11-xserver-utils feh firefox polybar picom alacritty rofi  
  
# Clone repository  
git clone https://github.com/bulutthecat/DragonDesktop.git  
cd DragonDesktop  
  
# Install Python dependencies  
pip3 install pywal --break-system-packages  
  
# Copy configuration  
mkdir -p ~/.config/dragondesktop  
cp config.json ~/.config/dragondesktop/  
```

## Usage

Starting DragonDesktop

1. Log out of your current session
2. At the login screen, select DragonDesktop from the session menu
3. Log in with your credentials

**Basic Navigation**

<table style="margin-left: auto; margin-right: auto; text-align: center;">
  <thead>
    <tr>
      <th style="text-align: center;">Action</th>
      <th style="text-align: center;">Keybinding</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Pan camera</td>
      <td><kbd>Super</kbd> + Left Mouse Drag</td>
    </tr>
    <tr>
      <td>Zoom in/out</td>
      <td><kbd>Super</kbd> + Scroll Wheel</td>
    </tr>
    <tr>
      <td>Move window</td>
      <td>Left Mouse Drag (on titlebar)</td>
    </tr>
    <tr>
      <td>Resize window</td>
      <td>Left Mouse Drag (bottom-right corner)</td>
    </tr>
    <tr>
      <td>Fullscreen toggle</td>
      <td>Click maximize button or <kbd>F11</kbd></td>
    </tr>
    <tr>
      <td>Close window</td>
      <td><kbd>Alt</kbd> + <kbd>F4</kbd> or click close button</td>
    </tr>
  </tbody>
</table>

Launch applications with the built-in command bar:

1. Press `Super + Space` to open
2. Type command or alias
3. Press `Enter` to execute
4. Press `Escape` to cancel

**Default Aliases** (edit in `config.json`):

```
{  
  "aliases": {  
    "term": "alacritty",  
    "rofi": "rofi -show run",  
    "settings": "xfce4-settings-manager"  
  }  
}  
```

**Workspace Management**

<table style="margin-left: auto; margin-right: auto; text-align: center;">
  <thead>
    <tr>
      <th style="text-align: center;">Action</th>
      <th style="text-align: center;">Keybinding</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Save camera position 1-4</td>
      <td><kbd>Super</kbd> + <kbd>Ctrl</kbd> + <kbd>F1</kbd>-<kbd>F4</kbd></td>
    </tr>
    <tr>
      <td>Jump to position 1-4</td>
      <td><kbd>Super</kbd> + <kbd>F1</kbd>-<kbd>F4</kbd></td>
    </tr>
    <tr>
      <td>Cycle windows forward</td>
      <td><kbd>Alt</kbd> + <kbd>Tab</kbd></td>
    </tr>
    <tr>
      <td>Cycle windows backward</td>
      <td><kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>Tab</kbd></td>
    </tr>
  </tbody>
</table>

## Configuration

**Main Config (`config.json`)**

Located at `/opt/dragondesktop/config.json` or `~/.config/dragondesktop/config.json`:

```
{  
  "wallpaper_path": "/path/to/wallpaper.jpg",  
  "use_picom": true,  
  "picom_config": "/opt/dragondesktop/app_configs/picom.conf",  
  "aliases": {  
    "term": "alacritty",  
    "browser": "firefox"  
  }  
}  
```

Parameters:

- **wallpaper_path**: Path to background image (uses `feh` for setting)
- **use_picom**: Enable compositor mode (`true`/`false`)
- **picom_config**: Path to Picom configuration file
- **aliases**: Command shortcuts for the command bar

**Picom Configuration**

The compositor configuration can be customized at:

```
/opt/dragondesktop/app_configs/picom.conf
```
Key settings:
```
backend = "glx"  
vsync = true  
shadow = true  
shadow-radius = 12  
fading = false  
```

**Polybar Configuration**

DragonDesktop uses the "Simple" theme from <ins>adi1090x/polybar-themes</ins>.

Customize at:
```
~/.config/polybar/simple/config.ini  
```

## Troubleshooting

**Picom Fails to Start**

*Symptoms*:

No shadows, transparency disabled, message "Using CPU mode"

*Solutions*:

Check if another compositor is running:
```
pgrep picom
```  

Verify Picom installation:
```
picom --version  
```
Test Picom manually:
```
picom --config /opt/dragondesktop/app_configs/picom.conf  
```
Check logs:
```
tail -f /tmp/dragon-session.log  
```

**Polybar Not Appearing**

*Symptoms*:

No status bar visible

*Solutions*:

Verify Polybar installation:
```
polybar --version  
```
Check if config exists:
```
ls ~/.config/polybar/simple/launch.sh  
```
Launch manually for testing:
```
~/.config/polybar/simple/launch.sh --hack  
```

**Windows Not Responding to Clicks**

*Symptoms*:

Cannot focus or interact with application windows

*Solutions*:

1. Check if window is mapped: Press `Super + F1` to save position, then `Super + F1` to jump back
2. Try Alt-Tab to cycle focus: `Alt + Tab`
3. Restart the window manager: Log out and back in

**High CPU Usage**

*Causes*:

- CPU rendering mode active
- Large number of windows visible
- High zoom level (many small windows)

*Solutions*:

1. Enable Picom in config.json: "use_picom": true
2. Zoom in to reduce visible window count
3. Close unused windows

## Development

**Project Structure**


```
dragondesktop/
├── app_configs
│   └── picom.conf              # Compositor configuration
├── config.json                 # Configuration file
├── dragon.png
├── input.py                    # Event handling (keyboard/mouse)
├── inst_scripts
│   ├── install_dragon.sh       # Automated installer
│   └── start-dragon.sh         # Autorun script for Desktop
├── main.py                     # Entry point
├── models.py                   # Data structures (Camera, ZWindow)
├── README.md
├── renderer.py                 # Rendering engine (CPU/Compositor)
├── run.sh
├── settings_menu.py
├── wallpapers
│   └── olga-schraven-yEJ37R74dMo-unsplash.jpg
└── wm.py                       # Core window manager logic
```

**Adding New Features**

1. *New Keybindings*:

    Edit `input.py` → `_on_key_normal()`
    
    ```if keysym == XK.XK_YOUR_KEY and (event.state & X.Mod4Mask):  
    self.wm.your_function()  
    ```

2. *New Window Properties*:

    Edit `models.py` → `ZWindow.__init__()`

    ```
    self.your_property = default_value  
    ```

3. *EWMH Atoms*:

    Edit `wm.py` → `_setup_ewmh()`

    ```
    self._NET_YOUR_ATOM = self.d.intern_atom('_NET_YOUR_ATOM')
    ```

**Testing**

```
# Run in nested X server (Xephyr)  
Xephyr -screen 1280x720 :1 &  
DISPLAY=:1 python3 main.py  
  
# Or use the provided test script  
./test_in_xephyr.sh  
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Follow PEP 8 style guidelines
4. Test thoroughly in both CPU and compositor modes
5. Submit a pull request with clear description

**Code Style**


- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Docstrings for all public methods
- Type hints where applicable

## Licence

MIT License - See <ins>LICENSE</ins> file for details

## Credits


- Window Manager: Built with <ins>python-xlib</ins>
- Compositor: <ins>Picom</ins>
- Status Bar: Polybar Themes by <ins>adi1090x</ins>
- Wallpaper Management: <ins>feh</ins>

### Changelog
v0.2.0 (Current)

    Added Alt-Tab window cycling
    Implemented compositor mode with Picom integration
    Added workspace position memory (F1-F4)
    Improved EWMH compliance for Polybar compatibility
    Fixed window stacking issues in fullscreen mode

v0.1.0 (Initial)

    Infinite canvas implementation
    Basic window management (move, resize, close)
    Semantic zoom system
    Command bar with aliases
    CPU rendering mode

## Support

- Issues: [Github Issues](https://github.com/bulutthecat/DragonDesktop/issues)
- Discussions: Coming Soon

---

**Made with ♥ for the Linux community**