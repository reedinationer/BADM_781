from sel_methods import BSG_Selenium
from pynput import keyboard
import pandas as pd
import numpy as np
from threading import Thread
from multiprocessing import Process, JoinableQueue
import tkinter as tk
import time

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

GLOBAL_QUEUE = JoinableQueue()

def listen_for_input(queue_obj):
	print('keyboard listener is initialized')
	with keyboard.Listener(on_press=lambda x: pynput_button_press(x, queue_obj)) as listener:
		listener.join()

def pynput_button_press(key, queue_obj):
	if key == keyboard.Key.f1:
		print("Putting an F1 into the queue")
		queue_obj.put("F1")


class GraphFrame(tk.Frame):
	def __init__(self, parent, *args, **kwargs):
		tk.Frame.__init__(self, parent, *args, **kwargs)
		self.parent = parent
		self.fig = Figure(facecolor="white", dpi=100, figsize=(10, 10))
		self.axis = self.fig.add_subplot(111)
		self.fig.set_tight_layout(True)
		self.canvas = FigureCanvasTkAgg(self.fig, master=self)
		self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
		self.canvas.get_tk_widget().rowconfigure(0, weight=1)
		self.canvas.get_tk_widget().columnconfigure(0, weight=1)

	def clear_graph(self):
		self.axis.clear()
		self.canvas.draw_idle()

	def scatter_data(self, x_data, y_data, x_label=None, y_label=None):
		if x_label:
			self.axis.set_xlabel(x_label)
		if y_label:
			self.axis.set_ylabel(y_label)
		self.axis.scatter(x_data, y_data)
		self.canvas.draw_idle()


class InputFrame(tk.Frame):
	def __init__(self, parent, *args, **kwargs):
		tk.Frame.__init__(self, parent, *args, **kwargs)
		self.parent = parent
		# self.calculator = calc_obj
		# self.fields = calc_obj.df["1"].columns
		# self.graph = graph_frame
		self.labels = []  # Hold labels so they are not garbage collected
		self.x_vars = {}
		self.y_vars = {}
		self.current_row_names = [
			"Sweep",
			"Earnings Per Share",
			"Return On Equity",
			"Credit Rating",
			"Image Rating",
			"Net Revenues ",
			"Net Profit ",
			"Ending Cash "
		]
		self.build_selectors(self.current_row_names)

	def build_selectors(self, list_of_variable_names):
		print("Building input checkbox area")
		for child in self.winfo_children():
			child.destroy()  # Reset the window when we are updating variable names
		self.x_vars = {}
		self.y_vars = {}
		self.labels = []
		for row_number, field in enumerate(list_of_variable_names):
			tk.Label(self, text=field).grid(row=row_number, column=1, sticky='news')
			x_var = tk.BooleanVar()
			self.x_vars[field] = x_var
			tk.Checkbutton(self, variable=x_var, command=self.run_calculation).grid(row=row_number, column=2)
			y_var = tk.BooleanVar()
			self.y_vars[field] = y_var
			tk.Checkbutton(self, variable=y_var, command=self.run_calculation).grid(row=row_number, column=3)
		self.current_row_names = list_of_variable_names

	def run_calculation(self):
		used_x_vars = dict(filter(lambda elem: elem[1].get() is True, self.x_vars.items()))  # Filter variables to only have user selections into a new dictionary
		used_y_vars = dict(filter(lambda elem: elem[1].get() is True, self.y_vars.items()))
		if len(used_x_vars) == 1 and len(used_y_vars) == 1:
			if len(used_y_vars) == 1:
				# self.graph.clear_graph()
				x_var = list(used_x_vars.keys())[0]
				y_var = list(used_y_vars.keys())[0]
				# print(f"Loading the QUEUE with ({x_var}, {y_var})")
				GLOBAL_QUEUE.put((x_var, y_var))
			elif len(used_y_vars) == 2:
				print("Double y variables detected")


