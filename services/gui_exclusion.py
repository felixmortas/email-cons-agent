import tkinter as tk
from tkinter import ttk
import json
import os
from multiprocessing import Process, Queue

class SiteSelector:
    def __init__(self, full_data, email_cible, prefs_file=".exclusions_prefs.json"):
        self.full_data = full_data
        self.email_cible = email_cible
        self.prefs_file = prefs_file
        
        # Filtering
        self.sites_a_afficher = [
            (i, item.get('name', 'Sans nom'))
            for i, item in enumerate(self.full_data.get('items', []))
            if item.get('login', {}).get('username') == self.email_cible
        ]
        
    def _load_prefs(self):
        if os.path.exists(self.prefs_file):
            try:
                with open(self.prefs_file, "r") as f:
                    return json.load(f)
            except: return []
        return []

    def _save_prefs(self, exclusions):
        with open(self.prefs_file, "w") as f:
            json.dump(exclusions, f)

    def run_ui(self, queue):
        """This method runs in a separate process   ."""
        root = tk.Tk()
        root.title("Sélection des sites")
        root.geometry("500x600")
        
        # Forced Focus for macOS
        root.lift()
        root.attributes('-topmost', True)

        saved_exclusions = self._load_prefs()
        vars_dict = {}

        # UI Construction
        container = ttk.Frame(root)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for original_index, name in self.sites_a_afficher:
            var = tk.BooleanVar(value=original_index not in saved_exclusions)
            vars_dict[original_index] = var
            ttk.Checkbutton(scrollable_frame, text=name, variable=var).pack(anchor="w")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_validate():
            exclusions = [idx for idx, v in vars_dict.items() if not v.get()]
            self._save_prefs(exclusions)
            queue.put(exclusions) # The data is returned to the main process
            root.quit()
            root.destroy()

        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_frame, text="Valider", command=on_validate).pack(side="right")

        root.mainloop()

def selectionner_sites_gui(full_data, email_cible):
    """Launches the UI in a separate process and waits for it to finish."""
    queue = Queue()
    selector = SiteSelector(full_data, email_cible)
    
    # We create a process dedicated to Tkinter
    p = Process(target=selector.run_ui, args=(queue,))
    p.start()
    
    # We are waiting for the user to confirm (blocking)
    exclusions = queue.get() 
    
    # We make sure the process is fully completed
    p.join()
    p.close()
    
    return exclusions