# type: ignore
from __future__ import annotations

import os
import re

import django

# file: noqa

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conferencecenter.settings")
django.setup()


from django.utils.translation.trans_real import _translations, activate, DjangoTranslation


class LanguageSwitcher:
    def __init__(self, target_lang='en'):
        activate('en')
        self.lang: DjangoTranslation = _translations['en']
        self.all_keys = self.load_strings()
        self.keys_by_length = sorted(self.all_keys.keys(), key=lambda k: len(k), reverse=True)
        IGNORE = {
            'e',
            'sip',
            'SIP',
            'GET',
            'POST',
            'PUT',
            'cospace',
            'Sparc',
            'HTTP',
            'HTTPS',
            'filter',
            'H323',
        }

        self.replace = [
            (
                self.compile_re_key(k),
                self.compile_re_value(self.all_keys[k]),
                self.get_longest_words(k),
            )
            for k in self.keys_by_length
            if k not in IGNORE
        ]

    def load_strings(self):
        all_keys = {}

        for key, value in self.lang._catalog.items():
            if key == '':
                continue

            if isinstance(key, tuple):
                if key[0] not in all_keys:
                    all_keys[key[0]] = value
            else:
                all_keys[key] = value

        return all_keys

    def compile_re_key(self, value: str):
        escaped = re.escape(value.strip('\'"'))
        result = (
            '((\(["\']|>|\', \')[ \n\t]*)'
            + re.sub(r'\\[ \n\t]', r'[ \\n\\t]+', escaped)
            + '([ \n]*["<\'])'
        )
        return re.compile(result)

    def compile_re_value(self, value: str):
        result = value.replace('\\', '\\\\').replace('\'', '\\\'')
        return r'\g<1>' + result + r'\g<3>'

    def get_longest_words(self, value: str):
        """Speed up re.sub. Ignore if word is not included"""
        return sorted(value.split(), key=lambda v: len(v), reverse=True)[:5]

    def switch_language(self, directory='.'):

        for filename in self.iter_filenames(directory):
            self.handle_file(filename)

    def iter_filenames(self, directory='.'):

        for root, _dirs, files in os.walk(directory):
            if 'node_modules' in root:
                continue
            if 'lib/python' in root:
                continue
            if 'site_media/' in root:
                continue
            if 'static/dist' in root:
                continue
            if '.git' in root:
                continue

            for f in files:
                if '.min.js' in f:
                    continue

                if f.rsplit('.', 1)[-1] not in ('py', 'html', 'vue', 'js', 'ts'):
                    continue

                yield os.path.join(root, f)

    def handle_file(self, filename):
        with open(filename) as fd:
            content, changed = self.reverse_translations(fd.read())

        if changed:
            with open(filename, 'w') as fd:
                fd.write(content)
            print(filename)

    def reverse_translations(self, content):
        initial = content
        for sub, value, haystack in self.replace:
            if all(h in content for h in haystack):
                content = sub.sub(value, content)

        return content, content != initial


LanguageSwitcher('en').switch_language()
