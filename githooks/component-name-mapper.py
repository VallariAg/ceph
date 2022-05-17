import os, csv

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

# file_component_mapping = open('./file_component_mapping', newline='')
mapping_file = open(ROOT_DIR + '/githooks/file_component_mapping', newline='')
mapping_file_reader = csv.reader(mapping_file, delimiter=' ', skipinitialspace=True)

def get_filepath_component_mapper() -> dict: 
  file_component_mapper = {}
  
  for (file_path, component) in mapping_file_reader:
    file_component_mapper[file_path] = component

  return file_component_mapper


PATH_TO_COMPONENT = get_filepath_component_mapper()

def does_component_exist(component) -> bool:
  return component in PATH_TO_COMPONENT
