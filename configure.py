#!/usr/bin/env python3
"""Bind a local config to an existing ChatGPT login, without copying tokens."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def configuration(template, auth, codex, codex_home, child_path, model=None):
    account_id = (auth.get('tokens') or {}).get('account_id')
    if not account_id or auth.get('OPENAI_API_KEY'):
        raise ValueError('An existing Codex ChatGPT login is required; run codex login first.')
    config = dict(template)
    if model:
        config['model'] = model
    config.update(codex=str(codex), codex_home=str(codex_home), child_path=child_path,
                  account_fingerprint=hashlib.sha256(account_id.encode()).hexdigest())
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', help='A model supported by this account in Codex CLI')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser().resolve()
    codex = shutil.which('codex')
    if not codex:
        raise SystemExit('Codex CLI was not found in PATH.')
    try:
        auth = json.loads((home / 'auth.json').read_text())
        template = json.loads((source / 'config.example.json').read_text())
        # Preserve local scheduling/model choices when explicitly reconfiguring.
        previous = source / 'config.json'
        if previous.exists():
            previous_config = json.loads(previous.read_text())
            for key in ('times', 'timezone', 'catchup_minutes', 'model'):
                if key in previous_config:
                    template[key] = previous_config[key]
        node = shutil.which('node')
        node_dirs = [str(Path(node).parent)] if node else []
        # Versioned Homebrew Node is commonly not on the interactive PATH.
        for directory in ('/opt/homebrew/opt/node@20/bin', '/opt/homebrew/bin',
                          '/usr/local/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin'):
            if directory not in node_dirs:
                node_dirs.append(directory)
        child_path = ':'.join(node_dirs)
        config = configuration(template, auth, codex, home, child_path, args.model)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
    os.umask(0o077)
    destination = source / 'config.json'
    destination.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    destination.chmod(0o600)
    print('Saved local configuration:', destination)
    print('Model:', config['model'])
    print('Times:', ', '.join(config['times']))
    print('Credentials stay in the original Codex login file.')


if __name__ == '__main__':
    main()
