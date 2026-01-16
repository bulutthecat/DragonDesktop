
"""  
DragonDesktop Settings Menu  
A simple GUI for changing wallpaper and other settings.  
"""  
  
import tkinter as tk  
from tkinter import filedialog, messagebox  
import json  
import os  
  
class SettingsMenu:  
    def __init__(self):  
        self.root = tk.Tk()  
        self.root.title("Desktop Settings")  
        self.root.geometry("400x300")  
        self.config_path = "config.json"  
        self.config = self.load_config()  
          
        self.setup_ui()  
      
    def load_config(self):  
        try:  
            if os.path.exists(self.config_path):  
                with open(self.config_path, "r") as f:  
                    return json.load(f)  
        except Exception as e:  
            print(f"Config load error: {e}")  
        return {"wallpaper_path": "", "aliases": {}}  
      
    def save_config(self):  
        try:  
            with open(self.config_path, "w") as f:  
                json.dump(self.config, f, indent=4)  
            return True  
        except Exception as e:  
            print(f"Config save error: {e}")  
            return False  
      
    def setup_ui(self):  
        
        title = tk.Label(self.root, text="DragonDesktop Settings",   
                        font=("Arial", 16, "bold"), pady=10)  
        title.pack()  
          
        
        wallpaper_frame = tk.LabelFrame(self.root, text="Wallpaper",   
                                       padx=10, pady=10)  
        wallpaper_frame.pack(fill="both", expand=True, padx=10, pady=10)
          
        current_wp = self.config.get("wallpaper_path", "None")  
        self.wp_label = tk.Label(wallpaper_frame,   
                                 text=f"Current: {os.path.basename(current_wp) if current_wp else 'None'}",   
                                 wraplength=350)  
        self.wp_label.pack(pady=5)  
          
        btn_choose = tk.Button(wallpaper_frame, text="Choose Wallpaper",   
                              command=self.choose_wallpaper)  
        btn_choose.pack(pady=5)  
          
        btn_clear = tk.Button(wallpaper_frame, text="Clear Wallpaper",   
                             command=self.clear_wallpaper)  
        btn_clear.pack(pady=5)  
          
        
        info_frame = tk.Frame(self.root)  
        info_frame.pack(pady=10)  
          
        info_text = "⚠️ Restart Desktop to apply changes"  
        info_label = tk.Label(info_frame, text=info_text,   
                             fg="orange", font=("Arial", 10))  
        info_label.pack()  
      
    def choose_wallpaper(self):  
        filename = filedialog.askopenfilename(  
            title="Select Wallpaper",  
            filetypes=[  
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"),  
                ("All files", "*.*")  
            ]  
        )  
          
        if filename:  
            self.config["wallpaper_path"] = filename  
            if self.save_config():  
                self.wp_label.config(text=f"Current: {os.path.basename(filename)}")  
                messagebox.showinfo("Success",   
                                   "Wallpaper set!\nRestart DragonDesktop to see changes.")  
            else:  
                messagebox.showerror("Error", "Failed to save configuration.")  
      
    def clear_wallpaper(self):  
        self.config["wallpaper_path"] = ""  
        if self.save_config():  
            self.wp_label.config(text="Current: None")  
            messagebox.showinfo("Success",   
                               "Wallpaper cleared!\nRestart DragonDesktop to see changes.")  
        else:  
            messagebox.showerror("Error", "Failed to save configuration.")  
      
    def run(self):  
        self.root.mainloop()  
  
if __name__ == "__main__":  
    app = SettingsMenu()  
    app.run()  
