import os, csv


class PathToComponent():
  def __init__(self) -> None:
    self.map_ = self._get_mapper()
    
  def _get_mapper(self):
    map_ = {}
    mapper_path = self._mapper_path
    mapper_file = open(mapper_path, newline='')
    mapper_reader = csv.reader(mapper_file, delimiter=' ', skipinitialspace=True)

    for (path, component) in mapper_reader:
      map_[path] = component
    return map_

  @property
  def _mapper_path(self):
    ROOT_GITHOOK_DIR = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(ROOT_GITHOOK_DIR, 'file_component_mapping')

  # def does_component_exist(self, component: str) -> bool:
    # return component in self.map_
  
  def get_component(self, path: str) -> str:
    if path in self.map_:
      return self.map_[path]
    file_dir, filename = os.path.split(path)
    if file_dir in [".", ""]: # file at root of the repo
      return filename
    return file_dir

  def get_all_components(self, paths: list) -> list:
    components = []
    for path in paths:
      component_ = self.get_component(path)
      if component_:
        components += [component_]
    return components

# print(PathToComponent().get_component_name(".somehing.tt"))
  