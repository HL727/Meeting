from typing import List

from endpoint.types import CommandDict, ConfigurationDict, XAPIParseDict


class XAPICommandParser:

    def __init__(self, text: str):
        self.text = text
        self.pending_argument_key = None
        self.line_number = 0

    def parse(self) -> XAPIParseDict:
        commands: List[CommandDict] = []
        configuration: List[ConfigurationDict] = []

        result = XAPIParseDict(commands=commands, configuration=configuration)

        self.pending_argument_key = None
        self.line_number = 0

        last_type = None

        lines = self.text.split('\n')

        while lines:
            line = lines.pop(0)

            self.line_number += 1

            line = line.lstrip(' ')
            if line.split(' ', 1)[0].lower() not in ('xconfiguration', 'xcommand'):

                if last_type == 'xcommand':
                    if self._extend_command_arguments(line, commands[-1]):
                        continue

                    multiline_body, is_multiline = self._get_multiline_body([line] + lines)
                    self.line_number += len(multiline_body) - 1
                    lines = lines[len(multiline_body) - 1:]
                    if is_multiline:
                        commands[-1]['arguments'].setdefault('body', []).extend(multiline_body[:-1])
                    self.last_type = None
                continue

            cur_type, key, arguments = self._parse_line(line)
            if cur_type.lower() == 'xconfiguration':
                configuration.append({'key': key, 'value': arguments})
            else:
                commands.append({'command': key, 'arguments': arguments})

            last_type = cur_type

        for command in commands:
            if 'body' in command['arguments']:
                command['arguments']['body'] = ['\n'.join(command['arguments']['body'])]
        return result

    def _parse_line(self, line):
        import shlex
        cur_type, *parts = shlex.split(line, comments=True, posix=False)

        result, arguments = self._parse_parts(parts)

        if cur_type.lower() == 'xconfiguration':
            if arguments:
                result.append(list(arguments.keys())[0])
                arguments = list(arguments.values())[0][0]

        return cur_type.lower(), result, arguments

    def _parse_parts(self, parts):
        result = []
        arguments = {}

        arg = self.pending_argument_key
        while parts:
            cur = parts.pop(0)
            if arg:
                arguments.setdefault(arg, []).append(cur)
                arg = None
                continue

            if cur.isdigit() and not arguments and result and not arg:  # item="1"-index
                if '[' not in result[-1]:
                    result.append('{}[{}]'.format(result.pop(), cur))
                    continue

            if ':' not in cur:
                result.append(cur)
                continue

            # argument key:
            if cur == ':':
                arg = result.pop()
                continue
            elif cur.index(':') != len(cur) - 1:
                arg, defer = cur.split(':', 1)
                parts.insert(0, defer)
            else:
                arg = cur.rstrip(': ')

        self.pending_argument_key = arg
        return result, arguments

    def _extend_command_arguments(self, line, command):
        import shlex
        parts = shlex.split(line, comments=True, posix=False)

        result, arguments = self._parse_parts(parts)

        if not (arguments and not result):
            return False

        for k, v in arguments.items():
            command['arguments'].setdefault(k, []).extend(v)
        return True

    def _get_multiline_body(self, lines):

        non_empty_lines = []

        i = -1
        for line in lines:
            i += 1

            if line.strip() == '.':
                return lines[:i + 1], True

            if line.strip().startswith('#'):
                continue

            if line.strip().split(' ', 1)[0].lower() in ('xcommand', 'xconfiguration'):
                i = max(0, i - 1)
                break

            if line.strip():
                non_empty_lines.append(line)

        if non_empty_lines:
            raise ValueError('Parse error on line {}: {}'.format(self.line_number + i, lines[i]))

        return lines[:i + 1], False
