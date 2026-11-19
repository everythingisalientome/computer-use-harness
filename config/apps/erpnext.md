---
schema_version: 1
id: erpnext
name: ERPNext (public demo site)
kind: web
launch:
  browser: chrome
  url: https://erpnext-demo.frappe.cloud/api/method/erpnext_demo.erpnext_demo.auth.login_demo
  wait_seconds: 8
# The allowed-app check. For a web app the window title is only the page title
# ("Customer", "New Quotation"), so a title match cannot prove which site is
# showing. The harness therefore checks that the foreground window is the one
# it launched for this app.
allowed_window:
  match: launched_window
  processes: [chrome.exe]
home:
  how: Click the logo at the top left of the page.
  looks_like: A page titled "Home" with a module list down the left side.
---

# ERPNext app context

Each line is marked **seen** (observed on the demo site on 2026-11-18) or **not checked**.

## Opening the app

- The launch address logs in automatically with no password and lands on the Home page after a few seconds. (seen)
- The site displays in a light theme on the build machine. (seen 2026-11-19; it was dark when viewed during planning on 2026-11-18)

## Layout

- A top bar runs across every page: logo at the left, a search box labelled "Search or type a command (Ctrl + G)" in the middle, Help and a user badge at the right. (seen)
- A breadcrumb at the top left shows where you are, for example "Selling > Customer". (seen)
- The Home page has a module list on the left: Accounting, Buying, Selling, Stock, Assets, HR, Payroll, Manufacturing, CRM, Quality, Projects, Support. (seen)

## Getting to a screen

- Typing a screen name such as "Customer List", "Item List" or "New Quotation" into the top search box and choosing the matching suggestion opens that screen. (not checked on this site)
- Customer is under Selling. Item is under Stock. Quotation is under Selling. (seen in breadcrumbs)

## List screens

- A row of filter boxes sits above the list. On the Customer list they are ID, Customer Name, Customer Group, Territory. On the Item list they are ID, Item Name, Item Group. (seen)
- Typing in a filter box narrows the list after a short pause. (not checked)
- A button at the top right adds a new record: "Add Customer", "Add Item". (seen)
- Each row shows a coloured status label, for example "Enabled" or "Template". (seen)

## Form screens

- A new form shows the label "Not Saved" next to its title until it is saved. (seen)
- The Save button is at the top right. (seen)
- Required fields are marked with an asterisk. (seen)
- Fields that refer to another record (Customer, Customer Group, Territory, Item Code) show a list of suggestions as you type. Choose the suggestion that matches exactly; typing alone does not set the field. (list seen on the Quotation's Customer field, 2026-11-19; "typing alone does not set the field" not checked)
- Each suggestion is two lines: the record's name in bold, then its details, for example "Acme Industries, Corporate, All Territories, +49 ...". (seen on the Customer field)
- Below the matching records the list always ends with two more entries: "Create a new Customer" and "Advanced Search". When only one record matches, the entry straight after it is "Create a new Customer". (seen on the Customer field)
- Never click "Create a new Customer" (or "Create a new ..." on any other field). Pick only a suggestion whose bold name matches the value exactly. If none matches, the step cannot proceed.

## Screen facts used by this procedure

- New Customer, first tab: Customer Name, Customer Type (defaults to "Company"), Customer Group (defaults to "All Customer Groups"), Territory (defaults to "All Territories"). (seen)
- Customer groups that exist: Corporate, Commercial, Individual, Government. (seen)
- New Quotation: Customer field, an Items table with columns Item Code, Quantity, Rate, Amount, and a "Total (INR)" field below the table. (seen)
- Amounts are in Indian rupees and use Indian digit grouping, for example 4,50,000.00. (currency seen; grouping not checked)

## Things to know

- An item whose status is "Template" is not a sellable product and must not be put on a quotation. (status seen; behaviour not checked)
- Saved quotations stay in "Draft" until someone presses Submit. This persona never presses Submit. (not checked)
- This is a public site shared with other visitors. Records may appear, change or disappear between runs. (known)

## Known interruptions

None observed yet. Add each one here as it is found, with how to dismiss it.
