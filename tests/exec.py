"""A helper script to call from test_exec.py.

It requires 2 arguments, the output directory and filename.
A file will be created in the output directory with the given filename.
If there are more arguments to the script, they will be written 1 per line to the file.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    # Make sure we have an output folder argument
    if len(sys.argv) < 3:
        print("exec.py must have parameter for output directory and filename")
        sys.exit(1)
    out_dir = Path(sys.argv[1])
    filename = sys.argv[2]
    # Make sure the output folder exists
    if not out_dir.exists():
        print(f"output dir {sys.argv[1]} does not exist")
        sys.exit(1)

    with (out_dir / filename).open('w') as outfile:
        for arg in sys.argv[3:]:
            outfile.write(arg + '\n')
