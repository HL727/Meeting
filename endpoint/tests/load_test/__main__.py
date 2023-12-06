import sys

from simulator.wsgi import BASE_URL, run

run(sys.argv[1] if len(sys.argv) > 1 else BASE_URL)
