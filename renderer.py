from Xlib import X    
from Xlib import error as XError    
import hashlib    
from PIL import Image    
import sys    
import subprocess    
  
class Renderer:  
    """  
    Dual-mode renderer:  
    - COMPOSITOR mode: Picom handles painting, we only do layout  
    - CPU mode: We manually paint everything 
    """  
    MODE_CPU = 0  
    MODE_COMPOSITOR = 1  
  
    def __init__(self, root, display, config):  
        self.root = root  
        self.display = display  
        self.screen = display.screen()  
        self.colormap = self.screen.default_colormap  
        self.depth = self.screen.root_depth  
        self.config = config  
        self.color_cache = {}  
          
        
        self.bg_pixmap = None  
        self.bg_width = 0  
        self.bg_height = 0  
          
        
        self.mode = self.MODE_CPU  
        self.picom_process = None  
        self.compositor_name = None  
          
        
        try:  
            self.font = self.display.open_font('fixed')  
        except:  
            self.font = None  
          
        
        gc_args = {  
            'foreground': self.alloc_color('black'),  
            'background': self.alloc_color('white')  
        }  
        if self.font:  
            gc_args['font'] = self.font.id  
        self.gc = self.root.create_gc(**gc_args)  
          
        
        self._initialize_compositor()  
  
    def _initialize_compositor(self):  
        """  
        Strategy:  
        1. Check if a compositor is already running  
        2. If config says use_picom=true, try to start it  
        3. Fall back to CPU mode if picom fails  
        """  
        use_picom = self.config.get("use_picom", True)  
        picom_config = self.config.get("picom_config", "~/.config/picom/picom.conf")  
          
        if use_picom:  
            
            if self._detect_compositor():  
                print(f"✓ Compositor detected: {self.compositor_name}")  
                self.mode = self.MODE_COMPOSITOR  
            else:  
                
                if self._start_picom(picom_config):  
                    print("✓ Picom started successfully")  
                    self.mode = self.MODE_COMPOSITOR  
                else:  
                    print("⚠ Picom failed to start, using CPU mode")  
                    self.mode = self.MODE_CPU  
        else:  
            print("✓ CPU rendering mode (picom disabled in config)")  
            self.mode = self.MODE_CPU  
          
        
        self._setup_wallpaper()  
  
    def _detect_compositor(self):  
        """  
        Detect if a compositor is running by checking for  
        _NET_WM_CM_S0 selection owner (EWMH composite manager)  
        """  
        try:  
            atom_name = f"_NET_WM_CM_S{self.display.get_default_screen()}"  
            cm_atom = self.display.intern_atom(atom_name)  
            owner = self.display.get_selection_owner(cm_atom)  
            if owner and owner != X.NONE:  
                
                try:  
                    net_wm_name = self.display.intern_atom('_NET_WM_NAME')  
                    prop = owner.get_full_property(net_wm_name, X.AnyPropertyType)  
                    if prop and prop.value:  
                        self.compositor_name = prop.value.decode('utf-8', errors='ignore')  
                    else:  
                        self.compositor_name = "Unknown Compositor"  
                except:  
                    self.compositor_name = "Unknown Compositor"  
                return True  
        except Exception as e:  
            print(f"Compositor detection error: {e}")  
        return False  
  
    def _start_picom(self, config_path):  
        """  
        Launch picom as a subprocess with proper error handling  
        """  
        try:  
            
            import os  
            config_path = os.path.expanduser(config_path)  
              
            
            cmd = ["picom"]  
              
            
            if os.path.exists(config_path):  
                cmd.extend(["--config", config_path])  
                print(f"Using picom config: {config_path}")  
            else:  
                print(f"⚠ Picom config not found: {config_path}")  
                print("Using picom defaults")  
              
            
            cmd.extend([  
                "--backend", "glx",  
                "--vsync",           
                "--no-fading-openclose",  
                "--no-fading-destroyed-argb",  
            ])  
              
            
            self.picom_process = subprocess.Popen(  
                cmd,  
                stdout=subprocess.DEVNULL,  
                stderr=subprocess.PIPE,  
                start_new_session=True  
            )  
              
            
            import time  
            time.sleep(0.5)  
              
            
            if self.picom_process.poll() is None:  
                
                if self._detect_compositor():  
                    self.compositor_name = "picom"  
                    return True  
                else:  
                    print("⚠ Picom started but didn't register compositor selection")  
                    return False  
            else:  
                
                stderr = self.picom_process.stderr.read().decode('utf-8', errors='ignore')  
                print(f"⚠ Picom failed to start: {stderr}")  
                return False  
        except FileNotFoundError:  
            print("⚠ Picom executable not found. Install with: sudo apt install picom")  
            return False  
        except Exception as e:  
            print(f"⚠ Failed to start picom: {e}")  
            return False  
  
    def _setup_wallpaper(self):  
        """  
        Use 'feh' to handle wallpaper. It sets the necessary X11 atoms  
        (_XROOTPMAP_ID) so that Picom, Polybar, and others see it correctly.  
        """  
        path = self.config.get("wallpaper_path", "")  
        if not path:  
            print("⚠ No wallpaper path in config.json")  
            return  
          
        import os  
        path = os.path.expanduser(path)  
          
        if not os.path.exists(path):  
            print(f"⚠ Wallpaper file not found: {path}")  
            return  
          
        try:  
            
            subprocess.run(["feh", "--bg-fill", path], check=True)  
            
            self.bg_width = self.root.get_geometry().width  
            self.bg_height = self.root.get_geometry().height  
            print(f"✓ Wallpaper set using feh: {path}")  
        except FileNotFoundError:  
            print("⚠ 'feh' is not installed. Run: sudo apt install feh")  
        except Exception as e:  
            print(f"⚠ Failed to set wallpaper: {e}")  
  
    def draw_wallpaper_cpu(self):  
        """  
        CPU MODE: Trigger X11 to repaint the background.  
        """  
        
        
        self.root.clear_area()  
  
    def alloc_color(self, name):  
        try:  
            return self.colormap.alloc_named_color(name).pixel  
        except:  
            return self.display.screen().white_pixel  
  
    def get_pixel(self, r, g, b):  
        r = max(0, min(65535, int(r)))  
        g = max(0, min(65535, int(g)))  
        b = max(0, min(65535, int(b)))  
        key = (r, g, b)  
        if key in self.color_cache:  
            return self.color_cache[key]  
        try:  
            color = self.colormap.alloc_color(r, g, b)  
            self.color_cache[key] = color.pixel  
            return color.pixel  
        except:  
            return self.display.screen().white_pixel  
  
    def create_theme(self, app_name):  
        if not app_name:  
            app_name = "unknown"  
        hash_bytes = hashlib.md5(app_name.encode('utf-8')).digest()  
        r_base = (hash_bytes[0] % 150) + 50  
        g_base = (hash_bytes[1] % 150) + 50  
        b_base = (hash_bytes[2] % 150) + 50  
        r16 = r_base * 257  
        g16 = g_base * 257  
        b16 = b_base * 257  
        full_pixel = self.get_pixel(r16 * 1.3, g16 * 1.3, b16 * 1.3)  
        bar_pixel = self.get_pixel(r16, g16, b16)  
        close_pixel = self.get_pixel(r16 * 0.6, g16 * 0.6, b16 * 0.6)  
        return {'bar': bar_pixel, 'full': full_pixel, 'close': close_pixel}  
  
    def render_cmd_bar(self, bar_window, text, screen_w, screen_h):  
        bar_window.clear_area()  
        try:  
            bar_window.draw_text(self.gc, 10, 25, text.encode('utf-8'))  
        except:  
            pass  
  
    def project(self, camera, wx, wy, ww, wh):  
        """  
        Transform world coordinates to screen coordinates.  
        This ALWAYS runs regardless of compositor mode.  
        """  
        screen = self.root.get_geometry()  
        half_w = screen.width // 2  
        half_h = screen.height // 2  
        sx = int((wx - camera.x) * camera.zoom + half_w)  
        sy = int((wy - camera.y) * camera.zoom + half_h)  
        sw = int(ww * camera.zoom)  
        sh = int(wh * camera.zoom)  
        sw = max(5, min(sw, 30000))  
        sh = max(5, min(sh, 30000))  
        return sx, sy, sw, sh  
  
    def render_world(self, camera, windows):  
        """  
        SPLIT ARCHITECTURE:  
        - Layout calculations (project, configure) ALWAYS run  
        - Painting operations (draw_wallpaper) ONLY in CPU mode  
          
        Picom handles:  
        - VSync  
        - Shadows  
        - Transparency  
        - Screen painting  
          
        We handle:  
        - Window positioning (ConfigureWindow)  
        - Semantic zoom calculations  
        - Layout logic  
        """  
        
        
        
        if self.mode == self.MODE_CPU:  
            
            self.draw_wallpaper_cpu()  
        
          
        
        
        
        show_content = camera.zoom > 0.5  
        dead_windows = []  
          
        for frame_id, win in windows.items():  
            try:  
                
                if not win.mapped:  
                    continue  
                  
                
                if win.is_fullscreen:  
                    scaled_title = 0  
                else:  
                    scaled_title = int(25 * camera.zoom)  
                    if scaled_title < 8:  
                        scaled_title = 8  
                  
                sx, sy, sw, sh = self.project(  
                    camera, win.world_x, win.world_y, win.world_w, win.world_h  
                )  
                  
                
                if sw < 5 or sh < 5:  
                    continue  
                  
                is_fixed_size = (win.min_w == win.max_w) and (win.min_w > 0)  
                if is_fixed_size and not win.is_fullscreen:  
                    sw = int(win.min_w * camera.zoom)  
                    sh = int(win.min_h * camera.zoom) + scaled_title  
                  
                
                try:  
                    win.frame.configure(x=sx, y=sy, width=sw, height=sh)  
                    win.frame.map()  
                except XError.BadWindow:  
                    dead_windows.append(frame_id)  
                    continue  
                  
                
                if scaled_title > 0 and not win.is_fullscreen:  
                    try:  
                        win.btn_close.map()  
                        win.btn_full.map()  
                        win.btn_close.configure(  
                            x=sw - scaled_title,  
                            y=0,  
                            width=scaled_title,  
                            height=scaled_title  
                        )  
                        win.btn_full.configure(  
                            x=sw - (scaled_title * 2),  
                            y=0,  
                            width=scaled_title,  
                            height=scaled_title  
                        )  
                    except:  
                        pass  
                      
                    
                    text_area_w = sw - (scaled_title * 2)  
                    if text_area_w > 10:  
                        try:  
                            win.frame.clear_area(x=0, y=0, width=text_area_w, height=scaled_title)  
                            if show_content and camera.zoom > 0.7:  
                                text_y = int(scaled_title * 0.7)  
                                win.frame.draw_text(self.gc, 5, text_y, win.title.encode('utf-8'))  
                        except:  
                            pass  
                else:  
                    
                    try:  
                        win.btn_close.unmap()  
                        win.btn_full.unmap()  
                    except:  
                        pass  
                  
                
                try:  
                    grip_size = min(scaled_title, 15)  
                    grip_x = sw - grip_size  
                    grip_y = sh - grip_size  
                    
                    grip_color = self.get_pixel(40000, 40000, 40000)  
                    self.gc.change(foreground=grip_color)  
                    win.frame.fill_rectangle(  
                        self.gc,  
                        grip_x, grip_y,  
                        grip_size, grip_size  
                    )  
                except:  
                    pass  
                  
                
                if show_content:  
                    
                    try:  
                        
                        if hasattr(win, 'hidden_by_zoom') and win.hidden_by_zoom:  
                            win.client.map()  
                            win.hidden_by_zoom = False  
                          
                        
                        win.client.map()  
                          
                        avail_w = sw  
                        avail_h = sh - scaled_title  
                          
                        scaled_min_w = int(win.min_w * camera.zoom) if win.min_w > 0 else avail_w  
                        scaled_min_h = int(win.min_h * camera.zoom) if win.min_h > 0 else avail_h  
                          
                        final_w = max(avail_w, scaled_min_w)  
                        final_h = max(avail_h, scaled_min_h)  
                          
                        off_x = max(0, (avail_w - final_w) // 2)  
                        off_y = max(0, scaled_title + (avail_h - final_h) // 2)  
                          
                        win.client.configure(  
                            x=off_x, y=off_y,  
                            width=final_w, height=final_h,  
                            border_width=0  
                        )  
                    except XError.BadWindow:  
                        dead_windows.append(frame_id)  
                        continue  
                    except:  
                        pass  
                else:  
                    
                    try:  
                        
                        if not hasattr(win, 'hidden_by_zoom') or not win.hidden_by_zoom:  
                            win.hidden_by_zoom = True  
                            win.client.unmap()  
                          
                        win.frame.clear_area(  
                            x=0, y=0,  
                            width=sw, height=sh  
                        )  
                    except:  
                        pass  
              
            except XError.BadWindow:  
                dead_windows.append(frame_id)  
            except Exception as e:  
                print(f"Render error on win {frame_id}: {e}")  
                import traceback  
                traceback.print_exc()  
          
        
        for fid in dead_windows:  
            if fid in windows:  
                del windows[fid]  
          
        
        self.display.flush()  
  
    def toggle_compositor(self):  
        """  
        Runtime toggle between CPU and Compositor modes.  
        Useful for debugging or if picom crashes.  
        """  
        if self.mode == self.MODE_CPU:  
            
            if self._detect_compositor():  
                self.mode = self.MODE_COMPOSITOR  
                print("✓ Switched to COMPOSITOR mode")  
                return True  
            elif self._start_picom(self.config.get("picom_config", "~/.config/picom/picom.conf")):  
                self.mode = self.MODE_COMPOSITOR  
                print("✓ Started picom and switched to COMPOSITOR mode")  
                return True  
            else:  
                print("⚠ Failed to enable compositor")  
                return False  
        else:  
            
            self.mode = self.MODE_CPU  
            print("✓ Switched to CPU mode")  
            
            if self.picom_process and self.picom_process.poll() is None:  
                try:  
                    self.picom_process.terminate()  
                    print("✓ Stopped picom")  
                except:  
                    pass  
            return True  
  
    def get_mode_string(self):  
        """Return human-readable mode string"""  
        if self.mode == self.MODE_COMPOSITOR:  
            return f"COMPOSITOR ({self.compositor_name})"  
        else:  
            return "CPU"  
  
    def cleanup(self):  
        """Cleanup resources on WM exit"""  
        
        
        pass  
