import os

# Refactor locatarios_ui.py
with open('locatarios_ui.py', 'r') as f:
    lines = f.readlines()

form_start = -1
form_end = -1
list_start = -1

for i, line in enumerate(lines):
    if "# Form to Add Locatário" in line:
        form_start = i
    if 'st.markdown("---")' in line and form_start != -1 and list_start == -1:
        form_end = i
        list_start = i

if form_start != -1 and list_start != -1:
    header = lines[:form_start]
    form_block = lines[form_start:list_start]
    list_block = lines[list_start:]
    
    with open('locatarios_ui.py', 'w') as f:
        f.writelines(header)
        f.writelines(list_block)
        f.write("\n    st.markdown('---')\n")
        f.writelines(form_block)

# Refactor frota_ui.py
with open('frota_ui.py', 'r') as f:
    lines = f.readlines()

form_start = -1
form_end = -1
list_start = -1

for i, line in enumerate(lines):
    if "# Form to Add Moto" in line:
        form_start = i
    if 'st.markdown("---")' in line and form_start != -1 and list_start == -1:
        form_end = i
        list_start = i

if form_start != -1 and list_start != -1:
    header = lines[:form_start]
    form_block = lines[form_start:list_start]
    list_block = lines[list_start:]
    
    with open('frota_ui.py', 'w') as f:
        f.writelines(header)
        f.writelines(list_block)
        f.write("\n    st.markdown('---')\n")
        f.writelines(form_block)

print("Refactored successfully")
