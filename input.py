from Xlib import X, XK

class InputHandler:
    def __init__(self, wm):
        self.wm = wm 
        self.drag_mode = None 
        self.drag_start_event = None

    def handle_event(self, event):
        # --- NEW: Handle Typing in Command Mode ---
        if event.type == X.KeyPress and self.wm.cmd_active:
            self._on_key_command(event)
            return

        # --- Handle Normal Shortcuts ---
        if event.type == X.KeyPress:
            self._on_key_normal(event)
        
        elif event.type == X.ButtonPress:
            self._on_click(event)
        elif event.type == X.MotionNotify:
            self._on_motion(event)
        elif event.type == X.ButtonRelease:
            self._on_release(event)
        
        # --- NEW: Redraw bar if it was covered/exposed ---
        elif event.type == X.Expose and event.window.id == self.wm.cmd_window.id:
             self.wm.draw_bar()
             
    def _on_key_normal(self, event):
        keysym = self.wm.d.keycode_to_keysym(event.detail, 0)
        
        # Win + Space -> Toggle Bar
        if (event.state & X.Mod4Mask) and keysym == XK.string_to_keysym("space"):
            self.wm.toggle_cmd_bar()
            return

        # --- RTS CAMERA CONTROLS (F1 - F4) ---
        # Map F-keys to indexes 1-4
        f_map = {
            XK.XK_F1: 1,
            XK.XK_F2: 2,
            XK.XK_F3: 3,
            XK.XK_F4: 4
        }

        if keysym in f_map:
            index = f_map[keysym]
            
            # Check Modifiers
            # X.ControlMask = Ctrl
            # X.Mod4Mask = Windows Key
            
            # CASE 1: Win + Ctrl + Fx -> SAVE
            if (event.state & X.Mod4Mask) and (event.state & X.ControlMask):
                self.wm.save_camera_pos(index)
                
            # CASE 2: Win + Fx -> LOAD
            elif (event.state & X.Mod4Mask):
                self.wm.load_camera_pos(index)

    def _on_key_command(self, event):
        """Handle typing inside the bar"""
        keysym = self.wm.d.keycode_to_keysym(event.detail, 0)
        
        # 1. Escape -> Close
        if keysym == XK.string_to_keysym("Escape"):
            self.wm.toggle_cmd_bar()
            return

        # 2. Return -> Execute
        if keysym == XK.string_to_keysym("Return"):
            self.wm.execute_command()
            return
            
        # 3. Backspace -> Delete char
        if keysym == XK.string_to_keysym("BackSpace"):
            self.wm.cmd_text = self.wm.cmd_text[:-1]
        
        # 4. Normal Characters (a-z, 0-9, etc)
        else:
            # We try to convert keycode to a char
            # This is a naive implementation (doesn't handle Shift perfectly for symbols)
            # But it works for basic launch commands
            try:
                # Xlib lookup_string is complex, naive chr() mapping often fails for raw keycodes
                # Simplest way for prototype: lookup string name
                key_str = XK.keysym_to_string(keysym)
                if key_str and len(key_str) == 1:
                    self.wm.cmd_text += key_str
                elif key_str == "space":
                     self.wm.cmd_text += " "
                elif key_str == "period":
                     self.wm.cmd_text += "."
                elif key_str == "minus":
                     self.wm.cmd_text += "-"
            except:
                pass

        self.wm.draw_bar()

    def _on_click(self, event):
        # 1. SCROLL (Zoom)
        if event.detail in [4, 5]:
            self.wm.zoom_camera(1 if event.detail == 4 else -1)
            return

        # 2. PAN (Win + Left Click)
        if (event.state & X.Mod4Mask) and event.detail == 1:
            self.drag_mode = 'CAMERA'
            self.drag_start_event = event
            self.drag_start_cam = (self.wm.camera.x, self.wm.camera.y)
            return

        # 3. UI Buttons
        if event.window.id in self.wm.btn_map:
            action, win_obj = self.wm.btn_map[event.window.id]
            if action == 'close': self.wm.close_window(win_obj)
            elif action == 'maximize': self.wm.toggle_fullscreen(win_obj)
            return

        # 4. Window Drag
        # Find which window we clicked (by checking frames)
        # In a real app we'd map frame_id -> window object directly
        win_obj = self.wm.get_window_by_frame(event.window.id)
        if win_obj:
            self.drag_mode = 'WINDOW'
            self.drag_start_event = event
            self.drag_start_frame = {'x': win_obj.world_x, 'y': win_obj.world_y}
            event.window.configure(stack_mode=X.Above)

    def _on_motion(self, event):
        if not self.drag_mode or not self.drag_start_event: return

        # Calc Screen Delta
        xsdiff = event.root_x - self.drag_start_event.root_x
        ysdiff = event.root_y - self.drag_start_event.root_y
        
        # Calc World Delta
        safe_zoom = max(self.wm.camera.zoom, 0.1)
        wxdiff = int(xsdiff / safe_zoom)
        wydiff = int(ysdiff / safe_zoom)

        if self.drag_mode == 'CAMERA':
            self.wm.camera.x = self.drag_start_cam[0] - wxdiff
            self.wm.camera.y = self.drag_start_cam[1] - wydiff
            self.wm.renderer.render_world(self.wm.camera, self.wm.windows)

        elif self.drag_mode == 'WINDOW':
            win_obj = self.wm.get_window_by_frame(self.drag_start_event.window.id)
            if win_obj:
                win_obj.world_x = self.drag_start_frame['x'] + wxdiff
                win_obj.world_y = self.drag_start_frame['y'] + wydiff
                self.wm.renderer.render_world(self.wm.camera, self.wm.windows)

    def _on_release(self, event):
        self.drag_mode = None
        # Clean up artifacts
        win_obj = self.wm.get_window_by_frame(event.window.id)
        if win_obj: win_obj.frame.clear_area()