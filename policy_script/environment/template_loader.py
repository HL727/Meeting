import re


def rewrite_template(content: str):
    result = []

    if '{%' in content or '{{' in content:
        return content

    for line in content.split('\n'):

        statement = (re.split(r'[\s()\[\]:/+-]', line.strip()) or [''])[0]

        if not line.strip() or statement in '{%':
            result.append(line)
            continue

        if statement in (
            'for',
            'if',
            'with',
            'do',
            'while',
            'endfor',
            'endif',
            'endwith',
            'endwhile',
        ):
            line = '% {}'.format(line.strip())
        elif statement.replace('_', 'A').isalpha():
            line = '% do ' + line

        result.append(line)

    return '\n'.join(result)
