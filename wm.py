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

        self.config = self.load_config()
        self.camera = Camera()
        
        self.renderer = Renderer(self.root, self.d, self.config)
        self.input = InputHandler(self)
        self.windows = {} 
        self.btn_map = {} 
        
        self.cmd_active = False
        self.cmd_text = ""
        self.cmd_window = self._create_cmd_bar()
        
        self.root.change_attributes(event_mask=X.SubstructureRedirectMask)
        self._setup_grabs()
        
        print("DragonDesktop Running...")

    def load_config(self):
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Config Error: {e}")
        return {"wallpaper_path": ""}

    def _create_cmd_bar(self):
        s = self.root.get_geometry()
        w = 600; h = 40
        x = (s.width - w) // 2; y = (s.height - h) // 2 
        win = self.root.create_window(
            x, y, w, h, border_width=2,
            depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=self.renderer.alloc_color('white'),
            event_mask=X.ExposureMask | X.KeyPressMask 
        )
        win.configure(border_pixel=self.renderer.alloc_color('black'))
        return win

    def _setup_grabs(self):
        # 1. Mod4 (Win) + Scroll (4, 5) -> Zoom
        self.root.grab_button(4, X.Mod4Mask, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        self.root.grab_button(5, X.Mod4Mask, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)
        
        # 2. Win + Space
        space_key = self.d.keysym_to_keycode(XK.string_to_keysym("space"))
        self.root.grab_key(space_key, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)

        # 3. F-Keys
        f_keys = [XK.XK_F1, XK.XK_F2, XK.XK_F3, XK.XK_F4]
        for ksym in f_keys:
            code = self.d.keysym_to_keycode(ksym)
            self.root.grab_key(code, X.Mod4Mask, True, X.GrabModeAsync, X.GrabModeAsync)
            self.root.grab_key(code, X.Mod4Mask | X.ControlMask, True, X.GrabModeAsync, X.GrabModeAsync)
            
        # 4. Alt + F4
        f4_key = self.d.keysym_to_keycode(XK.XK_F4)
        self.root.grab_key(f4_key, X.Mod1Mask, True, X.GrabModeAsync, X.GrabModeAsync)

    def focus_window(self, zwin):
        try:
            self.d.set_input_focus(zwin.client, X.RevertToParent, X.CurrentTime)
            zwin.frame.raise_window()
        except Exception as e:
            print(f"Focus Error: {e}")

    # --- THIS WAS MISSING AND CAUSED THE CRASH ---
    def get_fullscreen_window(self):
        """Returns the ZWindow object if one is currently fullscreen, else None."""
        for win in self.windows.values():
            if win.is_fullscreen: return win
        return None

    def close_focused_window(self):
        try:
            focus_reply = self.d.get_input_focus()
            focus_win = focus_reply.focus
            if isinstance(focus_win, int) or focus_win == X.NONE: return

            target_zwin = None
            if focus_win.id in self.windows:
                target_zwin = self.windows[focus_win.id]
            else:
                for win in self.windows.values():
                    if win.client.id == focus_win.id:
                        target_zwin = win
                        break
            
            if target_zwin:
                self.close_window(target_zwin)
                self.renderer.render_world(self.camera, self.windows)
        except Exception as e:
            print(f"Error closing window: {e}")

    def run(self):
        # --- CRASH PROTECTION ---
        # We wrap the loop so one error doesn't kill the whole desktop session
        while True:
            try:
                event = self.d.next_event()
                if event.type == X.MapRequest:
                    self.handle_map_request(event.window)
                else:
                    self.input.handle_event(event)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"CRITICAL WM ERROR: {e}")
                # We continue the loop so the desktop stays alive

    def toggle_cmd_bar(self):
        if self.cmd_active:
            self.cmd_active = False
            self.cmd_window.unmap()
            self.d.ungrab_keyboard(X.CurrentTime) 
        else:
            self.cmd_active = True
            self.cmd_text = ""
            self.cmd_window.map()
            self.cmd_window.raise_window()
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
            try:
                subprocess.Popen(cmd, shell=True, executable="/bin/bash")
            except Exception as e:
                print(f"Error: {e}")
        self.toggle_cmd_bar() 

    def get_size_hints(self, window):
        try:
            hints = window.get_wm_normal_hints()
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
        
        try: 
            geom = window.get_geometry()
            min_w, min_h, max_w, max_h = self.get_size_hints(window)
        except: return
        
        target_w = max(geom.width, min_w)
        target_h = max(geom.height, min_h)
        if target_w < 50: target_w = 400
        if target_h < 50: target_h = 300

        try:
            name = window.get_wm_name() or "Untitled"
            wm_class = window.get_wm_class()
            app_name = wm_class[1] if wm_class else "unknown"
        except:
            name = "Untitled"; app_name = "unknown"

        theme = self.renderer.create_theme(app_name)
        
        sx, sy, sw, sh = self.renderer.project(self.camera, self.camera.x, self.camera.y, target_w, target_h + 25)

        frame = self.root.create_window(
            sx, sy, sw, sh,
            border_width=1,
            depth=X.CopyFromParent,
            visual=X.CopyFromParent,
            background_pixel=theme['bar'],
            event_mask=X.StructureNotifyMask | X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask | X.SubstructureRedirectMask | X.ExposureMask
        )
        
        btn_size = 20
        btn_close = frame.create_window(
            sw - btn_size, 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['close'], event_mask=X.ButtonPressMask
        )
        
        btn_full = frame.create_window(
            sw - (btn_size * 2), 0, btn_size, btn_size, 
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,
            background_pixel=theme['full'], event_mask=X.ButtonPressMask
        )

        zwin = ZWindow(frame.id, window, frame, btn_close, btn_full, self.camera.x, self.camera.y, target_w, target_h + 25, title=name)
        zwin.min_w = min_w; zwin.min_h = min_h; zwin.max_w = max_w; zwin.max_h = max_h
        
        self.windows[frame.id] = zwin
        self.btn_map[btn_close.id] = ('close', zwin)
        self.btn_map[btn_full.id] = ('maximize', zwin)

        window.reparent(frame, 0, 25)
        frame.map()
        window.map()
        btn_close.map()
        btn_full.map()
        
        self.focus_window(zwin)
        self.renderer.render_world(self.camera, self.windows)

    def close_window(self, zwin):
        if zwin.id in self.windows:
            try:
                zwin.client.destroy()
                zwin.frame.destroy()
            except: pass
            del self.windows[zwin.id]
            self.renderer.render_world(self.camera, self.windows)

    def toggle_fullscreen(self, zwin):
        screen = self.root.get_geometry()
        if zwin.is_fullscreen:
            if zwin.saved_geometry:
                zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h = zwin.saved_geometry
                zwin.saved_geometry = None
            zwin.is_fullscreen = False
        else:
            zwin.saved_geometry = (zwin.world_x, zwin.world_y, zwin.world_w, zwin.world_h)
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

    def save_camera_pos(self, index):
        self.camera.saved_spots[index] = (self.camera.x, self.camera.y, self.camera.zoom)
        print(f"Saved Camera Position {index}")
        
    def load_camera_pos(self, index):
        if index in self.camera.saved_spots:
            x, y, z = self.camera.saved_spots[index]
            self.camera.x = x; self.camera.y = y; self.camera.zoom = z
            print(f"Jumped to Position {index}")
            self.renderer.render_world(self.camera, self.windows)