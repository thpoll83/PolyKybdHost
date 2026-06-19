import os
import sys
import time

_t_process = time.monotonic()   # ~interpreter start (os/sys/time already loaded)

current_file = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file)
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

if __name__ == "__main__" and parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print("Script is executed directly, sys.path corrected to:\n", sys.path)

from polyhost._bootstrap import bootstrap_dependencies

bootstrap_dependencies(parent_dir)
_t_bootstrap = time.monotonic()

from polyhost.main_app import main

# Pass the early timestamps so main() can log how long bootstrap + the
# pre-logging imports took — to tell apart "our startup is slow" from
# "Windows took its time firing the task / cold-starting the interpreter".
main(launch_monotonic=_t_process, post_bootstrap_monotonic=_t_bootstrap)

