import dataclasses
import json
import subprocess
import sys
import os

from dataclasses import dataclass, field
from typing import List


"""
Needs pdftotext binary. apt-get install poppler-utils
sudo apt-get install build-essential libpoppler-cpp-dev pkg-config python-dev

Usage:
parse_poly_rest_api.py hdx-irm.pdf > hdx-irm.json
"""


@dataclass
class APIEndpoint:
    path: str = ''
    method: str = ''
    input: str = ''
    output: str = ''


@dataclass
class Multiline:
    target: str = ''
    search: List[str] = field(default_factory=list)
    buffer: List[str] = field(default_factory=list)


def parse(pdftotext_output):

    result = []

    cur = APIEndpoint()

    def _shift(**kwargs):
        nonlocal cur
        if cur.path:
            result.append(cur)
        cur = APIEndpoint(**kwargs)

    multiline: Multiline = None

    for line in pdftotext_output.split('\n'):

        if multiline:
            if line.strip() in multiline.search:
                setattr(cur, multiline.target, '\n'.join(multiline.buffer).strip())
                multiline = None
            else:
                multiline.buffer.append(line)
                continue

        if line.startswith('Path:'):
            if cur.path:
                _shift(path=line[len('Path:') :].strip())
            else:
                cur.path = line[len('Path:') :].strip()
        elif line.startswith('Method:'):
            cur.method = line[len('Method:') :].strip()
        elif line.strip() == 'Input':
            multiline = Multiline('input', ['Output', 'Applicable return codes'])
        elif line.strip() == 'Output':
            multiline = Multiline('output', ['Applicable return codes', 'Description'])
        elif line.strip() == 'Description':
            _shift()
            multiline = Multiline(
                'description',
                ['Protocol, Method, and', 'Protocol, Method, and Path', 'Protocol and Method'],
            )

    _shift()

    return result

def to_json(api_endpoints):

    return json.dumps([dataclasses.asdict(a) for a in api_endpoints], indent=2)

def run(pdf_filename: str):
    abs_filepath = os.path.join(os.path.dirname(__file__), pdf_filename)
    content = subprocess.check_output(['pdftotext', abs_filepath, '-'], encoding='utf-8')
    
    return parse(content)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        content = run(sys.argv[1])
        print(to_json(content))
