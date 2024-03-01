
CREDIT_RANKINGS_MAP = {
	"C–": 0,
	"C": 1,
	"C+": 2,
	"B–": 3,
	"B": 4,
	"B+": 5,
	"A–": 6,
	"A": 7,
	"A+": 8
}


def format_to_number(some_text):
	output = some_text.replace("$", "").replace(",", "")
	if "%" in output:
		return float(output.replace("%", "")) # / 100
	elif "A" in output or "B" in output or "C" in output:
		return CREDIT_RANKINGS_MAP[output.strip()]
	else:
		return float(output)