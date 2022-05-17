#!/usr/bin/python

import csv

file_component_mapping = open('file_component_mapping.csv', newline='') as csvfile
print(csv.DictReader(file_component_mapping))
