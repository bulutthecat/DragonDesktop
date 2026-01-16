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
        self.frame_to_client = {}  
        self.btn_map = {}  
        self.cmd_active = False  
        self.cmd_text = ""  
        self.focused_window = None  
          
        
        self.polybar_windows = []  
        self.window_stack = []  
        self.alt_tab_index = 0  
        self.alt_tab_active = False  
          
        
        self.WM_PROTOCOLS = self.d.intern_atom('WM_PROTOCOLS')  
        self.WM_DELETE_WINDOW = self.d.intern_atom('WM_DELETE_WINDOW')  
        self.WM_STATE = self.d.intern_atom('WM_STATE')  
        self.WM_CHANGE_STATE = self.d.intern_atom('WM_CHANGE_STATE')  
        self.WM_TAKE_FOCUS = self.d.intern_atom('WM_TAKE_FOCUS')  
        self.WM_TRANSIENT_FOR = Xatom.WM_TRANSIENT_FOR  
          
        
        
        self._NET_SUPPORTED = self.d.intern_atom('_NET_SUPPORTED')  
        self._NET_WM_STATE = self.d.intern_atom('_NET_WM_STATE')  
        self._NET_WM_STATE_FULLSCREEN = self.d.intern_atom('_NET_WM_STATE_FULLSCREEN')  
        self._NET_ACTIVE_WINDOW = self.d.intern_atom('_NET_ACTIVE_WINDOW')  
        self._NET_CLIENT_LIST = self.d.intern_atom('_NET_CLIENT_LIST')  
        self._NET_SUPPORTING_WM_CHECK = self.d.intern_atom('_NET_SUPPORTING_WM_CHECK')  
        self._NET_WM_NAME = self.d.intern_atom('_NET_WM_NAME') 
          
        self.cmd_window = self._create_cmd_bar()  
          
        
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
          
        self._setup_ewmh()  
        self._setup_grabs()  
        print("DragonDesktop Running with Full X11 Protocol Support...")  
  
    def print_status(self):  
        """Print current WM status (for debugging)"""  
        print("\n=== DragonDesktop Status ===")  
        print(f"Rendering Mode: {self.renderer.get_mode_string()}")  
        print(f"Camera: x={self.camera.x}, y={self.camera.y}, zoom={self.camera.zoom:.2f}")  
        print(f"Windows: {len(self.windows)}")  
        print(f"Focused: {self.focused_window.title if self.focused_window else 'None'}")  
        print("============================\n")  
  
    def _setup_ewmh(self):  
        """  
        Advertise supported EWMH hints so Polybar/Picom knows what is supported.  
        This fixes the "Disabling module title" error.  
        """  
        try:  
            
            self.root.change_property(  
                self._NET_SUPPORTING_WM_CHECK,  
                Xatom.WINDOW,  
                32,  
                [self.root.id]  
            )  
              
            
            self.root.change_property(  
                self._NET_CLIENT_LIST,  
                Xatom.WINDOW,  
                32,  
                []  
            )  
              
            
            
            supported_atoms = [  
                self._NET_SUPPORTED,  
                self._NET_SUPPORTING_WM_CHECK,  
                self._NET_CLIENT_LIST,  
                self._NET_ACTIVE_WINDOW,  
                self._NET_WM_NAME,  
                self._NET_WM_STATE,  
                self._NET_WM_STATE_FULLSCREEN  
            ]  
            self.root.change_property(  
                self._NET_SUPPORTED,  
                Xatom.ATOM,  
                32,  
                supported_atoms  
            )  
        except Exception as e:  
            print(f"EWMH setup warning: {e}")  
  
    def _update_client_list(self):  
        """Update _NET_CLIENT_LIST (EWMH)"""  
        try:  
            client_ids = [zwin.client.id for zwin in self.windows.values() if zwin.mapped]  
            self.root.change_property(  
                self._NET_CLIENT_LIST,  
                Xatom.WINDOW,  
                32,  
                client_ids  
            )  
        except Exception as e:  
            print(f"Client list update warning: {e}")  
  
    def unfocus_all(self):  
        """Remove focus from all windows"""  
        try:  
            
            self.d.set_input_focus(self.root, X.RevertToPointerRoot, X.CurrentTime)  
            self.focused_window = None  
            
            try:  
                self.root.change_property(  
                    self._NET_ACTIVE_WINDOW,  
                    Xatom.WINDOW,  
                    32,  
                    [X.NONE]  
                )  
            except:  
                pass  
            self.d.sync()  
            print("Unfocused all windows")  
        except Exception as e:  
            print(f"Unfocus error: {e}")  
  
    def focus_window(self, zwin):  
        try:  
            
            if not zwin.mapped:  
                print(f"Cannot focus unmapped window: {zwin.title}")  
                return  
              
            
            protocols = self.get_wm_protocols(zwin.client)  
            if self.WM_TAKE_FOCUS in protocols:  
                self.send_client_message(  
                    zwin.client,   
                    self.WM_PROTOCOLS,  
                    [self.WM_TAKE_FOCUS, X.CurrentTime, 0, 0, 0]  
                )  
              
            
            self.d.set_input_focus(zwin.client, X.RevertToParent, X.CurrentTime)  
            zwin.frame.configure(stack_mode=X.Above)  
            self.focused_window = zwin  
              
            
            self.update_window_stack(zwin)  
              
            
            try:  
                self.root.change_property(  
                    self._NET_ACTIVE_WINDOW,  
                    Xatom.WINDOW,  
                    32,  
                    [zwin.client.id]  
                )  
            except:  
                pass  
              
            self.d.sync()  
            print(f"Focused window: {zwin.title}")  
        except XError.BadMatch:  
            pass  
        except XError.BadWindow:  
            print(f"Window {zwin.client.id} disappeared during focus.")  
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
            event_mask=X.ExposureMask | X.KeyPressMask,  
            override_redirect=True  
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
          
        
        tab_key = self.d.keysym_to_keycode(XK.string_to_keysym("Tab"))  
        for mask in alt_masks:  
            
            self.root.grab_key(tab_key, mask, True, X.GrabModeAsync, X.GrabModeAsync)  
            
            self.root.grab_key(tab_key, mask | X.ShiftMask, True, X.GrabModeAsync, X.GrabModeAsync)  
  
    def is_polybar_window(self, window):  
        """Detect if a window is polybar by checking WM_CLASS and WM_NAME"""  
        try:  
            
            wm_class = window.get_wm_class()  
            if wm_class:  
                if any("polybar" in c.lower() for c in wm_class):  
                    return True  
              
            
            wm_name = window.get_wm_name()  
            if wm_name and "polybar" in wm_name.lower():  
                return True  
              
            
            try:  
                prop = window.get_full_property(self._NET_WM_NAME, 0)  
                if prop and prop.value:  
                    name = prop.value.decode('utf-8', errors='ignore')  
                    if "polybar" in name.lower():  
                        return True  
            except:  
                pass  
        except:  
            pass  
        return False  
  
    def ensure_polybar_stacking(self):  
        """  
        Ensure polybar is always on top, unless there's a fullscreen window.  
        In fullscreen mode, polybar goes to the background.  
        """  
        if not self.polybar_windows:  
            return  
          
        
        fullscreen_win = self.get_fullscreen_window()  
          
        for polybar_win in self.polybar_windows:  
            try:  
                if fullscreen_win:  
                    
                    polybar_win.configure(stack_mode=X.Below, sibling=fullscreen_win.frame)  
                else:  
                    
                    polybar_win.configure(stack_mode=X.Above)  
            except Exception as e:  
                print(f"Polybar stacking error: {e}")  
          
        self.d.sync()  
  
    def update_window_stack(self, zwin):  
        """  
        Update the window stack for alt-tab cycling.  
        Most recently focused window goes to the front.  
        """  
        
        self.window_stack = [w for w in self.window_stack if w.id != zwin.id]  
        
        self.window_stack.insert(0, zwin)  
  
    def handle_alt_tab(self, reverse=False):  
        """  
        Cycle through windows using Alt+Tab (forward) or Alt+Shift+Tab (reverse).  
        """  
        
        tabbable_windows = [  
            w for w in self.window_stack   
            if w.mapped and w.id in self.windows  
        ]  
          
        if len(tabbable_windows) < 2:  
            print("Alt-Tab: Not enough windows to cycle")  
            return  
          
        if not self.alt_tab_active:  
            
            self.alt_tab_active = True  
            self.alt_tab_index = 1  
        else:  
            
            if reverse:  
                self.alt_tab_index = (self.alt_tab_index - 1) % len(tabbable_windows)  
            else:  
                self.alt_tab_index = (self.alt_tab_index + 1) % len(tabbable_windows)  
          
        
        target_window = tabbable_windows[self.alt_tab_index]  
          
        
        target_window.frame.configure(stack_mode=X.Above)  
        self.focus_window(target_window)  
          
        
        self.ensure_polybar_stacking()  
          
        print(f"Alt-Tab: Switched to '{target_window.title}' ({self.alt_tab_index + 1}/{len(tabbable_windows)})")  
  
    def end_alt_tab(self):  
        """  
        End the alt-tab cycling when Alt key is released.  
        """  
        if self.alt_tab_active:  
            self.alt_tab_active = False  
            self.alt_tab_index = 0  
            
            if self.focused_window:  
                self.update_window_stack(self.focused_window)  
            print("Alt-Tab: Cycle ended")  
  
    def get_wm_protocols(self, window):  
        """Get WM_PROTOCOLS supported by window"""  
        try:  
            prop = window.get_full_property(self.WM_PROTOCOLS, Xatom.ATOM)  
            if prop:  
                return prop.value  
        except:  
            pass  
        return []  
  
    def send_client_message(self, window, protocol, data=[0,0,0,0,0]):  
        """Send ClientMessage event (ICCCM)"""  
        try:  
            ev = event.ClientMessage(  
                window=window,  
                client_type=protocol,  
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
            
            frame_coords = zwin.frame.translate_coords(self.root, 0, 0)  
            ev = event.ConfigureNotify(  
                event=zwin.client,  
                window=zwin.client,  
                x=int(frame_coords.x),  
                y=int(frame_coords.y + 25),  
                width=int(geom.width),  
                height=int(geom.height),  
                border_width=0,  
                above_sibling=X.NONE,  
                override_redirect=0  
            )  
            zwin.client.send_event(ev, event_mask=X.StructureNotifyMask)  
            self.d.sync()  
        except Exception as e:  
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
            
            target_zwin = self.windows.get(focus_win.id)  
            if target_zwin:  
                self.close_window(target_zwin)  
                self.renderer.render_world(self.camera, self.windows)  
                self.ensure_polybar_stacking()  
        except Exception as e:  
            print(f"Error closing window: {e}")  
  
    def run(self):  
        while True:  
            try:  
                event = self.d.next_event()  
                
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
                    pass  
                elif event.type == X.ReparentNotify:  
                    pass  
                elif event.type == X.KeyRelease:  
                    
                    self.input.handle_event(event)  
                else:  
                    
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
        
        zwin = self.windows.get(window.id)  
        if zwin:  
            
            if event.value_mask & X.CWX:  
                zwin.world_x = int(event.x)  
            if event.value_mask & X.CWY:  
                zwin.world_y = int(event.y)  
            if event.value_mask & X.CWWidth:  
                zwin.world_w = max(int(event.width), zwin.min_w)  
            if event.value_mask & X.CWHeight:  
                zwin.world_h = max(int(event.height), zwin.min_h)  
            
            self.renderer.render_world(self.camera, self.windows)  
            self.ensure_polybar_stacking()  
            
            self.send_configure_notify(zwin)  
        else:  
            
            try:  
                args = {}  
                if event.value_mask & X.CWX: args['x'] = int(event.x)  
                if event.value_mask & X.CWY: args['y'] = int(event.y)  
                if event.value_mask & X.CWWidth: args['width'] = int(event.width)  
                if event.value_mask & X.CWHeight: args['height'] = int(event.height)  
                if event.value_mask & X.CWBorderWidth: args['border_width'] = int(event.border_width)  
                if event.value_mask & X.CWStackMode: args['stack_mode'] = int(event.stack_mode)  
                window.configure(**args)  
                self.d.sync()  
            except Exception as e:  
                print(f"Configure unmanaged window error: {e}")  
  
    def handle_unmap_notify(self, event):  
        """Window unmaps itself (minimize, hide, etc)"""  
        window_id = event.window.id  
        
        zwin = self.windows.get(window_id)  
        if zwin:  
            
            if hasattr(zwin, 'hidden_by_zoom') and zwin.hidden_by_zoom:  
                
                
                return  
            print(f"Window {window_id} unmapped itself")  
            
            zwin.mapped = False  
            
            try:  
                zwin.frame.unmap()  
            except:  
                pass  
            
            if self.focused_window == zwin:  
                self.focused_window = None  
            self._update_client_list()  
            self.renderer.render_world(self.camera, self.windows)  
            self.ensure_polybar_stacking()  
  
    def handle_destroy_notify(self, event):  
        """Window destroyed (app closed)"""  
        destroyed_window_id = event.window.id  
        
        zwin = self.windows.get(destroyed_window_id)  
        if zwin:  
            print(f"Window {destroyed_window_id} destroyed")  
            
            del self.windows[zwin.client.id]  
            if zwin.frame.id in self.frame_to_client:  
                del self.frame_to_client[zwin.frame.id]  
            if zwin.btn_close.id in self.btn_map:  
                del self.btn_map[zwin.btn_close.id]  
            if zwin.btn_full.id in self.btn_map:  
                del self.btn_map[zwin.btn_full.id]  
            
            self.window_stack = [w for w in self.window_stack if w.id != zwin.id]  
            
            if self.focused_window == zwin:  
                self.focused_window = None  
            
            try:  
                zwin.frame.destroy()  
            except XError.BadWindow:  
                pass  
            self._update_client_list()  
            self.renderer.render_world(self.camera, self.windows)  
            self.ensure_polybar_stacking()  
  
    def handle_property_notify(self, event):  
        """Window property changed (title, hints, etc)"""  
        window_id = event.window.id  
        
        zwin = self.windows.get(window_id)  
        if not zwin:  
            return  
        
        if event.atom == Xatom.WM_NAME:  
            try:  
                new_title = zwin.client.get_wm_name() or "Untitled"  
                zwin.title = new_title  
                self.renderer.render_world(self.camera, self.windows)  
                self.ensure_polybar_stacking()  
            except:  
                pass  
        
        elif event.atom == Xatom.WM_NORMAL_HINTS:  
            try:  
                min_w, min_h, max_w, max_h = self.get_size_hints(zwin.client)  
                zwin.min_w = min_w  
                zwin.min_h = min_h  
                zwin.max_w = max_w  
                zwin.max_h = max_h  
            except:  
                pass  
        
        elif event.atom == self._NET_WM_STATE:  
            try:  
                prop = zwin.client.get_full_property(self._NET_WM_STATE, Xatom.ATOM)  
                if prop and self._NET_WM_STATE_FULLSCREEN in prop.value:  
                    if not zwin.is_fullscreen:  
                        self.toggle_fullscreen(zwin)  
                elif zwin.is_fullscreen:  
                    self.toggle_fullscreen(zwin)  
            except:  
                pass  
  
    def handle_client_message(self, event):  
        """Handle ICCCM/EWMH client messages"""  
        try:  
            
            if event.client_type == self._NET_WM_STATE:  
                window_id = event.window.id  
                zwin = self.windows.get(window_id)  
                if zwin:  
                    
                    action = event.data.data[0]  
                    prop1 = event.data.data[1]  
                    if prop1 == self._NET_WM_STATE_FULLSCREEN:  
                        if action == 1 and not zwin.is_fullscreen:  
                            self.toggle_fullscreen(zwin)  
                        elif action == 0 and zwin.is_fullscreen:  
                            self.toggle_fullscreen(zwin)  
                        elif action == 2:  
                            self.toggle_fullscreen(zwin)  
            elif event.client_type == self.WM_CHANGE_STATE:  
                
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
                self.d.sync()  
                grab_status = self.cmd_window.grab_keyboard(  
                    True,  
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
                if hints.flags & X.PMinSize:  
                    min_w = hints.min_width  
                    min_h = hints.min_height  
                if hints.flags & X.PMaxSize:  
                    max_w = hints.max_width  
                    max_h = hints.max_height  
                if hints.flags & X.PBaseSize:  
                    if min_w == 0: min_w = hints.base_width  
                    if min_h == 0: min_h = hints.base_height  
            return min_w, min_h, max_w, max_h  
        except:  
            return 0, 0, 32768, 32768  
  
    def handle_map_request(self, window):  
        
        try:  
            attrs = window.get_attributes()  
            if attrs.override_redirect:  
                
                if self.is_polybar_window(window):  
                    self.polybar_windows.append(window)  
                    print(f"✓ Detected polybar window: {window.id}")  
                window.map()  
                
                self.ensure_polybar_stacking()  
                return  
        except:  
            return  
          
        
        if window.id in self.windows:  
            
            zwin = self.windows[window.id]  
            zwin.frame.map()  
            zwin.mapped = True  
            self._update_client_list()  
            return  
          
        
        if window.id in self.btn_map:  
            return  
          
        
        try:  
            transient_for = window.get_wm_transient_for()  
            is_dialog = transient_for is not None  
        except:  
            is_dialog = False  
            transient_for = None  
          
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
          
        
        if is_dialog and transient_for and transient_for.id in self.windows:  
            parent_zwin = self.windows[transient_for.id]  
            world_x = parent_zwin.world_x + 50  
            world_y = parent_zwin.world_y + 50  
        else:  
            world_x = self.camera.x  
            world_y = self.camera.y  
          
        sx, sy, sw, sh = self.renderer.project(  
            self.camera, world_x, world_y,  
            target_w, target_h + 25  
        )  
          
        
        frame = self.root.create_window(  
            sx, sy, sw, sh,  
            border_width=1,  
            depth=X.CopyFromParent,  
            visual=X.CopyFromParent,  
            background_pixel=theme['bar'],  
            event_mask=(  
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
            background_pixel=theme['close'],   
            event_mask=X.ButtonPressMask | X.ExposureMask  
        )  
        btn_full = frame.create_window(  
            sw - (btn_size * 2), 0, btn_size, btn_size,  
            border_width=1, depth=X.CopyFromParent, visual=X.CopyFromParent,  
            background_pixel=theme['full'],   
            event_mask=X.ButtonPressMask | X.ExposureMask  
        )  
          
        zwin = ZWindow(  
            window.id,  
            window, frame, btn_close, btn_full,  
            world_x, world_y, target_w, target_h + 25,  
            title=name  
        )  
        zwin.min_w = min_w; zwin.min_h = min_h  
        zwin.max_w = max_w; zwin.max_h = max_h  
        zwin.mapped = True  
        zwin.is_dialog = is_dialog  
        zwin.transient_for = transient_for  
          
        
        self.windows[window.id] = zwin  
        self.frame_to_client[frame.id] = window.id  
        self.btn_map[btn_close.id] = ('close', zwin)  
        self.btn_map[btn_full.id] = ('maximize', zwin)  
          
        
        try:  
            window.change_attributes(  
                event_mask=(  
                    X.PropertyChangeMask |  
                    X.StructureNotifyMask |  
                    X.FocusChangeMask  
                )  
            )  
        except:  
            pass  
          
        
        try:  
            window.change_property(  
                self.WM_STATE, self.WM_STATE, 32,  
                [1, X.NONE]  
            )  
        except:  
            pass  
          
        
        window.reparent(frame, 0, 25)  
          
        
        
        
        
        
        try:  
            window.grab_button(  
                1,                    
                X.AnyModifier,        
                True,                 
                X.ButtonPressMask,    
                X.GrabModeSync,       
                X.GrabModeAsync,      
                X.NONE,               
                X.NONE                
            )  
            print(f"✓ Passive grab set on {name}")  
        except Exception as e:  
            print(f"⚠ Failed to set passive grab on {name}: {e}")  
          
        
        frame.map()  
        btn_close.map()  
        btn_full.map()  
        
          
        
        if is_dialog and transient_for and transient_for.id in self.windows:  
            parent_zwin = self.windows[transient_for.id]  
            frame.configure(stack_mode=X.Above, sibling=parent_zwin.frame)  
          
        self.focus_window(zwin)  
        self._update_client_list()  
        self.renderer.render_world(self.camera, self.windows)  
        self.ensure_polybar_stacking()  
        
        self.send_configure_notify(zwin)  
  
    def close_window(self, zwin):  
        """Close window using ICCCM protocol"""  
        
        protocols = self.get_wm_protocols(zwin.client)  
        if self.WM_DELETE_WINDOW in protocols:  
            self.send_client_message(  
                zwin.client,  
                self.WM_PROTOCOLS,  
                [self.WM_DELETE_WINDOW, X.CurrentTime, 0, 0, 0]  
            )  
        else:  
            
            try:  
                zwin.client.kill_client()  
            except:  
                pass  
        
  
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
          
        
        try:  
            if zwin.is_fullscreen:  
                zwin.client.change_property(  
                    self._NET_WM_STATE,  
                    Xatom.ATOM,  
                    32,  
                    [self._NET_WM_STATE_FULLSCREEN]  
                )  
            else:  
                zwin.client.change_property(  
                    self._NET_WM_STATE,  
                    Xatom.ATOM,  
                    32,  
                    []  
                )  
        except:  
            pass  
          
        self.renderer.render_world(self.camera, self.windows)  
        self.send_configure_notify(zwin)  
          
        
        self.ensure_polybar_stacking()  
  
    def zoom_camera(self, direction):  
        self.camera.zoom += (0.1 * direction)  
        self.camera.zoom = max(0.11, min(self.camera.zoom, 5.0))  
        print(f"Zoom: {self.camera.zoom:.2f}")  
        try:  
            self.renderer.render_world(self.camera, self.windows)  
            self.ensure_polybar_stacking()  
        except Exception as e:  
            print(f"Renderer Error: {e}")  
  
    def get_window_by_frame(self, frame_id):  
        
        client_id = self.frame_to_client.get(frame_id)  
        if client_id:  
            return self.windows.get(client_id)  
        return None  
  
    def save_camera_pos(self, index):  
        self.camera.saved_spots[index] = (self.camera.x, self.camera.y, self.camera.zoom)  
        print(f"Saved Camera Position {index}")  
  
    def load_camera_pos(self, index):  
        if index in self.camera.saved_spots:  
            x, y, z = self.camera.saved_spots[index]  
            self.camera.x = x; self.camera.y = y; self.camera.zoom = z  
            print(f"Jumped to Position {index}")  
            self.renderer.render_world(self.camera, self.windows)  
            self.ensure_polybar_stacking()  
