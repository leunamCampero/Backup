#################################
## This script create templated SQL files based on geovelo conditions and copy
## a command to execute to clipboard

from pathlib import Path
import pyperclip
from string import Template
import subprocess
import shlex
from name_format import name
import os
# subprocess.run(["cd", "C:\\Users\\camperom\\safety-of-bike-networks\\Code\\OSM_extract\\2024\\First_project_2024"])
os.chdir("C:\\Users\\camperom\\safety-of-bike-networks\\Code\\OSM_extract\\2024\\First_project_2024")
sql_query_dir = "./sql"
extract_dir = "./extract"

# Create a new output directory for queries and extract
Path(sql_query_dir).mkdir(exist_ok=True)
Path(extract_dir).mkdir(exist_ok=True)

# List all sql files in the geovelo directory
path_to_geovelo = './requetes_amenagements_cyclables-master'
files = list(Path(path_to_geovelo).rglob('*.sql'))

# For each file, create a new SQL file with completed query, from template file
# Output format will be: key (= name(<filename>) :  value = geojson

for i,f in enumerate(files):
    with open(f, "r") as file:
        content = file.read()
    d = {
            'conditions': content,
            'feature_name': name(f)
        }
    # generate a new query by filling the template
    with open('C:\\Users\\camperom\\safety-of-bike-networks\\Code\\OSM_extract\\2024\\First_project_2024\\sql_template.sql', 'r') as template:
        src = Template(template.read())
        result = src.substitute(d)

    # write a new sql file
    with open(f'{sql_query_dir}/{name(f)}.sql', "w", encoding="UTF8") as f:
        f.write(result)

result_file = f'{extract_dir}/extract_m.txt'
# result_file = f'{extract_dir}/extract_ee.txt'
# result_file = f'{extract_dir}/extractten.txt'
# result_file = f'{extract_dir}/extract.txt'
# result_file = f'{extract_dir}/extractvilles.txt'

# List files in completed queries folder
files = [p.name for p in Path(sql_query_dir).rglob('*.sql')]

# build a command to run all the sql files
# 1 connect to database
# 2 to run all files a transaction needs to be opened
# 3 append all files
# 4 close transaction
# extract output as csv

# cmd = "psql -U osmuservilles -d osmvilles " +\
# cmd = "psql -U osmuser_ra -d osm_ra " +\
cmd = "psql -U osmuser_m -d osm_m " +\
        '-c "BEGIN TRANSACTION;" ' + \
        ' '.join([f'-f {sql_query_dir}/{file}' for file in files]) +\
        ' -c "COMMIT;" ' +\
        f'--csv -o {result_file} -q'

# copy to clipboard
pyperclip.copy(cmd)

print("Command copied to clipboard !")

print("Executing command: " + cmd)

# Execute the command line directly
subprocess.run(shlex.split(cmd))