import subprocess
from Xlib import X, display, XK
from models import Camera, ZWindow
from renderer import Renderer
from input import InputHandler
import json
import os

class WindowManager:
    def __init__(self):
        self.d = display.Display()
        self.root = self.d.screen().root

        # --- NEW: Load Config ---
        self.config = self.load_config()

        self.camera = Camera()
        
        # Pass config to renderer
        self.renderer = Renderer(self.root, self.d, self.config)
        self.input = InputHandler(self)
        self.windows = {} 
        self.btn_map = {} 
        
        # --- NEW: Command Bar State ---
        self.cmd_active = False
        self.cmd_text = ""
        self.cmd_window = self._create_cmd_bar()
        
        self.root.change_attributes(event_mask=X.SubstructureRedirectMask)
        self._setup_grabs()
        
        print("DragonDesktop Running...")

    def load_config(self):
        """Loads config.json or returns defaults"""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Config Error: {e}")
        
        # Default fallback
        return {
            "wallpaper_path": ""
            # tiling_type removed
        }

    def _create_cmd_bar(self):
        """Creates the hidden command bar window centered on screen."""
        s = self.root.get_geometry()
        w = 600
        h = 40
        x = (s.width - w) // 2
        y = (s.height - h) // 2  # Halfway down

        # Create window (White background)
        win = self.root.create_window(
            x, y, w, h, border_width=2,
            depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=self.renderer.alloc_color('white'),
            event_mask=X.ExposureMask | X.KeyPressMask # Listen for typing!
        )
        # Border color (Black)
        win.configure(border_pixel=self.renderer.alloc_color('black'))
        return win

    def _setup_grabs(self):
        # Mouse Grabs
        self.root.grab_button(4, X.AnyModifier, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        self.root.grab_button(5, X.AnyModifier, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        self.root.grab_button(1, X.Mod4Mask, True, X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        
        # --- NEW: Grab Win+Space ---
        # 32 is standard space keycode, but we should use keysym_to_keycode for safety
        space_key = self.d.keysym_to_keycode(XK.string_to_keysym("space"))
        self.root.grab_key(space_key, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)

        # --- GRAB F-KEYS (F1 to F4) ---
        f_keys = [XK.XK_F1, XK.XK_F2, XK.XK_F3, XK.XK_F4]
        
        for ksym in f_keys:
            code = self.d.keysym_to_keycode(ksym)
            
            # Grab Win + F_Key (Load)
            self.root.grab_key(code, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)
            
            # Grab Win + Ctrl + F_Key (Save)
            # Note: Modifiers are bitmasks, we use bitwise OR (|) to combine them
            self.root.grab_key(code, X.Mod4Mask | X.ControlMask, True, X.GrabModeAsync, X.GrabModeAsync)

    def run(self):
        while True:
            event = self.d.next_event()
            if event.type == X.MapRequest:
                self.handle_map_request(event.window)
            else:
                self.input.handle_event(event)

    # --- Command Bar Logic ---

    def toggle_cmd_bar(self):
        if self.cmd_active:
            # Hide it
            self.cmd_active = False
            self.cmd_window.unmap()
            self.d.ungrab_keyboard(X.CurrentTime) # Let apps type again
        else:
            # Show it
            self.cmd_active = True
            self.cmd_text = ""
            self.cmd_window.map()
            self.cmd_window.raise_window()
            # CRITICAL: Grab keyboard so typing goes to WM, not apps
            self.root.grab_keyboard(True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
            self.draw_bar()

    def draw_bar(self):
        if self.cmd_active:
            s = self.root.get_geometry()
            self.renderer.render_cmd_bar(self.cmd_window, "> " + self.cmd_text, s.width, s.height)

    def execute_command(self):
        cmd = self.cmd_text.strip()
        if cmd:
            print(f"Executing: {cmd}")
            # Launch async
            try:
                subprocess.Popen(cmd, shell=True, executable="/bin/bash")
            except Exception as e:
                print(f"Error: {e}")
        self.toggle_cmd_bar() # Close bar

    def handle_map_request(self, window):
        if window.id in self.windows or window.id in self.btn_map: return
        
        # 1. Get Geometry
        try: geom = window.get_geometry()
        except: return
        ww = 400 if geom.width < 50 else geom.width
        wh = 300 if geom.height < 50 else geom.height
        
        try:
            name = window.get_wm_name()
            if not name: name = "Untitled"
        except:
            name = "Untitled"
        
        # 2. Get App Name for Coloring
        # wm_class returns a tuple like ('xterm', 'XTerm')
        try:
            wm_class = window.get_wm_class()
            app_name = wm_class[1] if wm_class else "unknown"
        except:
            app_name = "unknown"
            
        print(f"Framing app: {app_name}")
        
        # 3. Generate Theme
        theme = self.renderer.create_theme(app_name)

        # 4. Create Windows
        sx, sy, sw, sh = self.renderer.project(self.camera, self.camera.x, self.camera.y, ww, wh + 25)

        # Frame
        frame = self.root.create_window(
            sx, sy, sw, sh, border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['bar'],
            event_mask=X.StructureNotifyMask | X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask | X.SubstructureRedirectMask | X.ExposureMask
        )
        
        # Initial sizing for buttons (Standard 20px, updated by renderer immediately anyway)
        btn_size = 20
        
        # Close Button (Far Right)
        btn_close = frame.create_window(
            sw - btn_size, 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['close'], event_mask=X.ButtonPressMask
        )
        
        # Fullscreen Button (Left of Close)
        btn_full = frame.create_window(
            sw - (btn_size * 2), 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['full'], event_mask=X.ButtonPressMask
        )

        # 5. Model & Register
        zwin = ZWindow(frame.id, window, frame, btn_close, btn_full, self.camera.x, self.camera.y, ww, wh + 25, title=name)
        
        self.windows[frame.id] = zwin
        self.btn_map[btn_close.id] = ('close', zwin)
        self.btn_map[btn_full.id] = ('maximize', zwin)

        window.reparent(frame, 0, 25)
        window.configure(border_width=0)
        frame.map()
        window.map()
        btn_close.map()
        btn_full.map()
        
        self.renderer.render_world(self.camera, self.windows)

    def close_window(self, zwin):
        if zwin.id in self.windows:
            zwin.client.destroy()
            zwin.frame.destroy()
            del self.windows[zwin.id]

    def toggle_fullscreen(self, zwin):
        screen = self.root.get_geometry()
        if zwin.saved_geometry:
            zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h = zwin.saved_geometry
            zwin.saved_geometry = None
        else:
            zwin.saved_geometry = (zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h)
            zwin.world_w = int(screen.width / self.camera.zoom)
            zwin.world_h = int(screen.height / self.camera.zoom)
            zwin.world_x = int(self.camera.x - (zwin.world_w / 2))
            zwin.world_y = int(self.camera.y - (zwin.world_h / 2))
        self.renderer.render_world(self.camera, self.windows)

    def zoom_camera(self, direction):
        self.camera.zoom += (0.1 * direction)
        self.camera.zoom = max(0.11, min(self.camera.zoom, 5.0))
        print(f"Zoom: {self.camera.zoom:.2f}")
        self.renderer.render_world(self.camera, self.windows)

    def get_window_by_frame(self, frame_id):
        return self.windows.get(frame_id)

    # Add these methods to the WindowManager class
    def save_camera_pos(self, index):
        self.camera.saved_spots[index] = (self.camera.x, self.camera.y, self.camera.zoom)
        print(f"Saved Camera Position {index}")
        # Visual feedback: flash the bar or print to console
        
    def load_camera_pos(self, index):
        if index in self.camera.saved_spots:
            x, y, z = self.camera.saved_spots[index]
            self.camera.x = x
            self.camera.y = y
            self.camera.zoom = z
            print(f"Jumped to Position {index}")
            self.renderer.render_world(self.camera, self.windows)

if __name__ == "__main__":
    WindowManager().run()