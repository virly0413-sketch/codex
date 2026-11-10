"""Single entry point that stays open even before a channel has materials."""
import tkinter as tk
from desktop import App
from publisher_profiles import initial_profile
import run


if __name__ == '__main__':
    previous = initial_profile()
    path = previous if previous != run.ROOT / 'config.json' else run.ROOT / 'profiles' / 'english.json'
    window = tk.Tk()
    App(window, path)
    window.mainloop()
