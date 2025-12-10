import subprocess  
from Xlib import X, display, XK, Xatom  
from Xlib import error as XError  
from Xlib.protocol import event  
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

        self.focused_window = None
          
        # --- ICCCM Protocol Atoms ---  
        self.WM_PROTOCOLS = self.d.intern_atom('WM_PROTOCOLS')  
        self.WM_DELETE_WINDOW = self.d.intern_atom('WM_DELETE_WINDOW')  
        self.WM_STATE = self.d.intern_atom('WM_STATE')  
        self.WM_CHANGE_STATE = self.d.intern_atom('WM_CHANGE_STATE')  
        self.WM_TAKE_FOCUS = self.d.intern_atom('WM_TAKE_FOCUS')  
          
        self.cmd_window = self._create_cmd_bar()  
          
        # --- PROPER ROOT EVENT MASK ---  
        self.root.change_attributes(  
            event_mask=(  
                X.SubstructureRedirectMask |  
                X.SubstructureNotifyMask |  
                X.StructureNotifyMask |  
                X.PropertyChangeMask |  
                X.ButtonPressMask |  
                X.KeyPressMask  
            )  
        )  
          
        self._setup_grabs()  
        print("DragonDesktop Running with Full X11 Protocol Support...")  

    def unfocus_all(self):  
        """Remove focus from all windows"""  
        try:  
            self.d.set_input_focus(X.PointerRoot, X.RevertToPointerRoot, X.CurrentTime)  
            self.focused_window = None  
            self.d.sync()  
            print("Unfocused all windows")  
        except Exception as e:  
            print(f"Unfocus error: {e}")  
    
    def focus_window(self, zwin):  
        try:  
            # Send WM_TAKE_FOCUS if supported  
            protocols = self.get_wm_protocols(zwin.client)  
            if self.WM_TAKE_FOCUS in protocols:  
                self.send_client_message(zwin.client, self.WM_TAKE_FOCUS)  
              
            # Always set input focus  
            self.d.set_input_focus(zwin.client, X.RevertToParent, X.CurrentTime)  
            zwin.frame.configure(stack_mode=X.Above)  
            self.focused_window = zwin  # TRACK FOCUS  
            self.d.sync()  
            print(f"Focused window: {zwin.title}")  
        except XError.BadMatch:  
            pass  
        except XError.BadWindow:  
            print(f"Window {zwin.id} disappeared during focus.")  
            self.close_window(zwin)  
        except Exception as e:  
            print(f"Focus Error: {e}")  


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
            # Send WM_TAKE_FOCUS if supported  
            protocols = self.get_wm_protocols(zwin.client)  
            if self.WM_TAKE_FOCUS in protocols:  
                self.send_client_message(zwin.client, self.WM_TAKE_FOCUS)  
            else:  
                # Fallback to direct focus  
                self.d.set_input_focus(zwin.client, X.RevertToParent, X.CurrentTime)  
              
            zwin.frame.configure(stack_mode=X.Above)  
            self.d.sync()  
        except XError.BadMatch:  
            pass  
        except XError.BadWindow:  
            print(f"Window {zwin.id} disappeared during focus.")  
            self.close_window(zwin)  
        except Exception as e:  
            print(f"Focus Error: {e}")  
  
    def get_wm_protocols(self, window):  
        """Get WM_PROTOCOLS supported by window"""  
        try:  
            prop = window.get_full_property(self.WM_PROTOCOLS, Xatom.ATOM)  
            if prop:  
                return prop.value  
        except:  
            pass  
        return []  
  
    def send_client_message(self, window, message_type, data=[0,0,0,0,0]):  
        """Send ClientMessage event (ICCCM)"""  
        try:  
            ev = event.ClientMessage(  
                window=window,  
                client_type=message_type,  
                data=(32, data)  
            )  
            window.send_event(ev, event_mask=X.NoEventMask)  
            self.d.sync()  
        except Exception as e:  
            print(f"ClientMessage Error: {e}")  
  
    def send_configure_notify(self, zwin):
            """Send synthetic ConfigureNotify (ICCCM requirement)"""
            try:
                geom = zwin.client.get_geometry()
                frame_geom = zwin.frame.get_geometry()
                
                # Ensure all values are Integers
                ev = event.ConfigureNotify(
                    event=zwin.client,
                    window=zwin.client,
                    x=int(frame_geom.x),
                    y=int(frame_geom.y + 25),
                    width=int(geom.width),
                    height=int(geom.height),
                    border_width=0,
                    above_sibling=X.NONE,
                    override_redirect=0  # Use integer 0 instead of False
                )
                
                zwin.client.send_event(ev, event_mask=X.StructureNotifyMask)
                self.d.sync()
                
            except Exception as e:
                # If it fails, print but DO NOT CRASH the WM
                print(f"ConfigureNotify Warning: {e}")
  
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
                  
                # --- CORE X11 EVENT HANDLERS ---  
                if event.type == X.MapRequest:  
                    self.handle_map_request(event.window)  
                elif event.type == X.ConfigureRequest:  
                    self.handle_configure_request(event)  
                elif event.type == X.UnmapNotify:  
                    self.handle_unmap_notify(event)  
                elif event.type == X.DestroyNotify:  
                    self.handle_destroy_notify(event)  
                elif event.type == X.PropertyNotify:  
                    self.handle_property_notify(event)  
                elif event.type == X.ClientMessage:  
                    self.handle_client_message(event)  
                elif event.type == X.MapNotify:  
                    pass  # Informational only  
                elif event.type == X.ReparentNotify:  
                    pass  # We caused this  
                else:  
                    # Pass to input handler  
                    self.input.handle_event(event)  
            except KeyboardInterrupt:  
                break  
            except Exception as e:  
                print(f"Event Loop Error: {e}")  
                import traceback  
                traceback.print_exc()  
  
    def handle_configure_request(self, event):  
            """  
            CRITICAL: Apps request size/position changes.
            Must respond or app will hang/break.  
            """  
            window = event.window  
              
            # Check if this is one of our managed windows  
            zwin = None  
            for win in self.windows.values():  
                if win.client.id == window.id:  
                    zwin = win  
                    break  
                
            if zwin:  
                # Update world coordinates if app requests it  
                if event.value_mask & X.CWX:  
                    zwin.world_x = int(event.x)  # Force Int
                if event.value_mask & X.CWY:  
                    zwin.world_y = int(event.y)  # Force Int
                if event.value_mask & X.CWWidth:  
                    zwin.world_w = max(int(event.width), zwin.min_w)  
                if event.value_mask & X.CWHeight:  
                    zwin.world_h = max(int(event.height), zwin.min_h)  
                  
                # Re-render  
                self.renderer.render_world(self.camera, self.windows)  
                  
                # Send synthetic ConfigureNotify (ICCCM requirement)  
                self.send_configure_notify(zwin)  
            else:  
                # Unmanaged window - grant request directly  
                try:  
                    # Prepare configuration arguments cleanly
                    args = {}
                    if event.value_mask & X.CWX: args['x'] = int(event.x)
                    if event.value_mask & X.CWY: args['y'] = int(event.y)
                    if event.value_mask & X.CWWidth: args['width'] = int(event.width)
                    if event.value_mask & X.CWHeight: args['height'] = int(event.height)
                    if event.value_mask & X.CWBorderWidth: args['border_width'] = int(event.border_width)
                    if event.value_mask & X.CWStackMode: args['stack_mode'] = int(event.stack_mode)
                    
                    window.configure(**args)
                except Exception as e:  
                    print(f"Configure unmanaged window error: {e}")
  
    def handle_unmap_notify(self, event):  
            """Window unmaps itself (minimize, hide, etc)"""  
            window_id = event.window.id  
              
            # Find and remove the window  
            target_zwin = None  
            for zwin in list(self.windows.values()):  
                if zwin.client.id == window_id:  
                    target_zwin = zwin  
                    break  
                
            if target_zwin:  
                print(f"Window {window_id} unmapped itself")  
                # Don't destroy, just hide  
                try:  
                    # Check if the frame is actually valid before unmapping
                    target_zwin.frame.unmap()  
                except Exception as e:
                    # Ignore errors if the window is already gone
                    pass  
                self.renderer.render_world(self.camera, self.windows)
  
    def handle_destroy_notify(self, event):  
        """Window destroyed (app closed)"""  
        destroyed_window_id = event.window.id  
          
        target_zwin = None  
        for zwin in list(self.windows.values()):  
            if zwin.client.id == destroyed_window_id:  
                target_zwin = zwin  
                break  
          
        if target_zwin:  
            print(f"Window {destroyed_window_id} destroyed")  
              
            if target_zwin.id in self.windows:  
                del self.windows[target_zwin.id]  
              
            if target_zwin.btn_close.id in self.btn_map:  
                del self.btn_map[target_zwin.btn_close.id]  
            if target_zwin.btn_full.id in self.btn_map:  
                del self.btn_map[target_zwin.btn_full.id]  
              
            try:  
                target_zwin.frame.destroy()  
            except XError.BadWindow:  
                pass  
              
            self.renderer.render_world(self.camera, self.windows)  
  
    def handle_property_notify(self, event):  
        """Window property changed (title, hints, etc)"""  
        window_id = event.window.id  
          
        # Find the window  
        target_zwin = None  
        for zwin in self.windows.values():  
            if zwin.client.id == window_id:  
                target_zwin = zwin  
                break  
          
        if not target_zwin:  
            return  
          
        # Update title if WM_NAME changed  
        if event.atom == Xatom.WM_NAME:  
            try:  
                new_title = target_zwin.client.get_wm_name() or "Untitled"  
                target_zwin.title = new_title  
                self.renderer.render_world(self.camera, self.windows)  
            except:  
                pass  
          
        # Update size hints if WM_NORMAL_HINTS changed  
        elif event.atom == Xatom.WM_NORMAL_HINTS:  
            try:  
                min_w, min_h, max_w, max_h = self.get_size_hints(target_zwin.client)  
                target_zwin.min_w = min_w  
                target_zwin.min_h = min_h  
                target_zwin.max_w = max_w  
                target_zwin.max_h = max_h  
            except:  
                pass  
  
    def handle_client_message(self, event):  
        """Handle ICCCM client messages"""  
        try:  
            if event.client_type == self.WM_CHANGE_STATE:  
                # App wants to change state (iconify, etc)  
                pass  
        except Exception as e:  
            print(f"ClientMessage handler error: {e}")  
  
    def toggle_cmd_bar(self):  
        if self.cmd_active:  
            self.cmd_active = False  
            self.cmd_window.unmap()  
            try:  
                self.d.ungrab_keyboard(X.CurrentTime)  
                self.d.sync()  
                print("Bar closed, keyboard ungrabbed")  
            except Exception as e:  
                print(f"Ungrab error: {e}")  
        else:  
            self.cmd_active = True  
            self.cmd_text = ""  
            self.cmd_window.map()  
            self.cmd_window.raise_window()  
            try:  
                # Give the window time to map  
                self.d.sync()  
                # Grab keyboard  
                grab_status = self.cmd_window.grab_keyboard(  
                    True,  # owner_events  
                    X.GrabModeAsync,  
                    X.GrabModeAsync,  
                    X.CurrentTime  
                )  
                if grab_status == X.GrabSuccess:  
                    print("Bar opened, keyboard grabbed successfully")  
                else:  
                    print(f"Keyboard grab failed with status: {grab_status}")  
            except Exception as e:  
                print(f"Grab error: {e}")  
            self.draw_bar()  

  
    def draw_bar(self):  
        if self.cmd_active:  
            s = self.root.get_geometry()  
            self.renderer.render_cmd_bar(self.cmd_window, "> " + self.cmd_text, s.width, s.height)  
  
    def execute_command(self):  
        cmd = self.cmd_text.strip()  
        if cmd:  
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
                # Min Size  
                if hints.flags & X.PMinSize:  
                    min_w = hints.min_width  
                    min_h = hints.min_height  
                # Max Size  
                if hints.flags & X.PMaxSize:  
                    max_w = hints.max_width  
                    max_h = hints.max_height  
                # Base Size (for terminal emulators)  
                if hints.flags & X.PBaseSize:  
                    if min_w == 0: min_w = hints.base_width  
                    if min_h == 0: min_h = hints.base_height  
                      
            return min_w, min_h, max_w, max_h  
        except:  
            return 0, 0, 32768, 32768  
  
    def handle_map_request(self, window):  
        # Ignore override_redirect windows  
        try:  
            attrs = window.get_attributes()  
            if attrs.override_redirect:  
                window.map()  
                return  
        except:  
            return  
          
        if window.id in self.windows or window.id in self.btn_map:  
            return  
          
        try:  
            geom = window.get_geometry()  
            min_w, min_h, max_w, max_h = self.get_size_hints(window)  
        except:  
            return  
          
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
          
        sx, sy, sw, sh = self.renderer.project(  
            self.camera, self.camera.x, self.camera.y,  
            target_w, target_h + 25  
        )  
          
        frame = self.root.create_window(  
            sx, sy, sw, sh,  
            border_width=1,  
            depth=X.CopyFromParent,  
            visual=X.CopyFromParent,  
            background_pixel=theme['bar'],  
            event_mask=(  
                X.SubstructureRedirectMask |  
                X.SubstructureNotifyMask |  
                X.ButtonPressMask |  
                X.ButtonReleaseMask |  
                X.ButtonMotionMask |  
                X.ExposureMask  
            )  
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
          
        zwin = ZWindow(  
            frame.id, window, frame, btn_close, btn_full,  
            self.camera.x, self.camera.y, target_w, target_h + 25,  
            title=name  
        )  
        zwin.min_w = min_w; zwin.min_h = min_h  
        zwin.max_w = max_w; zwin.max_h = max_h  
          
        self.windows[frame.id] = zwin  
        self.btn_map[btn_close.id] = ('close', zwin)  
        self.btn_map[btn_full.id] = ('maximize', zwin)  
          
        # Subscribe to client events  
        try:  
            window.change_attributes(  
                event_mask=(  
                    X.PropertyChangeMask |  
                    X.StructureNotifyMask |  
                    X.FocusChangeMask |
                    X.ButtonPressMask |      # ADD THIS  
                    X.ButtonReleaseMask |    # ADD THIS  
                    X.EnterWindowMask        # ADD THIS  
                )  
            )  
        except:  
            pass  
          
        # Set WM_STATE to Normal  
        try:  
            window.change_property(  
                self.WM_STATE, self.WM_STATE, 32,  
                [1, X.NONE]  # NormalState  
            )  
        except:  
            pass  
          
        window.reparent(frame, 0, 25)  
        frame.map()  
        window.map()  
        btn_close.map()  
        btn_full.map()  
          
        self.focus_window(zwin)  
        self.renderer.render_world(self.camera, self.windows)  
          
        # Send initial configure notify  
        self.send_configure_notify(zwin)  
  
    def close_window(self, zwin):  
        """Close window using ICCCM protocol"""  
        # Try graceful close first  
        protocols = self.get_wm_protocols(zwin.client)  
        if self.WM_DELETE_WINDOW in protocols:  
            self.send_client_message(  
                zwin.client,  
                self.WM_PROTOCOLS,  
                [self.WM_DELETE_WINDOW, X.CurrentTime, 0, 0, 0]  
            )  
        else:  
            # Force kill  
            try:  
                zwin.client.kill_client()  
            except:  
                pass  
          
        # Don't delete immediately - wait for DestroyNotify  
  
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
        self.send_configure_notify(zwin)  
  
    def zoom_camera(self, direction):
            # 1. Update Zoom
            self.camera.zoom += (0.1 * direction)

            # Clamp zoom (using the range from your old code which allowed up to 5.0)
            self.camera.zoom = max(0.11, min(self.camera.zoom, 5.0))
            print(f"Zoom: {self.camera.zoom:.2f}")

            # 2. Render the world
            # This moves the windows. X11 automatically sends ConfigureNotify 
            # to apps when their physical window is moved/resized by the renderer.
            try:
                self.renderer.render_world(self.camera, self.windows)
            except Exception as e:
                print(f"Renderer Error: {e}")
  
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
