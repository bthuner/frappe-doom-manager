import frappe


def execute():
	"""Give runs recorded before the outcome field existed a truthful outcome.

	Those rows were written by the old one-shot record_run, which inserted and
	submitted in a single call. Adding the field stamped them all with its
	"In Progress" default, which contradicts their docstatus of 1 -- a submitted
	run is by definition over. `completed` already says how each one ended, so
	derive the outcome from it.

	Their kills/items/secrets stay as they are: those were percentages, and the
	level totals they would need to become counts were never recorded. total_* is
	0 for them, which the UI's ratio() helper renders as a bare number.
	"""
	table = frappe.qb.DocType("Doom Run")

	for completed, outcome in ((1, "Completed"), (0, "Died")):
		frappe.qb.update(table).set(table.outcome, outcome).where(
			(table.docstatus == 1) & (table.outcome == "In Progress") & (table.completed == completed)
		).run()

	frappe.db.commit()
