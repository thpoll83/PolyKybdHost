import os
import sys

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

if __name__ == "__main__" and parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print("Script is executed directly, sys.path corrected to:\n", sys.path)

from polyhost._bootstrap import bootstrap_dependencies

bootstrap_dependencies(parent_dir)

from polyhost.main_app import main

main()
