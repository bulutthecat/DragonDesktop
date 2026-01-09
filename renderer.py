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
    - CPU mode: We manually paint everything (current behavior)  
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
          
        # Wallpaper resources  
        self.bg_pixmap = None  
        self.bg_width = 0  
        self.bg_height = 0  
          
        # Compositor state  
        self.mode = self.MODE_CPU  
        self.picom_process = None  
        self.compositor_name = None  
          
        # Font setup  
        try:  
            self.font = self.display.open_font('fixed')  
        except:  
            self.font = None  
          
        # Graphics context  
        gc_args = {  
            'foreground': self.alloc_color('black'),  
            'background': self.alloc_color('white')  
        }  
        if self.font:  
            gc_args['font'] = self.font.id  
          
        self.gc = self.root.create_gc(**gc_args)  
          
        # Auto-detect compositor or start picom  
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
            # Check if compositor already running  
            if self._detect_compositor():  
                print(f"✓ Compositor detected: {self.compositor_name}")  
                self.mode = self.MODE_COMPOSITOR  
            else:  
                # Try to start picom  
                if self._start_picom(picom_config):  
                    print("✓ Picom started successfully")  
                    self.mode = self.MODE_COMPOSITOR  
                else:  
                    print("⚠ Picom failed to start, using CPU mode")  
                    self.mode = self.MODE_CPU  
        else:  
            print("✓ CPU rendering mode (picom disabled in config)")  
            self.mode = self.MODE_CPU  
          
        # Load wallpaper based on mode  
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
                # Try to identify which compositor  
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
            # Expand user path  
            import os  
            config_path = os.path.expanduser(config_path)  
              
            # Build picom command  
            cmd = ["picom"]  
              
            # Add config if it exists  
            if os.path.exists(config_path):  
                cmd.extend(["--config", config_path])  
                print(f"Using picom config: {config_path}")  
            else:  
                print(f"⚠ Picom config not found: {config_path}")  
                print("Using picom defaults")  
              
            # Add some sensible defaults for a WM  
            cmd.extend([  
                "--backend", "glx",  # GPU-accelerated  
                "--vsync",           # Prevent tearing  
                "--no-fading-openclose",  # Faster window operations  
                "--no-fading-destroyed-argb",  
            ])  
              
            # Start picom  
            self.picom_process = subprocess.Popen(  
                cmd,  
                stdout=subprocess.DEVNULL,  
                stderr=subprocess.PIPE,  
                start_new_session=True  # Don't kill picom when WM exits  
            )  
              
            # Give picom time to register  
            import time  
            time.sleep(0.5)  
              
            # Verify it started  
            if self.picom_process.poll() is None:  
                # Still running, verify compositor selection  
                if self._detect_compositor():  
                    self.compositor_name = "picom"  
                    return True  
                else:  
                    print("⚠ Picom started but didn't register compositor selection")  
                    return False  
            else:  
                # Process died  
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
        Setup wallpaper based on rendering mode  
        """  
        path = self.config.get("wallpaper_path", "")  
        if not path:  
            return  
          
        if self.mode == self.MODE_COMPOSITOR:  
            self._setup_static_wallpaper_compositor()  
        else:  
            self._setup_static_wallpaper_cpu()  
      
    def _setup_static_wallpaper_compositor(self):  
        """  
        COMPOSITOR MODE: Set wallpaper ONCE, let picom handle it.  
        This is the critical fix - we don't repaint in render_world.  
        """  
        path = self.config.get("wallpaper_path", "")  
        if not path:  
            return  
          
        try:  
            img = Image.open(path).convert("RGB")  
            geom = self.root.get_geometry()  
            scr_w = geom.width  
            scr_h = geom.height  
              
            print(f"Loading wallpaper (COMPOSITOR mode): {path}")  
            resized = img.resize((scr_w, scr_h), Image.LANCZOS)  
              
            # Upload to pixmap  
            try:  
                data = resized.tobytes("raw", "BGRX")  
                bpp = 4  
            except:  
                data = resized.tobytes("raw", "RGB")  
                bpp = 3  
              
            self.bg_pixmap = self.root.create_pixmap(scr_w, scr_h, self.depth)  
            bg_gc = self.bg_pixmap.create_gc()  
              
            # Chunked upload to avoid X11 request size limits  
            bytes_per_row = scr_w * bpp  
            max_packet_size = 200000  
            rows_per_chunk = max(1, max_packet_size // bytes_per_row)  
              
            current_row = 0  
            while current_row < scr_h:  
                chunk_h = min(rows_per_chunk, scr_h - current_row)  
                start_byte = current_row * bytes_per_row  
                end_byte = start_byte + (chunk_h * bytes_per_row)  
                chunk_data = data[start_byte:end_byte]  
                  
                self.bg_pixmap.put_image(  
                    bg_gc,  
                    0, current_row,  
                    scr_w, chunk_h,  
                    X.ZPixmap,  
                    self.depth,  
                    0,  
                    chunk_data  
                )  
                current_row += chunk_h  
              
            self.bg_width = scr_w  
            self.bg_height = scr_h  
              
            # CRITICAL: Set as root background and STOP  
            # Picom will composite this, we don't touch it again  
            self.root.change_attributes(background_pixmap=self.bg_pixmap)  
            self.root.clear_area()  
            self.display.flush()  
              
            print("✓ Wallpaper set (picom will handle compositing)")  
              
        except Exception as e:  
            print(f"Wallpaper setup error: {e}")  
            self.bg_pixmap = None  
      
    def _setup_static_wallpaper_cpu(self):  
        """  
        CPU MODE: Same as before, we'll repaint in render_world  
        """  
        path = self.config.get("wallpaper_path", "")  
        if not path:  
            return  
          
        try:  
            img = Image.open(path).convert("RGB")  
            geom = self.root.get_geometry()  
            scr_w = geom.width  
            scr_h = geom.height  
              
            print(f"Loading wallpaper (CPU mode): {path}")  
            resized = img.resize((scr_w, scr_h), Image.LANCZOS)  
              
            try:  
                data = resized.tobytes("raw", "BGRX")  
                bpp = 4  
            except:  
                data = resized.tobytes("raw", "RGB")  
                bpp = 3  
              
            self.bg_pixmap = self.root.create_pixmap(scr_w, scr_h, self.depth)  
            bg_gc = self.bg_pixmap.create_gc()  
              
            # Chunked upload  
            bytes_per_row = scr_w * bpp  
            max_packet_size = 200000  
            rows_per_chunk = max(1, max_packet_size // bytes_per_row)  
              
            current_row = 0  
            while current_row < scr_h:  
                chunk_h = min(rows_per_chunk, scr_h - current_row)  
                start_byte = current_row * bytes_per_row  
                end_byte = start_byte + (chunk_h * bytes_per_row)  
                chunk_data = data[start_byte:end_byte]  
                  
                self.bg_pixmap.put_image(  
                    bg_gc,  
                    0, current_row,  
                    scr_w, chunk_h,  
                    X.ZPixmap,  
                    self.depth,  
                    0,  
                    chunk_data  
                )  
                current_row += chunk_h  
              
            self.bg_width = scr_w  
            self.bg_height = scr_h  
              
            print("✓ Wallpaper loaded (will repaint each frame)")  
              
        except Exception as e:  
            print(f"Wallpaper setup error: {e}")  
            self.bg_pixmap = None  
      
    def draw_wallpaper_cpu(self):  
        """  
        CPU MODE ONLY: Manually repaint wallpaper to prevent trails.  
        This is NEVER called in compositor mode.  
        """  
        if self.bg_pixmap:  
            try:  
                # Copy pixmap to root window  
                self.bg_pixmap.copy_area(  
                    self.gc, 0, 0, self.bg_width, self.bg_height,  
                    self.root, 0, 0  
                )  
            except:  
                try:  
                    self.root.clear_area(0, 0, self.bg_width, self.bg_height, False)  
                except:  
                    pass  
        else:  
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
          
        # ========================================  
        # PAINTING: Conditional based on mode  
        # ========================================  
        if self.mode == self.MODE_CPU:  
            # CPU mode: We must repaint wallpaper every frame  
            self.draw_wallpaper_cpu()  
        # else: Compositor mode - DO NOTHING, picom owns the screen  
          
        # ========================================  
        # LAYOUT: Always runs (compositor can't do this)  
        # ========================================  
        show_content = camera.zoom > 0.5  
        dead_windows = []  
          
        for frame_id, win in windows.items():  
            try:  
                # Skip unmapped windows  
                if not win.mapped:  
                    continue  
                  
                # ---- GEOMETRY CALCULATIONS ----  
                if win.is_fullscreen:  
                    scaled_title = 0  
                else:  
                    scaled_title = int(25 * camera.zoom)  
                    if scaled_title < 8:  
                        scaled_title = 8  
                  
                sx, sy, sw, sh = self.project(  
                    camera, win.world_x, win.world_y, win.world_w, win.world_h  
                )  
                  
                # Sanity checks  
                if sw < 5 or sh < 5:  
                    continue  
                  
                is_fixed_size = (win.min_w == win.max_w) and (win.min_w > 0)  
                if is_fixed_size and not win.is_fullscreen:  
                    sw = int(win.min_w * camera.zoom)  
                    sh = int(win.min_h * camera.zoom) + scaled_title  
                  
                # ---- CONFIGURE FRAME (Layout) ----  
                try:  
                    win.frame.configure(x=sx, y=sy, width=sw, height=sh)  
                    win.frame.map()  
                except XError.BadWindow:  
                    dead_windows.append(frame_id)  
                    continue  
                  
                # ---- TITLEBAR & BUTTONS ----  
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
                      
                    # Draw title text  
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
                    # Hide buttons  
                    try:  
                        win.btn_close.unmap()  
                        win.btn_full.unmap()  
                    except:  
                        pass  
                  
                # ---- CLIENT WINDOW CONTENT ----  
                if show_content:  
                    # High detail: show actual app  
                    try:  
                        # [FIX] If we previously hid this window for zoom, bring it back now
                        if hasattr(win, 'hidden_by_zoom') and win.hidden_by_zoom:
                            win.client.map()
                            win.hidden_by_zoom = False
                        
                        # Fallback map to ensure visibility
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
                    # Low detail: show colored placeholder  
                    try:  
                        # [FIX] Mark this as an internal unmap so the WM ignores the event
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
          
        # Cleanup dead windows  
        for fid in dead_windows:  
            if fid in windows:  
                del windows[fid]  
          
        # Flush to X server  
        self.display.flush()
      
    def toggle_compositor(self):  
        """  
        Runtime toggle between CPU and Compositor modes.  
        Useful for debugging or if picom crashes.  
        """  
        if self.mode == self.MODE_CPU:  
            # Try to enable compositor  
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
            # Switch to CPU mode  
            self.mode = self.MODE_CPU  
            print("✓ Switched to CPU mode")  
            # Optionally kill picom  
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
        # Don't kill picom on exit (start_new_session=True means it stays alive)  
        # This is intentional - picom can serve other apps  
        pass  