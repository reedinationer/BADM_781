from sel_methods import BSG_Selenium
from pynput import keyboard
import pandas as pd
import xlwings
import numpy as np
from threading import Thread
from multiprocessing import Process, JoinableQueue
import tkinter as tk
import time

GLOBAL_QUEUE = JoinableQueue()

def listen_for_input(queue_obj):
	print('keyboard listener is initialized')
	with keyboard.Listener(on_press=lambda x: pynput_button_press(x, queue_obj)) as listener:
		listener.join()

def pynput_button_press(key, queue_obj):
	if key == keyboard.Key.f1:
		print("Putting an F1 into the queue")
		queue_obj.put("F1")


class OOP:
	def __init__(self):
		self.win = tk.Tk()
		# self.bsg = BSG_Selenium()
		height = self.win.winfo_screenheight()
		width = self.win.winfo_screenwidth()
		self.win.geometry("%dx%d+0+0" % (width, height))
		# self.win.resizable(False, False)
		self.win.title("BADM 781 automation")
		self.create_widgets()
		self.wb = xlwings.books["Book1"]
		self.t = Thread(target=self.listen_for_pynput)
		self.t.start()

	def click_me(self):
		print("clicked")

	def create_widgets(self):
		tk.Label(self.win, text="My GUI").pack(expand=1, fill='both')
		tk.Button(self.win, text="Click ME", command=self.click_me).pack(expand=1, fill='both')

	def listen_for_pynput(self):
		print("Listening for items on the QUEUE")
		while True:
			if GLOBAL_QUEUE.empty() is False:
				# print("Processing item in the QUEUE")
				item = GLOBAL_QUEUE.get()
				if item == "F1":
					print("Running sweep")
					output = self.bsg.run_sweep()
					df = pd.DataFrame(output)
					self.wb.sheets["A1"].value = pd.DataFrame(np.array(df.values.tolist())[:, :, 0], df.index, df.columns)  # Write only the first item of each tuple into the spreadsheet
				GLOBAL_QUEUE.task_done()
			time.sleep(.5)  # Wait half a second, so we don't run this ALL the time

	def on_press(self, key):
		if key == keyboard.Key.f1:
			print("Running sweep")
			output = self.bsg.run_sweep()
			df = pd.DataFrame(output)
			self.wb.sheets["A1"].value = pd.DataFrame(np.array(df.values.tolist())[:, :, 0], df.index, df.columns)  # Write only the first item of each tuple into the spreadsheet


if __name__ == "__main__":
	p = Process(target=listen_for_input, args=(GLOBAL_QUEUE, ))
	p.daemon = True
	p.start()
	gui = OOP()
	gui.win.mainloop()
	# print("Running sweep")
	# output = self.bsg.run_sweep()
	# df = pd.DataFrame(output)
	# self.wb.sheets["A1"].value = pd.DataFrame(np.array(df.values.tolist())[:, :, 0], df.index,
	# 										  df.columns)  # Write only the first item of each tuple into the spreadsheet

