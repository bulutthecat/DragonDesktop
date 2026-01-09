class Camera:  
    def __init__(self):  
        self.x = 0  
        self.y = 0  
        self.zoom = 1.0  
        # Store saved locations: key (e.g., 1) -> (x, y, zoom)  
        self.saved_spots = {}  
  
  
class ZWindow:  
    def __init__(self, client_id, client_window, frame_window, close_btn, full_btn, x, y, w, h, title=""):  
        # FIX #1: Use client window ID as primary identifier  
        self.id = client_id  # This is now client.id, not frame.id  
        self.client = client_window  
        self.frame = frame_window  
        self.title = title  
          
        # Decorations  
        self.btn_close = close_btn  
        self.btn_full = full_btn  
          
        # World coordinates (for 3D WM positioning)  
        self.world_x = x  
        self.world_y = y  
        self.world_w = w  
        self.world_h = h  
          
        # Size constraints  
        self.min_w = 0  
        self.min_h = 0  
        self.max_w = 32768  
        self.max_h = 32768  
          
        # --- State Tracking (CRITICAL for X11 protocol compliance) ---  
        self.is_fullscreen = False  
        self.saved_geometry = None  # (x, y, w, h) before fullscreen  
          
        # FIX #7: Track map state to prevent rendering unmapped windows  
        self.mapped = False  # Is the window currently mapped?  
          
        # FIX #3: Dialog/Transient window support  
        self.is_dialog = False  # Is this a transient/dialog window?  
        self.transient_for = None  # Parent window if this is a dialog  
