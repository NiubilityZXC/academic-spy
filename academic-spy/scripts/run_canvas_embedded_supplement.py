import sys

import canvas_embedded_supplement as ces
from canvas_runtime import apply_runtime


ce = apply_runtime()


if __name__ == "__main__":
    ces.main(sys.argv[1:] or None)
