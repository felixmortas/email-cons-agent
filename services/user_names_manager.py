"""
User Names Manager

A utility for managing a persistent list of user identifiers (names, initials, or nicknames) 
stored in a local JSON configuration file.
"""

import json
import os

class UserNamesManager:
    def __init__(self, prefs_file=".prefs.json"):
        self.prefs_file = prefs_file
        self.user_names = self._load_prefs()

    def _load_prefs(self):
        """Load user names from prefs file, preserving index list."""
        if os.path.exists(self.prefs_file):
            try:
                with open(self.prefs_file, "r") as f:
                    prefs = json.load(f)
                    return prefs.get("user_names", [])
            except Exception:
                return []
        return []

    def _save_prefs(self):
        """Save user names to prefs file, preserving index list."""
        existing_prefs = {}
        if os.path.exists(self.prefs_file):
            try:
                with open(self.prefs_file, "r") as f:
                    existing_prefs = json.load(f)
            except Exception:
                pass
        existing_prefs["user_names"] = self.user_names
        with open(self.prefs_file, "w") as f:
            json.dump(existing_prefs, f)

    def add_name(self, name):
        """Add a name to the list and save."""
        if name not in self.user_names:
            self.user_names.append(name)
            self._save_prefs()
            print(f"Added: {name}")
        else:
            print(f"'{name}' is already in the list.")

    def remove_name(self, name):
        """Remove a name from the list and save."""
        if name in self.user_names:
            self.user_names.remove(name)
            self._save_prefs()
            print(f"Removed: {name}")
        else:
            print(f"'{name}' not found in the list.")

    def list_names(self):
        """List all names."""
        if not self.user_names:
            print("No names, first names, initials, or nicknames added yet.")
        else:
            print("Current list:")
            for name in self.user_names:
                print(f"- {name}")

    def prompt_user_for_names(self):
        """Prompt the user to add or remove names interactively."""
        self.list_names()
        print("Enter names, first names, initials, or nicknames one by one.")
        print("Type '/remove <name>' to remove a name. Press Enter on an empty line to finish.")

        while True:
            user_input = input("> ").strip()
            if not user_input:
                break  # Empty input: finish
            elif user_input.startswith("/remove "):
                name_to_remove = user_input[8:].strip()
                self.remove_name(name_to_remove)
            else:
                self.add_name(user_input)

        print("Final list:")
        self.list_names()
    
    def get_user_names(self):
        """Return the current list of names."""
        return self.user_names.copy()

def get_user_names():
    manager = UserNamesManager()
    manager.prompt_user_for_names()

    return manager.get_user_names()

# Example usage
if __name__ == "__main__":
    names = get_user_names()
    print(names)
