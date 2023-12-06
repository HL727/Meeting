import requests
import sys

requests.post(sys.argv[1], {'message': sys.stdin.read()})
