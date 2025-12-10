from Xlib import X
from Xlib import error as XError
import hashlib
from PIL import Image
import sys 

class Renderer:
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

        try:
            self.font = self.display.open_font('fixed')
        except:
            self.font = None

        gc_args = {
            'foreground': self.alloc_color('black'),
            'background': self.alloc_color('white')
        }
        if self.font: gc_args['font'] = self.font.id 
        self.gc = self.root.create_gc(**gc_args)
        
        self._setup_static_wallpaper()

    def alloc_color(self, name):
        try: return self.colormap.alloc_named_color(name).pixel
        except: return self.display.screen().white_pixel

    def get_pixel(self, r, g, b):
        r = max(0, min(65535, int(r)))
        g = max(0, min(65535, int(g)))
        b = max(0, min(65535, int(b)))
        
        key = (r, g, b)
        if key in self.color_cache: return self.color_cache[key]
        
        try:
            color = self.colormap.alloc_color(r, g, b)
            self.color_cache[key] = color.pixel
            return color.pixel
        except:
            return self.display.screen().white_pixel

    def _setup_static_wallpaper(self):
        path = self.config.get("wallpaper_path", "")
        if not path: return

        try:
            img = Image.open(path).convert("RGB")
            geom = self.root.get_geometry()
            scr_w = geom.width
            scr_h = geom.height
            
            print(f"Loading Wallpaper: {path}")
            resized = img.resize((scr_w, scr_h), Image.LANCZOS)
            
            # X11 usually expects 32-bit padded data (BGRX) even for 24-bit depth
            try:
                data = resized.tobytes("raw", "BGRX")
                bpp = 4 # Bytes per pixel
            except:
                data = resized.tobytes("raw", "RGB")
                bpp = 3

            self.bg_pixmap = self.root.create_pixmap(scr_w, scr_h, self.depth)
            bg_gc = self.bg_pixmap.create_gc()
            
            # --- FIX: CHUNKED UPLOAD ---
            # X11 Request Size Limit is ~262KB. We must split the image.
            bytes_per_row = scr_w * bpp
            
            # Calculate max rows we can send in one packet (target 200KB to be safe)
            max_packet_size = 200000 
            rows_per_chunk = max_packet_size // bytes_per_row
            if rows_per_chunk < 1: rows_per_chunk = 1
            
            total_rows = scr_h
            current_row = 0
            
            # Slice the data byte-array and upload in parts
            while current_row < total_rows:
                chunk_h = min(rows_per_chunk, total_rows - current_row)
                
                start_byte = current_row * bytes_per_row
                end_byte = start_byte + (chunk_h * bytes_per_row)
                
                chunk_data = data[start_byte:end_byte]
                
                self.bg_pixmap.put_image(
                    bg_gc, 
                    0, current_row,   # x, y
                    scr_w, chunk_h,   # width, height
                    X.ZPixmap, 
                    self.depth, 
                    0,                # left_pad
                    chunk_data
                )
                current_row += chunk_h

            self.bg_width = scr_w
            self.bg_height = scr_h
            
            self.root.change_attributes(background_pixmap=self.bg_pixmap)
            self.root.clear_area()
            self.display.flush()
            print("Wallpaper loaded successfully.")
            
        except Exception as e:
            print(f"Wallpaper Setup Error: {e}")
            self.bg_pixmap = None

    def draw_wallpaper(self, camera):
        if self.bg_pixmap:
            try:
                self.bg_pixmap.copy_area(
                    self.gc, 0, 0, self.bg_width, self.bg_height, 
                    self.root, 0, 0
                )
            except:
                try:
                    self.root.clear_area(0, 0, self.bg_width, self.bg_height, False)
                except: pass
        else:
            self.root.clear_area()

    def create_theme(self, app_name):
        if not app_name: app_name = "unknown"
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
        except: pass

    def project(self, camera, wx, wy, ww, wh):
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
        # 1. DRAW STATIC WALLPAPER  
        self.draw_wallpaper(camera)  
    
        # 2. Draw Windows  
        show_content = camera.zoom > 0.5  
        dead_windows = []  
    
        for frame_id, win in windows.items():  
            try:  
                # --- CALCULATION LOGIC ---  
                if win.is_fullscreen:  
                    scaled_title = 0  
                else:  
                    scaled_title = int(25 * camera.zoom)  
                    # IMPORTANT: Don't let title bar disappear at low zoom  
                    if scaled_title < 8:  
                        scaled_title = 8  
    
                sx, sy, sw, sh = self.project(  
                    camera, win.world_x, win.world_y, win.world_w, win.world_h  
                )  
    
                # Sanity check: Ensure window has minimum renderable size  
                if sw < 5 or sh < 5:  
                    continue  
                
                is_fixed_size = (win.min_w == win.max_w) and (win.min_w > 0)  
                if is_fixed_size and not win.is_fullscreen:  
                    sw = int(win.min_w * camera.zoom)  
                    sh = int(win.min_h * camera.zoom) + scaled_title  
    
                # --- CONFIGURE FRAME (Wrapped separately to catch errors) ---  
                try:  
                    win.frame.configure(x=sx, y=sy, width=sw, height=sh)  
                    win.frame.map()  # Ensure it's visible  
                except XError.BadWindow:  
                    dead_windows.append(frame_id)  
                    continue  
                
                # --- HANDLE TITLE BAR & BUTTONS ---  
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
                        pass  # Buttons might be too small, skip them  
                    
                    # Draw Title  
                    text_area_w = sw - (scaled_title * 2)  
                    if text_area_w > 10:  
                        try:  
                            win.frame.clear_area(x=0, y=0, width=text_area_w, height=scaled_title)  
                            if show_content and camera.zoom > 0.7:  # Only show text at readable zoom  
                                text_y = int(scaled_title * 0.7)  
                                win.frame.draw_text(self.gc, 5, text_y, win.title.encode('utf-8'))  
                        except:  
                            pass  
                else:  
                    # Hide buttons in fullscreen or when too small  
                    try:  
                        win.btn_close.unmap()  
                        win.btn_full.unmap()  
                    except:  
                        pass  
                    
                # --- HANDLE CLIENT CONTENT ---  
                if show_content:  
                    # HIGH DETAIL: Show actual app  
                    try:  
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
                        pass  # Client might not accept this configuration  
                else:  
                    # LOW DETAIL: Show colored block placeholder  
                    try:  
                        win.client.unmap()  
                        # Clear the entire frame to show background color  
                        win.frame.clear_area(  
                            x=0,   
                            y=0,  # Clear entire frame including title area  
                            width=sw,   
                            height=sh  
                        )  
                    except:  
                        pass  
                    
            except XError.BadWindow:  
                dead_windows.append(frame_id)  
            except Exception as e:  
                print(f"Render error on win {frame_id}: {e}")  
                import traceback  
                traceback.print_exc()  
    
        # Clean up dead windows  
        for fid in dead_windows:  
            if fid in windows:  
                del windows[fid]  
    