import dataclasses
import json
import subprocess
import sys
import os

from dataclasses import dataclass, field
from typing import List, Dict


"""
Needs pdftotext binary. apt-get install poppler-utils
sudo apt-get install build-essential libpoppler-cpp-dev pkg-config python-dev

Usage:
parse_poly_rest_api.py ucsoftware-6-4-2-rest-api-ref-guide.pdf > ucsoftware-6-4-2-rest-api-ref-guide.json
"""


@dataclass
class APIEndpoint:
    commands: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    outputs: str = ''

@dataclass
class Multiline:
    target: str = ''
    search: List[str] = field(default_factory=list)
    buffer: List[str] = field(default_factory=list)


def parse(pdftotext_output):

    result = []
    mode = 'none'
    iter = -1
    cur = APIEndpoint()
    lines = pdftotext_output.split('\n')



    for line in lines:
        # print(mode)
        
        iter += 1

        if mode == 'feedback' and line == '':
            mode = 'one element complete'
            continue
        if line.startswith('Feedback Examples'):
            mode = 'feedback'
            continue
        if line.startswith('Parameter') and line.endswith('Parameter') and lines[iter+2].startswith('Description') and lines[iter+2].endswith('Description'):
            mode = 'none'
            continue
        if line.startswith('Description') and line.endswith('Description'):
            mode = 'parameter'
            continue
        if line.startswith('Syntax') and line.endswith('Syntax'):
            mode = 'syntax'
            continue
        if line == '':
            continue

        if mode == 'syntax':
            cur.commands.append(line)
        if mode == 'parameter':
            # cur.parameters.append(line)
            if len(cur.commands):
                if len(cur.commands) == len(cur.parameters) and len(cur.parameters):
                    cur.parameters[list(cur.parameters.keys())[-1]] += line

                else:
                    if line in cur.commands[len(cur.parameters)]:
                        cur.parameters[line] = ''
                    else:
                        if len(cur.parameters):
                            cur.parameters[list(cur.parameters.keys())[-1]] += line
        if mode == 'feedback':
            cur.outputs += line
        if mode == 'one element complete':
            result.append(cur)
            cur = APIEndpoint()
            mode = 'none'

    # print(result)
    return result

def to_json(api_endpoints):

    return json.dumps([dataclasses.asdict(a) for a in api_endpoints], indent=2)

def run(pdf_filename: str):
    abs_filepath = os.path.join(os.path.dirname(__file__), pdf_filename)
    content = subprocess.check_output(['pdftotext', abs_filepath, '-'], encoding='utf-8')
    # print(content)
    print(to_json(parse(content)))
    return parse(content)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        content = run(sys.argv[1])
        print(to_json(content))
