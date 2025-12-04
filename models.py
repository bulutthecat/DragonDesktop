class Camera:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.zoom = 1.0
        # Store saved locations: key (e.g., 1) -> (x, y, zoom)
        self.saved_spots = {}
        
class ZWindow:
    def __init__(self, frame_id, client_window, frame_window, close_btn, full_btn, x, y, w, h, title=""):
        self.id = frame_id
        self.client = client_window
        self.frame = frame_window
        
        # --- NEW: Store Title ---
        self.title = title
        
        # Buttons
        self.btn_close = close_btn
        self.btn_full = full_btn
        
        # World Geometry
        self.world_x = x
        self.world_y = y
        self.world_w = w
        self.world_h = h
        
        self.saved_geometry = None