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
        # ... (Keep your existing mouse grabs) ...
        self.root.grab_button(4, X.AnyModifier, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        self.root.grab_button(5, X.AnyModifier, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        self.root.grab_button(1, X.Mod4Mask, True, X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        
        # Win + Space
        space_key = self.d.keysym_to_keycode(XK.string_to_keysym("space"))
        self.root.grab_key(space_key, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)

        # F-Keys (Load/Save)
        f_keys = [XK.XK_F1, XK.XK_F2, XK.XK_F3, XK.XK_F4]
        for ksym in f_keys:
            code = self.d.keysym_to_keycode(ksym)
            self.root.grab_key(code, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)
            self.root.grab_key(code, X.Mod4Mask | X.ControlMask, True, X.GrabModeAsync, X.GrabModeAsync)
            
        # --- NEW: Alt + F4 (Close Window) ---
        # Mod1Mask is usually the "Alt" key
        f4_key = self.d.keysym_to_keycode(XK.XK_F4)
        self.root.grab_key(f4_key, X.Mod1Mask, True, X.GrabModeAsync, X.GrabModeAsync)

    def get_fullscreen_window(self):
        """Returns the ZWindow object if one is currently fullscreen, else None."""
        for win in self.windows.values():
            if win.is_fullscreen:
                return win
        return None

    def close_focused_window(self):
        """Finds which window has X11 focus and closes it."""
        try:
            # Ask X11 who has focus
            focus_reply = self.d.get_input_focus()
            focus_win = focus_reply.focus
            
            # FIX: If focus is X.PointerRoot (1) or X.None (0), it returns an int, not a Window object.
            # We cannot close the "mouse pointer", so we just return.
            if isinstance(focus_win, int):
                return
            
            if not focus_win or focus_win == X.NONE: return

            target_zwin = None
            
            # Check 1: Did we focus the Frame?
            if focus_win.id in self.windows:
                target_zwin = self.windows[focus_win.id]
            
            # Check 2: Did we focus the Client (the app inside)?
            else:
                for win in self.windows.values():
                    if win.client.id == focus_win.id:
                        target_zwin = win
                        break
            
            if target_zwin:
                print(f"Closing focused window: {target_zwin.title}")
                self.close_window(target_zwin)
                self.renderer.render_world(self.camera, self.windows)
                
        except Exception as e:
            print(f"Error closing window: {e}")

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

    def get_size_hints(self, window):
        """
        Reads WM_NORMAL_HINTS to get min/max size and resize increments.
        Returns (min_w, min_h, max_w, max_h)
        """
        try:
            # Xlib provides a helper for this standard property
            hints = window.get_wm_normal_hints()
            
            # Default values if hints are missing
            min_w, min_h = 0, 0
            max_w, max_h = 32768, 32768

            if hints:
                if hints.flags & X.PMinSize:
                    min_w = hints.min_width
                    min_h = hints.min_height
                if hints.flags & X.PMaxSize:
                    max_w = hints.max_width
                    max_h = hints.max_height
            
            return min_w, min_h, max_w, max_h
        except:
            return 0, 0, 32768, 32768

    def handle_map_request(self, window):
        if window.id in self.windows or window.id in self.btn_map: return
        
        # 1. Get Geometry & HINTS
        try: 
            geom = window.get_geometry()
            min_w, min_h, max_w, max_h = self.get_size_hints(window)
        except: return
        
        # --- Respect App's Requested Size ---
        target_w = geom.width
        target_h = geom.height

        # Enforce Minimums
        if target_w < min_w: target_w = min_w
        if target_h < min_h: target_h = min_h
        
        # Defaults for unconfigured windows
        if target_w < 50 and min_w < 50: target_w = 400
        if target_h < 50 and min_h < 50: target_h = 300

        # 2. Get App Name
        try:
            name = window.get_wm_name() or "Untitled"
            wm_class = window.get_wm_class()
            app_name = wm_class[1] if wm_class else "unknown"
        except:
            name = "Untitled"
            app_name = "unknown"

        print(f"Framing {app_name}: {target_w}x{target_h} (Min: {min_w}x{min_h})")
        
        # 3. Generate Theme
        theme = self.renderer.create_theme(app_name)

        # 4. Create Windows
        # We project the target size to screen coordinates
        sx, sy, sw, sh = self.renderer.project(self.camera, self.camera.x, self.camera.y, target_w, target_h + 25)

        # --- FIX: FULL CREATE_WINDOW CALL ---
        frame = self.root.create_window(
            sx, sy, sw, sh,
            border_width=1,
            depth=X.CopyFromParent,
            visual=X.CopyFromParent,
            background_pixel=theme['bar'],
            event_mask=X.StructureNotifyMask | X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask | X.SubstructureRedirectMask | X.ExposureMask
        )
        
        btn_size = 20
        
        # Close Button
        btn_close = frame.create_window(
            sw - btn_size, 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['close'], event_mask=X.ButtonPressMask
        )
        
        # Fullscreen Button
        btn_full = frame.create_window(
            sw - (btn_size * 2), 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['full'], event_mask=X.ButtonPressMask
        )

        # 5. Model & Register
        zwin = ZWindow(frame.id, window, frame, btn_close, btn_full, self.camera.x, self.camera.y, target_w, target_h + 25, title=name)
        
        # Save Hints into the Window Model (Crucial for Wine)
        zwin.min_w = min_w
        zwin.min_h = min_h
        zwin.max_w = max_w
        zwin.max_h = max_h
        
        self.windows[frame.id] = zwin
        self.btn_map[btn_close.id] = ('close', zwin)
        self.btn_map[btn_full.id] = ('maximize', zwin)

        window.reparent(frame, 0, 25)
        # We don't force configure here anymore, the renderer loop handles it based on hints
        
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
        
        if zwin.is_fullscreen:
            # RESTORE to Windowed
            if zwin.saved_geometry:
                zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h = zwin.saved_geometry
                zwin.saved_geometry = None
            zwin.is_fullscreen = False
        else:
            # GO FULLSCREEN
            zwin.saved_geometry = (zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h)
            
            # Calculate world units needed to fill screen at current zoom
            zwin.world_w = int(screen.width / self.camera.zoom)
            zwin.world_h = int(screen.height / self.camera.zoom)
            zwin.world_x = int(self.camera.x - (zwin.world_w / 2))
            zwin.world_y = int(self.camera.y - (zwin.world_h / 2))
            
            zwin.is_fullscreen = True

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