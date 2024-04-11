import multiprocessing
import time
import itertools
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

	@staticmethod
	def filter_production_df(prod_df, min_image, min_sq, max_reject_rate):
		output = prod_df[(prod_df["Image Rating"] >= min_image) & (prod_df["SQ"] >= min_sq) & (prod_df["Reject Rate"] <= max_reject_rate)].sort_values("Net Profit ", ascending=False)
		if len(output) == 0:  # Nothing within the constraints
			output = prod_df[prod_df["SQ"] == max(prod_df["SQ"])].sort_values("Net Profit ", ascending=False)
		return output

	def optimize_production(self):
		self.driver.switch_to.window(self.driver.window_handles[-1])
		if self.driver.current_url.endswith("branded-production"):
			region_headers = {
				0: "NorthAmerica",
				1: "Europe",
				2: "Asia",
				3: "LatinAmerica"
			}
			sup_label = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td[text()='Superior Materials %']")
			material_selections = sup_label.find_elements(By.XPATH, "../td/div/glo-entry-select/select")
			styling = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/span[text()='Enhanced Styling / Features ']")
			styling_selections = styling.find_elements(By.XPATH, "../../td/div/glo-entry-select/select")
			tqm = self.driver.find_element(By.XPATH, "//div/div/table/tbody/tr/td/span[text()='TQM / 6-Sigma Quality Program ']")
			tqm_selections = tqm.find_elements(By.XPATH, "../../td/div/glo-entry-select/select")
			reject_rating_span = self.driver.find_element(By.XPATH,"//div/div/table/tbody/tr/td/span[text()='Projected Reject Rate ']")
			reject_ratings = reject_rating_span.find_elements(By.XPATH, "../../td[contains(@class, 'ng-star-inserted')]")
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
			profit_scan = input("Optimize for profit?")
			if "y" in profit_scan:
				q_list = [x.text for x in quality.options]
				s_list = [x.text for x in style.options]
				m_list = [x.text for x in material.options]
				"""Optimize profit by scanning for the most profitable selection from each row, and iterating until no options provide a better profit"""
				def build_result(result_quality=None, result_style=None, result_material=None):
					if result_quality is None:
						result_quality = float(quality.first_selected_option.text)
					if result_style is None:
						result_style = int(style.first_selected_option.text)
					if result_material is None:
						result_material = int(material.first_selected_option.text)
					this_result = {
						"Reject Rate": float(reject_ratings[region].text.replace("%", "")),
						"Quality": result_quality,
						"Style": result_style,
						"Material": result_material,
						"SQ": float(sq_ratings[region].text.replace("★", "")),
						"Production Cost": float(production_costs[region].text),
						"Reject Cost": float(reject_costs[region].text.replace("$", ""))
					}
					for k, v in {met: self.get_metric(met)[0] for met in self.metrics}.items():
						this_result[k] = v
					return this_result

				min_image = int(input("Specify minimum image allowed"))
				min_sq = float(input("Specify minimum SQ allowed"))
				max_reject = float(input("Specify maximum reject rate"))
				initial_result = build_result()
				best = {
					"Material": int(material.first_selected_option.text),
					"Style": int(style.first_selected_option.text),
					"Quality": float(quality.first_selected_option.text)
				}
				results = pd.DataFrame([initial_result])
				break_loop = False
				first_loop = True
				while break_loop is False:
					new_results = []
					res_quality = float(quality.first_selected_option.text)
					res_style = int(style.first_selected_option.text)
					if first_loop:
						# Only do a full sweep on the first loop
						for m_s in material.options:
							material.select_by_visible_text(m_s.text)
							new_results.append(build_result(result_quality=res_quality, result_style=res_style, result_material=int(m_s.text)))
						results = pd.concat([results, pd.DataFrame(new_results)]).reset_index(drop=True)
						best_row = self.filter_production_df(results, min_image, min_sq, max_reject)
						material.select_by_visible_text(str(best_row["Material"].values[0]))
						res_material = int(material.first_selected_option.text)

						new_results = []
						for s_s in style.options:
							style.select_by_visible_text(s_s.text)
							new_results.append(build_result(result_quality=res_quality, result_style=int(s_s.text), result_material=res_material))
						results = pd.concat([results, pd.DataFrame(new_results)]).reset_index(drop=True)
						best_row = self.filter_production_df(results, min_image, min_sq, max_reject)
						style.select_by_visible_text(str(best_row["Style"].values[0]))
						res_style = int(style.first_selected_option.text)

						new_results = []
						for q_s in quality.options:
							quality.select_by_visible_text(q_s.text)
							new_results.append(build_result(result_quality=float(q_s.text), result_style=res_style, result_material=res_material))
						results = pd.concat([results, pd.DataFrame(new_results)]).reset_index(drop=True)
						quality.select_by_visible_text(f"{best_row["Quality"].values[0]:.2f}")

					best_row = self.filter_production_df(results, min_image, min_sq, max_reject)
					# Now do a sweep around this best option
					center_q = best_row[["Material", "Style", "Quality"]].values[0][2]
					center_s = best_row[["Material", "Style", "Quality"]].values[0][1]
					center_m = best_row[["Material", "Style", "Quality"]].values[0][0]
					center_q_index = q_list.index(f"{center_q:.2f}")
					center_s_index = s_list.index(f"{center_s:.0f}")
					center_m_index = m_list.index(f"{center_m:.0f}")
					if first_loop:
						OFFSET = 3
						first_loop = False
					else:
						OFFSET = 5
					print("Determining loop values needed")
					# Figure out all the values needed for the sweep
					sweep_needed = list(
						itertools.product(q_list[max(0, center_q_index - OFFSET):center_q_index + OFFSET],
										  s_list[max(0, center_s_index - OFFSET):center_s_index + OFFSET],
										  m_list[max(0, center_m_index - OFFSET):center_m_index + OFFSET]))
					# Now eliminate values that we already computed to avoid duplicated work
					to_run = []
					for qual, sty, mat in sweep_needed:
						run_exists = ((results['Quality'] == float(qual)) & (results['Style'] == int(sty)) & (results["Material"] == int(mat))).any()
						if not run_exists:
							to_run.append({"Quality": qual, "Style": sty, "Material": mat})

					sweep_results = []
					using_qual = None
					using_mat = None
					using_sty = None
					for row in to_run:
						if using_qual is None:
							quality.select_by_visible_text(row["Quality"])
							using_qual = row["Quality"]
							style.select_by_visible_text(row["Style"])
							using_sty = row["Style"]
							material.select_by_visible_text(row["Material"])
							using_mat = row["Material"]
							sweep_results.append(
								build_result(result_quality=float(row["Quality"]), result_style=int(row["Style"]),
											 result_material=int(row["Material"])))
						else:
							if using_qual != row["Quality"]:
								quality.select_by_visible_text(row["Quality"])
								using_qual = row["Quality"]
							if using_sty != row["Style"]:
								style.select_by_visible_text(row["Style"])
								using_sty = row["Style"]
							if using_mat != row["Material"]:
								material.select_by_visible_text(row["Material"])
								using_mat = row["Material"]
							sweep_results.append(build_result(result_quality=float(row["Quality"]), result_style=int(row["Style"]), result_material=int(row["Material"])))

					# for q in q_list[max(0, center_q_index - OFFSET):center_q_index + OFFSET]:
					# 	quality.select_by_visible_text(q)
					# 	for s in s_list[max(0, center_s_index - OFFSET):center_s_index + OFFSET]:
					# 		style.select_by_visible_text(s)
					# 		for m in m_list[max(0, center_m_index - OFFSET):center_m_index + OFFSET]:
					# 			material.select_by_visible_text(m)
					# 			sweep_results.append(build_result(result_quality=float(q), result_style=int(s), result_material=int(m)))
					results = pd.concat([results, pd.DataFrame(sweep_results)]).reset_index(drop=True)

					# Now determine if we have found a new best combo since our last loop through
					best_row = self.filter_production_df(results, min_image, min_sq, max_reject)
					new_bests = best_row[["Material", "Style", "Quality"]]
					material.select_by_visible_text(f"{new_bests.values[0][0]:.0f}")
					style.select_by_visible_text(f"{new_bests.values[0][1]:.0f}")
					quality.select_by_visible_text(f"{new_bests.values[0][2]:.2f}")
					if new_bests.values[0][0] == best["Material"] and new_bests.values[0][1] == best["Style"] and new_bests.values[0][2] == best["Quality"]:
						print(f"Determined optimal inputs to be: {best}")
						break_loop = True
					else:
						print(f"Previous best was: {best}\nNew best is: {best_row.head(1)}")
						best["Material"] = new_bests.values[0][0]
						best["Style"] = new_bests.values[0][1]
						best["Quality"] = new_bests.values[0][2]
				results.to_excel(f"Best_Profit_{region_headers[region]}.xlsx")
			else:
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



