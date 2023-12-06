import sys
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[404, 429, 500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

url = sys.argv[1]

timeout = 10
if len(sys.argv) > 2:
    timeout = int(sys.argv[2])

try:
    response = session.get(sys.argv[1], timeout=timeout)
    if response.status_code != 200:
        raise ValueError('Invalid Status {}'.format(response.status_code))
    print('200 OK')
except Exception as e:
    print(str(e))
    sys.exit(1)
