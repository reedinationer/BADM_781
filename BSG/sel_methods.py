import multiprocessing
import time
import numpy
import pandas as pd
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

	def optimize_production(self):
		self.driver.switch_to.window(self.driver.window_handles[-1])
		if self.driver.current_url.endswith("branded-production"):
			sup_label = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td[text()='Superior Materials %']")
			material_selections = sup_label.find_elements(By.XPATH, "../td/div/glo-entry-select/select")
			styling = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/span[text()='Enhanced Styling / Features ']")
			styling_selections = styling.find_elements(By.XPATH, "../../td/div/glo-entry-select/select")
			tqm = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/span[text()='TQM / 6-Sigma Quality Program ']")
			tqm_selections = tqm.find_elements(By.XPATH, "../../td/div/glo-entry-select/select")

			sq_rating_span = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/strong[text()='Projected S/Q Rating ']")
			sq_ratings = sq_rating_span.find_elements(By.XPATH, "../../td[contains(@class, 'ng-star-inserted')]/strong")
			cost_row = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/strong[text()='Total Branded Production Cost']")
			production_costs = cost_row.find_elements(By.XPATH, "../../td/div/span/strong[contains(text(), '.')]")
			reject_cost_row = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/span[text()='Cost of Rejected Pairs']")
			reject_costs = reject_cost_row.find_elements(By.XPATH, "../../td/div/span[contains(text(), '.')]")
			assert len(material_selections) == len(styling_selections) == len(tqm_selections)
			region = int(input("What index should be used for the region"))
			region_data = []
			print(f"Optimizing region {region}")
			material = Select(material_selections[region])
			style = Select(styling_selections[region])
			quality = Select(tqm_selections[region])
			for m_s in material.options[25::2]:
				material.select_by_visible_text(m_s.text)
				for s_s in style.options[15::2]:
					style.select_by_visible_text(s_s.text)
					for q_s in quality.options[21::2]:
						quality.select_by_visible_text(q_s.text)
						this_result = {
							"Quality": float(q_s.text),
							"Style": int(s_s.text),
							"Material": int(m_s.text),
							"SQ": float(sq_ratings[region].text.replace("★", "")),
							"Production Cost": float(production_costs[region].text),
							"Reject Cost": float(reject_costs[region].text.replace("$", ""))
						}
						for k, v in {met: self.get_metric(met)[0] for met in self.metrics}.items():
							this_result[k] = v
						region_data.append(this_result)
			df = pd.DataFrame(region_data)
			region_headers = {
				0: "NorthAmerica",
				1: "Europe",
				2: "Asia",
				3: "LatinAmerica"
			}
			df["Total Cost"] = df["Production Cost"] + df["Reject Cost"]
			df.to_excel(f"Year15_{region_headers[region]}.xlsx")
			pd.set_option('display.max_columns', None)
			pd.set_option('display.width', 1000)
			# while True:
			# 	try:
			# 		use_sq = float(input("Input a float for an S/Q rating to evaluate"))
			# 		print("Best Cost")
			# 		print(df[df["SQ"] >= use_sq].sort_values("Total Cost", axis=0).head(5))
			# 		print("Best Earnings")
			# 		print(df[df["SQ"] >= use_sq].sort_values("Earnings Per Share", axis=0, ascending=False).head(5))
			# 	except:
			# 		break  # Just put something that can't be converted to a float to exit loop
		else:
			print("Not on branded production page. Aborting optimization")

	def get_page_specific_results(self):
		"""This is called by run_sweep, and will add different result keys depending on the page being viewed"""
		if self.driver.current_url.endswith("comp-training"):
			pass
		elif self.driver.current_url.endswith("branded-production"):
			pass



