#!/usr/bin/env python3
"""Populate Sales Stage Revision tab in RevOps Backlog & Action Tracker."""
import json, subprocess, sys

SHEET_ID = "REDACTED_GOOGLE_ID"

def gwsg(*args):
    r = subprocess.run(["gwsg"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print("ERR:", r.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)

# ---- Main matrix: New Business Stages ----
# Columns: Stage # | HubSpot Stage | Probability | Stage Criteria | Stage Activities | Exit Criteria | Required Fields | Secondary (non-required)
stages = [
    ["0", "Qualification", "0%",
     "Lead validated on conversion. Discovery call scheduled. Primary contact placed on opp (attribution/sourcing source).",
     "Run discovery call. Capture current situation, challenge/goal, current solutions, estimated assets. Confirm fit and mutual problem.",
     "Discovery Call Held Date, Estimated ARR, Mutually Agreed Problem Statement, Connectors/tech, Challenge/Goal, Project Timeline, Budget, Next Steps",
     "Discovery Meeting Date, Time Zone, Current Situation, Challenge/Goal, Discovery Call Scheduled Date, Discovery Call Time, Close Date, xDR Notes, Current Solution(s), # of estimated assets/licenses, Primary Contact",
     "Current Solution End Date (new field, not required)"],
    ["1", "Value Alignment", "1%",
     "Mutually agreed problem statement confirmed. Value proposition aligned to org goals.",
     "Align solution to future state and org goals. Engage Solutions Engineer. Confirm budget and project timeline.",
     "Solutions Engineer, Future State & Organization Goals",
     "Discovery Call Held Date, Estimated ARR, Mutually Agreed Problem Statement, Connectors/tech, Challenge/Goal, Project Timeline, Budget, Next Steps",
     ""],
    ["2", "Planning", "25%",
     "Evaluation approach defined. MAP document and competitor identified. Preliminary pricing shared.",
     "Build MAP document. Identify competitor. Define evaluation type (Full POC / Workshop / No Evaluation). Share preliminary pricing.",
     "MAP Document, Competitor, Evaluation Type. IF Evaluation Type = Full POC THEN POC Kickoff Date required. Preliminary Pricing Shared (checkbox)",
     "Evaluation Type, POC Kickoff Date, MAP Document, Competitor, Preliminary Pricing Shared",
     "Expected Full POC Started Date, POC Status, Extension Reason, POC Instance License, POC Summary Presentation, SE Notes, POC Active"],
    ["3", "Evaluation", "40%",
     "POC / evaluation running. Success criteria validated. Technical criteria assessed.",
     "Run POC. Validate success criteria. Assess technical criteria met/not met. Prepare executive summary. Confirm vendor of choice.",
     "Executive Buyer, Validation of Success Criteria, Executive Summary, Executive Summary shared date, POC Start & End Date, Vendor of Choice, Technical Criteria Met, Technical Criteria NOT Met Reason, Testing working as it should, Technical Selection Status",
     "Executive Summary, Executive Summary shared date, Validation of Success Criteria, Vendor of Choice, Expected POC Start Date, POC End Date, Extension Reason, POC Summary Presentation, Technical Criteria Met, Technical Criteria NOT Met Reason, Technical Selection Status, POC Instance License, SE Notes, POC Active",
     ""],
    ["4", "Decision", "65%",
     "Vendor of choice confirmed. Decision process underway. Commercial terms being finalized.",
     "Drive decision process. Issue DealHub quote. Negotiate terms.",
     "Decision Process, DealHub quote issued",
     "Executive Buyer, Validation of Success Criteria, Executive Summary, Executive Summary shared date, POC Start & End Date, Vendor of Choice, Technical Criteria Met, Technical Criteria NOT Met Reason, Technical Selection Status",
     ""],
    ["5", "Purchasing", "90%",
     "Quote accepted. Procurement / legal in progress. Handoff to CSM prepared.",
     "Finalize contract. Prepare CSM handoff. Confirm technical contact and instance details.",
     "Technical Contact, Requested URL Instance Name, Link to CSM Handoff document",
     "Decision Process, DealHub quote issued",
     ""],
    ["6", "Closed Won", "100%",
     "Deal closed. Contract signed.",
     "Log close. Capture closed won reason.",
     "Closed Won Reason, Close Date",
     "Technical Contact, Requested URL Instance Name, Link to CSM Handoff document",
     ""],
    ["7", "Closed Lost", "0%",
     "Deal lost. Reason captured.",
     "Log loss reason.",
     "Closed Lost Reason, Product Loss Reason, Detailed Loss Reason, Last Status Before Close Lost, Last Stage to Close",
     "Closed Won Reason, Close Date",
     ""],
]

# ---- Stage progression required fields ----
progression = [
    ["0 - Qualification", "1 - Value Alignment",
     "Discovery Call Held Date, Estimated ARR, Mutually Agreed Problem Statement, Connectors/tech, Challenge/Goal, Project Timeline, Budget, Next Steps"],
    ["1 - Value Alignment", "2 - Planning",
     "Solutions Engineer, Future State & Organization Goals"],
    ["2 - Planning", "3 - Evaluation",
     "MAP Document, Competitor, Evaluation Type (Full POC / Workshop / No Evaluation). IF Full POC THEN POC Kickoff Date. Preliminary Pricing Shared (checkbox)"],
    ["3 - Evaluation", "4 - Decision",
     "Executive Buyer, Validation of Success Criteria, Executive Summary, Executive Summary shared date, POC Start & End Date, Vendor of Choice, Technical Criteria Met, Technical Criteria NOT Met Reason, Testing working as it should, Technical Selection Status"],
    ["4 - Decision", "5 - Purchasing",
     "Decision Process, DealHub quote issued"],
    ["5 - Purchasing", "6 - Closed Won",
     "Technical Contact, Requested URL Instance Name, Link to CSM Handoff document"],
]

# ---- Closed lost rules ----
closed_lost = [
    ["Stage 0 - Qualification to Closed Lost",
     "Stage-0 Closed Lost Reason (NEW required field, picklist). Lives under Discovery Meeting Details section. Validation rule: IF moving to Closed Lost in Stage 0 THEN reference Stage-0 Closed Lost Reason (currently rule references Closed Lost Reason + Detailed Loss Reason, which is the Stage 1+ rule).",
     "Not Qualified - Timing, Not Qualified - Need, Not Qualified - Budget, Not Qualified - No authority, No show - Unresponsive"],
    ["Stage 1 through 5 to Closed Lost",
     "Closed Lost Reason (working as it should), Product Loss Reason (working as it should), Detailed Loss Reason (working as it should)",
     ""],
]

# ---- Lead conversion required fields ----
conversion = [
    ["XDR Owner", "Required on conversion"],
    ["Discovery Call Scheduled Date", "Required on conversion"],
    ["Discovery Call Time", "Required on conversion"],
    ["Time Zone", "New field, picklist of all time zones. Populates onto new biz opp."],
    ["Close Date", "Required on conversion"],
    ["Current Situation", "Required on conversion"],
    ["Challenge / Goal", "Required on conversion"],
    ["xDR Notes", "Required on conversion"],
    ["Current Solution(s)", "Required on conversion"],
    ["Current Solution End Date", "New field, NOT required"],
    ["# of estimated assets", "Confirmed populates onto new biz opp"],
    ["Primary Contact", "Placed on opp at top of page on conversion. Source of opp attribution/sourcing."],
    ["Discovery Call Held", "On opp"],
    ["# of estimated assets/licenses", "On opp"],
]

# ---- Renewal / ownership ----
renewal = [
    ["Opportunity Owner",
     "When a new business or upsell opportunity is created, the AE Owner should be the opportunity owner. Logic in production today unclear."],
    ["New account created at same time as new biz opp",
     "AE should be owner of the new biz opp AND the account page."],
    ["New biz opp created AND existing account exists",
     "Opportunity owner should be the account owner."],
    ["Before conversion",
     "Ownership fields show {{REVOPS_1}} as account owner (reference screenshot)."],
]

# ---- Data migration & go-live ----
migration = [
    ["Update existing workflows in SFDC with new stage names",
     "Is there a way to set flows up so we don't have to reference names?"],
    ["Stage timestamp migration",
     "Will we need to update existing opps with new stages and old timestamps? If so, pull a report on opp stage history from beginning of xFY and do the update."],
    ["Map current sales stages to new sales stages",
     "For open new biz opps. What happens to closed won/lost opps and their sales stages? New stages or old stages?"],
    ["Existing validation rules",
     "Ensure current validation rules that aren't changing stay in place and continue to work."],
    ["Files needed for data migration",
     "Data Migration List for Stage Revision."],
    ["Existing fields transferred to new field",
     "What about existing fields today being transferred over to a new field?"],
    ["Existing opp in later phase when new process implemented",
     "Will the AE have to go back and fill out missing requirements?"],
]

go_live = [
    ["1. Push to production date", "What day is best to push to production?"],
    ["2. QA testing plan", "What is the QA testing plan once live?"],
    ["3. Flow updates", "How do we ensure all flows have been updated correctly?"],
    ["4. Post-live support", "What is the post-live support plan?"],
    ["5. Timestamp migration", "Confirming we do NOT need a timestamp migration because we use the same fields, just re-labeled existing timestamp fields. What about the new stage?"],
    ["6. Existing opp stage mapping", "What is the plan for existing opportunity stage mapping to the new stages?"],
]

# ---- Evaluation type picklist ----
eval_type = [
    ["Full POC", "IF selected, POC Kickoff Date required"],
    ["Workshop", ""],
    ["No Evaluation", "Replace 'Sandbox' with 'No Evaluation'. NOT listed on dropdown picklist."],
]

# ---- Field section mapping (2-Planning vs 3-Evaluation) ----
field_sections = [
    ["2 - Planning section (relabeled from '2-Proof of Value w/POC')",
     "Evaluation Type, POC Kickoff Date, MAP Document, Competitor, Preliminary Pricing Shared"],
    ["3 - Evaluation section",
     "Executive Summary, Executive Summary shared date, Validation of Success Criteria, Vendor of Choice, Expected POC Start Date, POC End Date, Extension Reason, POC Summary Presentation, Technical Criteria Met, Technical Criteria NOT Met Reason, Technical Selection Status, POC Instance License, SE Notes, POC Active"],
    ["5 - Purchasing section (NEW)",
     "Technical Contact, Requested URL Instance Name, Link to CSM Handoff document (moved from opp)"],
    ["Fields moved down to 3-Evaluation",
     "POC Status, POC Stage"],
    ["Fields that stay on opp",
     "Expected Full POC Started Date (renamed from Expected POC Start Date), POC Status, Extension Reason, POC Instance License, POC Summary Presentation, SE Notes, POC Active"],
]

def write_range(tab, rng, values):
    body = {"range": f"'{tab}'!{rng}", "majorDimension": "ROWS", "values": values}
    gwsg("sheets", "spreadsheets", "values", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps({"valueInputOption": "USER_ENTERED", "data": [body]}))

# Main stages tab
write_range("Sales Stage Revision", "A1:H9",
    [["Stage #", "HubSpot Stage", "Probability", "Stage Criteria", "Stage Activities", "Exit Criteria", "Required Fields", "Secondary (non-required)"]] + stages)

# Add supporting tabs
tabs = [
    ("Stage Progression", ["From Stage", "To Stage", "Required Fields to Progress"], progression),
    ("Closed Lost Rules", ["Scenario", "Requirements", "Picklist Options"], closed_lost),
    ("Lead to Opp Conversion", ["Field", "Requirement / Notes"], conversion),
    ("Renewal & Ownership", ["Topic", "Logic / Notes"], renewal),
    ("Data Migration Notes", ["Topic", "Question / Note"], migration),
    ("Push to Production", ["#", "Question", "Details"], go_live),
    ("Evaluation Type Picklist", ["Option", "Notes"], eval_type),
    ("Field Section Mapping", ["Section", "Fields"], field_sections),
]

for name, header, rows in tabs:
    gwsg("sheets", "spreadsheets", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps({"requests": [{"addSheet": {"properties": {"title": name}}}]}))
    write_range(name, "A1", [header] + rows)

print("DONE")
