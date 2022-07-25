import os, csv
import fnmatch, re
from collections import Counter


class PathToComponent():
  def __init__(self) -> None:
    self.mapper = self._get_mapper()

  def _get_mapper(self):
    mapper = []
    mapper_path = self._mapper_path
    mapper_file = open(mapper_path, newline='')
    mapper_reader = csv.reader(mapper_file, delimiter=' ', skipinitialspace=True)

    for (path, component) in mapper_reader:
      path_regex = fnmatch.translate(path)
      path_regexobj = re.compile(path_regex)
      mapper += [(component, path_regexobj)]
    return mapper

  @property
  def _mapper_path(self):
    ROOT_GITHOOK_DIR = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(ROOT_GITHOOK_DIR, 'file_component_mapping')
  
  def get_component(self, path: str) -> str:
    for (component, path_regexobj) in self.mapper:
      if path_regexobj.match(path):
        return component
    file_dir, filename = os.path.split(path)
    if file_dir in [".", "", "/"]:
      return filename
    return file_dir

  def get_all_components(self, paths: list) -> list:
    components = []
    for path in paths:
      component_ = self.get_component(path)
      if component_:
        components += [component_]
    sorted_components = [item[0] for item in Counter(components).most_common()]
    return sorted_components


# print(PathToComponent().get_component_name(".somehing.tt"))
  