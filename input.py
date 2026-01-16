from Xlib import X, XK  
  
class InputHandler:  
    def __init__(self, wm):  
        self.wm = wm   
        self.drag_mode = None   
        self.drag_start_event = None  
        
        self.drag_start_cam = (0, 0)  
        self.drag_start_frame = {'x': 0, 'y': 0, 'w': 0, 'h': 0}  
  
    def handle_event(self, event):  
        
        if event.type == X.KeyPress and self.wm.cmd_active:  
            self._on_key_command(event)  
            return  
          
        
        if event.type == X.KeyPress:  
            self._on_key_normal(event)  
        elif event.type == X.ButtonPress:  
            self._on_click(event)  
        elif event.type == X.MotionNotify:  
            self._on_motion(event)  
        elif event.type == X.ButtonRelease:  
            self._on_release(event)  
        
        elif event.type == X.KeyRelease:  
            self._on_key_release(event)  
        
        elif event.type == X.Expose and hasattr(self.wm, 'cmd_window') and event.window.id == self.wm.cmd_window.id:   
            self.wm.draw_bar()  
  
    def _on_key_normal(self, event):  
        keysym = self.wm.d.keycode_to_keysym(event.detail, 0)  
          
        
        if keysym == XK.string_to_keysym("Tab") and (event.state & X.Mod1Mask):  
            
            reverse = bool(event.state & X.ShiftMask)  
            self.wm.handle_alt_tab(reverse=reverse)  
            return  
          
        
        if keysym == XK.XK_F4 and (event.state & X.Mod1Mask):  
            self.wm.close_focused_window()  
            return  
          
        
        f_map = { XK.XK_F1: 1, XK.XK_F2: 2, XK.XK_F3: 3, XK.XK_F4: 4 }  
        if keysym in f_map:  
            index = f_map[keysym]  
            
            if (event.state & X.Mod4Mask) and (event.state & X.ControlMask):  
                self.wm.save_camera_pos(index)  
            
            elif (event.state & X.Mod4Mask):  
                self.wm.load_camera_pos(index)  
          
        
        elif (event.state & X.Mod4Mask) and keysym == XK.string_to_keysym("space"):  
            self.wm.toggle_cmd_bar()  
  
    def _on_key_release(self, event):  
        """Handle key release events"""  
        keysym = self.wm.d.keycode_to_keysym(event.detail, 0)  
          
        
        
        if keysym in [XK.XK_Alt_L, XK.XK_Alt_R]:  
            self.wm.end_alt_tab()  
  
    def _on_key_command(self, event):  
        """Handle typing inside the bar"""  
        keysym = self.wm.d.keycode_to_keysym(event.detail, 0)  
          
        
        if keysym == XK.string_to_keysym("Escape"):  
            self.wm.toggle_cmd_bar()  
            return  
        elif keysym == XK.string_to_keysym("Return"):  
            self.wm.execute_command()  
            return  
        elif keysym == XK.string_to_keysym("BackSpace"):  
            self.wm.cmd_text = self.wm.cmd_text[:-1]  
            self.wm.draw_bar()  
            return  
          
        
        try:  
            
            key_str = XK.keysym_to_string(keysym)  
            if key_str:  
                
                if len(key_str) == 1:   
                    self.wm.cmd_text += key_str  
                
                elif key_str == "space": self.wm.cmd_text += " "  
                elif key_str == "period": self.wm.cmd_text += "."  
                elif key_str == "minus": self.wm.cmd_text += "-"  
                elif key_str == "underscore": self.wm.cmd_text += "_"  
                elif key_str == "slash": self.wm.cmd_text += "/"  
        except Exception as e:  
            print(f"Key Error: {e}")  
          
        self.wm.draw_bar()  
  
    def _on_click(self, event):  
        
        if event.state & X.Mod4Mask and event.detail in [4, 5]:  
            if self.wm.get_fullscreen_window(): return   
            self.wm.zoom_camera(1 if event.detail == 4 else -1)  
            return  
          
        
        if (event.state & X.Mod4Mask) and event.detail == 1:  
            fs_win = self.wm.get_fullscreen_window()  
            if fs_win:  
                self.wm.toggle_fullscreen(fs_win)  
                return  
            self.drag_mode = 'CAMERA'  
            self.drag_start_event = event  
            self.drag_start_cam = (self.wm.camera.x, self.wm.camera.y)  
            return  
          
        
        if event.window.id in self.wm.btn_map:  
            action, win_obj = self.wm.btn_map[event.window.id]  
            if action == 'close': self.wm.close_window(win_obj)  
            elif action == 'maximize': self.wm.toggle_fullscreen(win_obj)  
            return  
          
        
        win_obj = self.wm.get_window_by_frame(event.window.id)  
        if win_obj:  
            self.wm.focus_window(win_obj)  
            event.window.configure(stack_mode=X.Above)  
              
            
            try:  
                geom = event.window.get_geometry()  
                click_x = event.event_x  
                click_y = event.event_y  
                w = geom.width  
                h = geom.height  
                  
                
                
                
                
                
                resize_threshold = max(60, int(80 / self.wm.camera.zoom))  
                  
                
                is_corner = (click_x > w - resize_threshold) and (click_y > h - resize_threshold)  
                  
                if is_corner:  
                    self.drag_mode = 'RESIZE'  
                    print(f"🔧 Resize mode activated (threshold: {resize_threshold}px)")  
                else:  
                    self.drag_mode = 'WINDOW'  
                  
                self.drag_start_event = event  
                self.drag_start_frame = {  
                    'x': win_obj.world_x,   
                    'y': win_obj.world_y,  
                    'w': win_obj.world_w,  
                    'h': win_obj.world_h  
                }  
            except:  
                self.drag_mode = None  
            return  
          
        
        if event.window.id == self.wm.root.id:  
            print("Desktop clicked - unfocusing all")  
            self.wm.unfocus_all()  
            return  
          
        
        for win_obj in self.wm.windows.values():  
            if event.window.id == win_obj.client.id:  
                
                self.wm.focus_window(win_obj)  
                win_obj.frame.configure(stack_mode=X.Above)  
                  
                
                try:  
                    self.wm.d.allow_events(X.ReplayPointer, event.time)  
                    self.wm.d.sync()  
                    print(f"✓ Focused and replayed click to: {win_obj.title}")  
                except Exception as e:  
                    print(f"⚠ Replay failed: {e}")  
                return  
  
    def _on_motion(self, event):  
        if not self.drag_mode or not self.drag_start_event: return  
          
        xsdiff = event.root_x - self.drag_start_event.root_x  
        ysdiff = event.root_y - self.drag_start_event.root_y  
        safe_zoom = max(self.wm.camera.zoom, 0.1)  
        wxdiff = int(xsdiff / safe_zoom)  
        wydiff = int(ysdiff / safe_zoom)  
          
        if self.drag_mode == 'CAMERA':  
            self.wm.camera.x = self.drag_start_cam[0] - wxdiff  
            self.wm.camera.y = self.drag_start_cam[1] - wydiff  
            self.wm.renderer.render_world(self.wm.camera, self.wm.windows)  
            self.wm.ensure_polybar_stacking()  
        elif self.drag_mode == 'WINDOW':  
            win_obj = self.wm.get_window_by_frame(self.drag_start_event.window.id)  
            if win_obj:  
                win_obj.world_x = self.drag_start_frame['x'] + wxdiff  
                win_obj.world_y = self.drag_start_frame['y'] + wydiff  
                self.wm.renderer.render_world(self.wm.camera, self.wm.windows)  
                self.wm.ensure_polybar_stacking()  
        elif self.drag_mode == 'RESIZE':  
            win_obj = self.wm.get_window_by_frame(self.drag_start_event.window.id)  
            if win_obj:  
                new_w = self.drag_start_frame['w'] + wxdiff  
                new_h = self.drag_start_frame['h'] + wydiff  
                if new_w < 50: new_w = 50  
                if new_h < 50: new_h = 50  
                win_obj.world_w = new_w  
                win_obj.world_h = new_h  
                self.wm.renderer.render_world(self.wm.camera, self.wm.windows)  
                self.wm.ensure_polybar_stacking()  
  
    def _on_release(self, event):  
        self.drag_mode = None  
