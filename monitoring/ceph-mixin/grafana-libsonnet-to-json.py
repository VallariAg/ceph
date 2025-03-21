import json
from jinja2 import Environment, FileSystemLoader

with open("dashboards_out/nvmeof-new.json", "r") as f:
    data = json.load(f)

# Convert Python booleans to lowercase JSON format
json_data = json.dumps(data)  # Ensures `true` instead of `True`
data = json.loads(json_data)  # Load it back as a dictionary
# Load the Jinja2 environment from the current directory
env = Environment(loader=FileSystemLoader("."))

# Load the template
template = env.get_template("test.libsonnet.j2")

# Render the template with data
output = template.render(data)

# Save to a libsonnet file
with open("dashboards/test.libsonnet", "w") as f:
    f.write(output)

print("Generated output.libsonnet ✅")
