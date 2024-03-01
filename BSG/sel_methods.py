import multiprocessing
import time
import numpy
import selenium.common.exceptions
import selenium.webdriver as webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import numpy as np
from Utility import format_to_number
from pynput import keyboard
from collections import defaultdict

shared_list = multiprocessing.JoinableQueue()

def listener_process(some_list: multiprocessing.JoinableQueue):
	print("Press COMMAND + CONTRL + SHIFT to select an element")
	def process_hotkey():
		print("Hotkey pressed. Adding value to the list")
		some_list.put(True)
	with keyboard.GlobalHotKeys({'<cmd>+<ctrl>+<shift>': process_hotkey}) as h:
		h.join()

def get_with_wait(browser, xpath):
	return WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.XPATH, xpath)))


class BSG_Selenium:
	def __init__(self):
		self.driver = webdriver.Chrome()
		self.login_to_game()
		self.metrics = ["Earnings Per Share", "Return On Equity", "Credit Rating", "Image Rating", "Net Revenues ", "Net Profit ", "Ending Cash "]
		self.sweep_elems = []
		self.p = self.start_listener()

	@staticmethod
	def start_listener():
		p = multiprocessing.Process(target=listener_process, args=(shared_list,))
		p.daemon = True
		p.start()
		return p

	def login_to_game(self):
		self.driver.get("https://www.bsg-online.com/")
		get_with_wait(self.driver, "//div/input[@id='acct_name']").send_keys("rparkhurst@nevada.unr.edu")
		get_with_wait(self.driver, "//div/input[@id='passwdInput']").send_keys("Gkd6VybX.EL!SK4")
		get_with_wait(self.driver, "//div/button[@id='loginbutton']").click()

	def get_metric(self, metric_text):
		if metric_text not in self.metrics:
			print("Metric was spelled incorrectly")
			return None
		elems = self.driver.find_element(By.XPATH, f"//div/table/tbody/tr/td[text()='{metric_text}']").find_elements(By.XPATH, "../td")
		return format_to_number(elems[1].text), format_to_number(elems[2].text) # [1] is current amount, [2] is investor expectations

	def get_expectations(self):
		avgs = {}
		for met in self.metrics:
			temp = self.get_metric(met)
			avgs[met] = temp[1]
		return avgs

	def change_selection(self, elem, value):
		if isinstance(value, str):
			selection_obj = Select(elem)
			selection_obj.select_by_visible_text(value)
		else:
			elem.clear()
			elem.send_keys("0")
			elem.send_keys(Keys.ENTER)
			elem.clear()
			elem.send_keys(f"{value:.2f}")
			elem.send_keys(Keys.ENTER)
			time.sleep(.1)

	def _run_sweep(self):
		# Figure out what the inputs we will sweep across are
		inputs = []
		for ind, elem in enumerate(self.sweep_elems):
			try:
				selection_obj = Select(elem)
				inputs.append([x.text for x in selection_obj.options])
			except selenium.common.exceptions.UnexpectedTagNameException:  # There aren't specific options for input, this is a free response
				lower_bound = int(input("What is the lowest number to try?"))
				upper_bound = int(input("What is the largest number to try?"))
				inputs.append(np.linspace(lower_bound, upper_bound, 50))

		results = defaultdict(dict)
		results["Expectations"] = self.get_expectations()  # Store expectations before running the sweep
		def add_to_results(input1, value, input2=None):
			if input2 is None:
				if isinstance(input1, float):
					results[input1] = value
				else:
					results[format_to_number(input1)] = value
			else:
				if isinstance(input1, float):
					if isinstance(input2, float):
						results[input1][input2] = value
					else:
						results[input1][format_to_number(input2)] = value
				else:
					if isinstance(input2, float):
						results[format_to_number(input1)][input2] = value
					else:
						results[format_to_number(input1)][format_to_number(input2)] = value

		if len(self.sweep_elems) == 1:
			for x in inputs[0]:
				self.change_selection(self.sweep_elems[0], x)
				add_to_results(x, {met: self.get_metric(met)[0] for met in self.metrics})
		elif len(self.sweep_elems) == 2:
			for x1 in inputs[0][::3]: # Loop over first array
				self.change_selection(self.sweep_elems[0], x1) # Change the first value
				for x2 in inputs[1][::3]:
					self.change_selection(self.sweep_elems[1], x2) # Change second value
					# Now record the adjustment
					add_to_results(x1, {met: self.get_metric(met)[0] for met in self.metrics}, x2)
		return results

	def run_sweep(self, number_of_variables):
		self.sweep_elems = [] # Reset the array to fill again

		while len(self.sweep_elems) < number_of_variables:
			if shared_list.empty() is False:
				val = shared_list.get()
				print(f"Received value: {val}")
				if val is True:
					self.driver.switch_to.window(self.driver.window_handles[-1])
					self.sweep_elems.append(self.driver.switch_to.active_element)
				shared_list.task_done()
			time.sleep(1)

		return self._run_sweep()

	# def run_double_sweep(self):
	# 	results = dict()
	# 	self.driver.switch_to.window(self.driver.window_handles[-1])  # Swap to using the last tab in the browser
	# 	self.elem_selected = self.driver.switch_to.active_element
	# 	results["Expectations"] = self.get_expectations()  # Store expectations before running the sweep
	# 	try:
	# 		selection_obj = Select(self.elem_selected)
	# 		for ind in range(len(selection_obj.options)):
	# 			this_result = {}
	# 			# print(f"Testing option: {selection_obj.options[ind].text}")
	# 			selection_obj.select_by_index(ind)
	# 			this_result = {met: self.get_metric(met)[0] for met in self.metrics}
	# 			results[format_to_number(selection_obj.options[ind].text)] = this_result
	# 	except selenium.common.exceptions.UnexpectedTagNameException:  # There aren't specific options for input, this is a free response
	# 		lower_bound = int(input("What is the lowest number to try?"))
	# 		upper_bound = int(input("What is the largest number to try?"))
	# 		try_inputs = np.linspace(lower_bound, upper_bound, 50)
	# 		while self.elem_selected.tag_name == "body":
	# 			print("No active element identified")
	# 			time.sleep(1)
	# 			self.elem_selected = self.driver.switch_to.active_element
	# 		for trial in try_inputs:
	# 			self.elem_selected.clear()
	# 			self.elem_selected.send_keys("0")
	# 			self.elem_selected.send_keys(Keys.ENTER)
	# 			self.elem_selected.clear()
	# 			self.elem_selected.send_keys(f"{trial:.2f}")
	# 			self.elem_selected.send_keys(Keys.ENTER)
	# 			time.sleep(.2)
	# 			this_result = {met: self.get_metric(met)[0] for met in self.metrics}
	# 			# for met in self.metrics:
	# 			# 	# print(f"{met}: {self.get_metric(met)}")
	# 			# 	this_result[met] = self.get_metric(met)[0]
	# 			results[trial] = this_result
	# 	finally:
	# 		return results

	def get_page_specific_results(self):
		"""This is called by run_sweep, and will add different result keys depending on the page being viewed"""
		if self.driver.current_url.endswith("comp-training"):
			pass
		elif self.driver.current_url.endswith("branded-production"):
			pass