class OOP:
	def __init__(self):
		self.win = tk.Tk()
		self.bsg = BSG_Selenium()
		height = self.win.winfo_screenheight()
		width = self.win.winfo_screenwidth()
		self.win.geometry("%dx%d+0+0" % (width, height))
		# self.win.resizable(False, False)
		self.win.title("BADM 781 automation")

		self.graph = GraphFrame(self.win)
		self.graph.grid(row=0, column=1)
		self.currently_plotted = None
		self.input_region = InputFrame(self.win)
		self.input_region.grid(row=0, column=0)
		self.win.columnconfigure(1, weight=1)
		self.win.rowconfigure(0, weight=1)

		# self.wb = xlwings.books["Book1"]
		self.df = None
		self.t = Thread(target=self.listen_for_pynput)
		self.t.start()

	def listen_for_pynput(self):
		print("Listening for items on the QUEUE")
		while True:
			if GLOBAL_QUEUE.empty() is False:
				# print("Processing item in the QUEUE")
				item = GLOBAL_QUEUE.get()
				if item == "F1":
					print("Running sweep")
					output = self.bsg.run_sweep()
					self.df = pd.DataFrame(output)
					# self.wb.sheets["A1"].value = pd.DataFrame(np.array(df.values.tolist())[:, :, 0], df.index, df.columns)  # Write only the first item of each tuple into the spreadsheet
					names_expected = ["Sweep", *self.df.index.tolist()]
					if names_expected != self.input_region.current_row_names:
						self.input_region.build_selectors(names_expected)
				elif type(item) is tuple:
					try:
						# print(f"Receiving tuple from the QUEUE: {item}")
						self.currently_plotted = item
						x_var, y_var = item  # unpack tuple
						if self.df is not None:
							print(f"Graphing {x_var} vs {y_var}")
							self.graph.clear_graph()
							plot_df = self.df.drop("Expectations", axis=1)
							if x_var in plot_df.index and y_var in plot_df.index:
								# In these cases we know that we need to use data from two of the rows
								print(plot_df.loc[x_var])
								print(plot_df.loc[y_var])
								self.graph.axis.scatter(plot_df.loc[x_var], plot_df.loc[y_var], label=f"{x_var} vs {y_var}")
							elif x_var == "Sweep":
								print(plot_df.loc[y_var])
								self.graph.axis.scatter(plot_df.columns, plot_df.loc[y_var], label=y_var)
								self.graph.axis.plot(plot_df.columns, plot_df.loc[y_var])  # Plot a line so we can see trends
								self.graph.axis.plot([min(plot_df.columns), max(plot_df.columns)], [self.df.loc[y_var]["Expectations"], self.df.loc[y_var]["Expectations"]], label=f"{y_var} Expectations")
							## Apply general formatting regardless of what method was used to plot
							self.graph.axis.legend()
							self.graph.axis.set_xlabel(x_var)
							self.graph.axis.set_ylabel(y_var)
							self.graph.axis.grid(which='major', alpha=0.85)
							self.graph.axis.grid(which="minor", alpha=0.3)
						else:
							print("self.df is empty. Unable to graph")
					except Exception as e:
						print("Exception encountered while graphing")
						print(e.args)

				# self.graph.axis.set_xticks(np.linspace(min_x, max_x, 20))
				# self.graph.axis.set_yticks(np.linspace(min_y, max_y, 20))
				else:
					print(f"Receiving unexpected item from the QUEUE: {item}")
				GLOBAL_QUEUE.task_done()
			time.sleep(.5)  # Wait half a second, so we don't run this ALL the time
			self.graph.canvas.draw_idle()

	def on_press(self, key):
		"""If the user presses F1, we will run a sweep on their focused element and update our dataframe we are plotting"""
		if key == keyboard.Key.f1:
			print("Running sweep")
			output = self.bsg.run_sweep()
			self.df = pd.DataFrame(output)
			GLOBAL_QUEUE.put(self.currently_plotted)
			# self.wb.sheets["A1"].value = pd.DataFrame(np.array(df.values.tolist())[:, :, 0], df.index, df.columns)  # Write only the first item of each tuple into the spreadsheet


if __name__ == "__main__":
	p = Process(target=listen_for_input, args=(GLOBAL_QUEUE, ))
	p.daemon = True
	p.start()
	gui = OOP()
	gui.win.mainloop()

