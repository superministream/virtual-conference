import sys
import re

import core.excel_db as excel_db
import core.schedule as schedule

USAGE = """
./populate_paper_info.py <paper_info.xlsx> <paper_info_sheet> <uid prefix> <schedule_db.xlsx>
"""

if len(sys.argv) != 5:
    print(USAGE)
    sys.exit(1)

nonalphanumeric = re.compile("[^A-Za-z0-9]")

def make_normalized_title(title):
    if not title:
        return ""
    norm = nonalphanumeric.sub("", title)
    return norm.lower()

paper_info_db = excel_db.open(sys.argv[1])
paper_info = paper_info_db.get_table(sys.argv[2])
uid_prefix = sys.argv[3]
schedule_db = schedule.Database(sys.argv[4])

# Go through the papers in paper info and make the stripped title slug to look up,
# then go find it in the schedule
days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
for paper in paper_info.items():
    found_paper = False
    # We're done when we run out of paper titles
    title = paper["Title"].value
    if not title:
        break
    norm_title = make_normalized_title(paper["Title"].value)
    for d in days:
        day_info = schedule_db.get_day(d)
        found = day_info.sheet.find_if(lambda p: make_normalized_title(p["Time Slot Title"].value) == norm_title)
        if len(found) == 1 and not found_paper:
            row = found[0]
            day_info.entry(row, "UID").value = uid_prefix + "-" + str(paper["Paper ID"].value)
            day_info.entry(row, "Contributor Email(s)").value = paper["Contact email"].value
            if "Abstract" in paper:
                day_info.entry(row, "Abstract").value = paper["Abstract"].value
            if "Keywords" in paper:
                keywords = paper["Keywords"].value
                if ";" in keywords:
                    keywords = keywords.split(";")
                elif "," in keywords:
                    keywords = keywords.split(",")
                else:
                    keywords = [keywords]
                for i in range(0, len(keywords)):
                    keywords[i] = keywords[i].strip()

                day_info.entry(row, "Keywords").value = "|".join(keywords)
            found_paper = True
            schedule_db.save("papers_assigned.xlsx")
        elif (len(found) != 0 and found_paper) or len(found) > 1:
            print(f"found multiple entry for {paper['Title'].value}!?")
    if not found_paper:
        print(f"WARNING: Failed to find time slot for paper '{paper['Title'].value}'")
        print(f"Normalized title: {norm_title}")


