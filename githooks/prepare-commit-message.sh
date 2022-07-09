#!/usr/bin/python

import csv


# file_component_mapping = open('file_component_mapping.csv', newline='') as csvfile
# print(csv.DictReader(file_component_mapping))




# commit_msg_filepath = ROOT_DIR + "/.git/COMMIT_EDITMSG"
# if len(sys.argv) > 2:
#   commit_type = sys.argv[2]
# else:
#   commit_type = ''
# if len(sys.argv) > 3:
#   commit_hash = sys.argv[3]
# else:
#   commit_hash = ''
# print("prepare-commit-msg: File: %s\nType: %s\nHash: %s" % (commit_msg_filepath, commit_type, commit_hash))




# files_changed = subprocess.check_output(['git','diff','--cached','--name-only']).decode("utf-8") 
# files_changed = files_changed.split("\n")

# # changed files to component mapping
# component_mapper = PathToComponent()
# components = component_mapper.get_all_components(files_changed)
# # print("files_changed: ", files_changed)
# # print("components: ", components)

# # sign-off
# signoff_ = subprocess.check_output(['git', 'var', 'GIT_COMMITTER_IDENT'])
# signoff_ = signoff_.decode('utf-8').split(" ")
# signoff = f'Signed-off-by: {" ".join(signoff_[:-2])}'
# # signoff = re.sub(r'^\s*>\s*$', 'Signed-off-by: \1', signoff_, re.M)
# # commiter = subprocess.Popen(['git', 'var', 'GIT_COMMITTER_IDENT'], stdout=subprocess.PIPE)
# # signoff = subprocess.check_output(['sed', '-n', 's/^\(.*>\).*$/Signed-off-by: \1/p'], stdin=commiter.stdout)
# # commiter.stdout.close() 
# # SOB, err = signoff.communicate()
# SOB = signoff


# SOB = subprocess.check_output(['git','var','GIT_COMMITTER_IDENT']).decode("utf-8") 


# SOB = subprocess.check_output("git var GIT_COMMITTER_IDENT | sed -n 's/^\(.*>\).*$/Signed-off-by: \1/p'")
# SOB = subprocess.run("git var GIT_COMMITTER_IDENT | sed -n 's/^\(.*>\).*$/Signed-off-by: \1/p'")
# print("SOB", SOB)


# print(sys.argv[2])

# with open(commit_msg_filepath, 'r+') as f:
#   content = f.read()
#   f.seek(0, 0)
#   f.write("ISSUE- %s" % (content))




