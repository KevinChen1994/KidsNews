#!/usr/bin/env python3
"""Render a public script template into a private, final TTS transcript, offline."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'\{\{\s*([a-z_]+)\s*\}\}')


def load_profile(root=ROOT):
    """Use generic defaults; personal overrides never belong in the repository."""
    profile = json.loads((root / 'config/local.example.json').read_text(encoding='utf-8'))
    local = root / 'config/local.json'
    if local.exists():
        overrides = json.loads(local.read_text(encoding='utf-8'))
        if not isinstance(overrides, dict):
            raise ValueError('Local configuration must be a JSON object')
        for key, value in overrides.items():
            if key == 'delivery' and isinstance(value, dict):
                profile[key] = dict(profile[key], **value)
            else:
                profile[key] = value
    for key in ('program_name', 'listener_name', 'audience_age', 'listening_context'):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError(f'Configuration requires a non-empty string: {key}')
    if not isinstance(profile.get('interests'), list) or not all(
            isinstance(item, str) for item in profile['interests']):
        raise ValueError('Configuration interests must be a list of strings')
    if not isinstance(profile.get('delivery'), dict):
        raise ValueError('Configuration delivery must be an object')
    return profile


def render_script(template, profile):
    values = {key: profile[key] for key in (
        'program_name', 'listener_name', 'audience_age', 'listening_context')}
    values['interests'] = '、'.join(profile['interests'])

    def replace(match):
        if match[1] not in values:
            raise ValueError(f'Unknown script placeholder: {match[1]}')
        return values[match[1]]

    rendered = TOKEN.sub(replace, template)
    if '{{' in rendered or '}}' in rendered:
        raise ValueError('Unresolved script placeholder')
    return rendered


def prepare(template, output, root=ROOT):
    output = Path(output).resolve()
    # Resolve symlinks too, so personal text cannot escape the ignored folders.
    if root.resolve() not in output.parents or not any(root / folder in output.parents
               for folder in ('episodes', 'samples', 'delivery', 'private')):
        raise ValueError('Rendered scripts must be inside episodes/, samples/, delivery/ or private/')
    rendered = render_script(Path(template).read_text(encoding='utf-8'), load_profile(root))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never silently change a transcript that may already have paid audio cached.
    with output.open('x', encoding='utf-8') as handle:
        handle.write(rendered)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        output = prepare(args.template, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(f'Saved: {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
