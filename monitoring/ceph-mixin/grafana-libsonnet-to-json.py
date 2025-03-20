import json
from jinja2 import Environment, FileSystemLoader

with open("dashboards_out/nvmeof-new.json", "r") as f:
    data = json.load(f)


# Load the Jinja2 environment from the current directory
env = Environment(loader=FileSystemLoader("."))

# Load the template
template = env.get_template("test.libsonnet.j2")

# Define values for the template
context = {
    "namespace": "production",
    "replicas": 3,
    "resources": {"cpu": "500m", "memory": "256Mi"},
}

# Render the template with data
output = template.render(data)

# Save to a libsonnet file
with open("output.libsonnet", "w") as f:
    f.write(output)

print("Generated output.libsonnet ✅")
