import subprocess  
from Xlib import X, display, XK  
from Xlib import error as XError  
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
        return {  
            "wallpaper_path": "",  
            "aliases": {  
                "settings": "python3 settings_menu.py"  
            }  
        }  
  
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
        masks = [  
            X.Mod4Mask,   
            X.Mod4Mask | X.Mod2Mask,   
            X.Mod4Mask | X.LockMask,   
            X.Mod4Mask | X.Mod2Mask | X.LockMask  
        ]  
  
        for mask in masks:  
            self.root.grab_button(4, mask, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)  
            self.root.grab_button(5, mask, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)  
            self.root.grab_button(1, mask, True, X.ButtonPressMask | X.ButtonReleaseMask | X.ButtonMotionMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)  
  
        space_key = self.d.keysym_to_keycode(XK.string_to_keysym("space"))  
        for mask in masks:  
            self.root.grab_key(space_key, mask, True, X.GrabModeAsync, X.GrabModeAsync)  
  
        f_keys = [XK.XK_F1, XK.XK_F2, XK.XK_F3, XK.XK_F4]  
        for ksym in f_keys:  
            code = self.d.keysym_to_keycode(ksym)  
            for mask in masks:  
                self.root.grab_key(code, mask, True, X.GrabModeAsync, X.GrabModeAsync)  
                self.root.grab_key(code, mask | X.ControlMask, True, X.GrabModeAsync, X.GrabModeAsync)  
  
        f4_key = self.d.keysym_to_keycode(XK.XK_F4)  
        alt_masks = [  
            X.Mod1Mask,   
            X.Mod1Mask | X.Mod2Mask,   
            X.Mod1Mask | X.LockMask,   
            X.Mod1Mask | X.Mod2Mask | X.LockMask  
        ]  
        for mask in alt_masks:  
            self.root.grab_key(f4_key, mask, True, X.GrabModeAsync, X.GrabModeAsync)  
  
    def focus_window(self, zwin):  
        try:  
            self.d.set_input_focus(zwin.client, X.RevertToParent, X.CurrentTime)  
            zwin.frame.raise_window()  
        except XError.BadMatch:  
            pass   
        except XError.BadWindow:  
            print(f"Window {zwin.id} disappeared during focus.")  
            self.close_window(zwin)  
        except Exception as e:  
            print(f"Generic Focus Error: {e}")  
  
    def get_fullscreen_window(self):  
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
        while True:  
            try:  
                event = self.d.next_event()  
                if event.type == X.MapRequest:  
                    self.handle_map_request(event.window)  
                # --- FIX: Handle DestroyNotify ---  
                elif event.type == X.DestroyNotify:  
                    self.handle_destroy_notify(event)  
                else:  
                    self.input.handle_event(event)  
            except KeyboardInterrupt:  
                break  
            except Exception as e:  
                print(f"CRITICAL WM ERROR: {e}")  
  
    def handle_destroy_notify(self, event):  
        """  
        Called when a client window is destroyed (app exits).  
        We need to clean up our frame and internal state.  
        """  
        destroyed_window_id = event.window.id  
          
        # Find the ZWindow that contains this client  
        target_zwin = None  
        for zwin in list(self.windows.values()):  
            if zwin.client.id == destroyed_window_id:  
                target_zwin = zwin  
                break  
          
        if target_zwin:  
            print(f"Client window {destroyed_window_id} destroyed, cleaning up frame {target_zwin.id}")  
            # Remove from tracking  
            if target_zwin.id in self.windows:  
                del self.windows[target_zwin.id]  
              
            # Remove buttons from btn_map  
            if target_zwin.btn_close.id in self.btn_map:  
                del self.btn_map[target_zwin.btn_close.id]  
            if target_zwin.btn_full.id in self.btn_map:  
                del self.btn_map[target_zwin.btn_full.id]  
              
            # Destroy the frame (decoration)  
            try:  
                target_zwin.frame.destroy()  
            except XError.BadWindow:  
                pass  # Already gone  
              
            # Re-render to update display  
            self.renderer.render_world(self.camera, self.windows)  
  
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
            # --- Check for aliases first ---  
            aliases = self.config.get("aliases", {})  
            if cmd in aliases:  
                actual_cmd = aliases[cmd]  
                print(f"Alias '{cmd}' -> '{actual_cmd}'")  
                cmd = actual_cmd  
              
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
  
        # --- FIX: Subscribe to client window events so we get DestroyNotify ---  
        try:  
            window.change_attributes(event_mask=X.StructureNotifyMask)  
        except:  
            pass  
  
        window.reparent(frame, 0, 25)  
        frame.map()  
        window.map()  
        btn_close.map()  
        btn_full.map()  
  
        self.focus_window(zwin)  
        self.renderer.render_world(self.camera, self.windows)  
  
    def close_window(self, zwin):  
        if zwin.id in self.windows:  
            del self.windows[zwin.id]  
  
        try:  
            zwin.client.kill_client()  
        except XError.BadWindow:  
            pass  
        except Exception:  
            pass  
  
        try:  
            zwin.frame.destroy()  
        except XError.BadWindow:  
            pass  
  
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