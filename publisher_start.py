"""Start the original publisher with its last selected local channel preset."""
import argparse
import tkinter as tk
from desktop import App
from publisher_profiles import initial_profile

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config')
    args=parser.parse_args()
    window=tk.Tk();App(window,args.config or initial_profile());window.mainloop()
