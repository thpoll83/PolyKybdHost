import sys
import os

# Get absolute path of the current file (__main__.py)
current_file = os.path.abspath(__file__)
# Get the directory that contains this file
current_dir = os.path.dirname(current_file)
# Get the parent directory (the project root)
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

# Detect if the script is being run directly
if __name__ == "__main__" and parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print("Script is executed directly, sys.path corrected to:\n", sys.path)

# Now you can safely import from your package
from polyhost.main_app import main

main()
