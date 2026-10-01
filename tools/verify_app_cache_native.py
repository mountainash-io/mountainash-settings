"""One-off verification runner; reuse artifacts from native run 36805956372."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def run(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs)


repository = Path(__file__).resolve().parents[1]
root = Path(os.environ['RUNNER_TEMP'])
existing = root / 'existing-native-proof'
output = root / 'app-cache-proof'
output.mkdir()
receipt = json.loads((existing / 'proof.json').read_text())
assert receipt['status'] == 'passed'
assert receipt['source_revision'] == '16a5ea3cab257432145d81711ff6cc79307a9f69'
copied = root / 'app-cache-work'
shutil.copytree(repository / 'tests', copied / 'tests')
env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'PYTHONHOME'}}
report = {'source_revision': run(['git', 'rev-parse', 'HEAD'], cwd=repository).strip(),
          'artifact_source_revision': receipt['source_revision'],
          'artifact_run': 36805956372, 'python': sys.version, 'installed': []}
try:
    for kind in ('wheel', 'sdist-wheel'):
        wheel, = (existing / kind).glob('*.whl')
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert digest == receipt['artifacts'][kind]['sha256']
        venv = root / ('app-cache-' + kind)
        run([sys.executable, '-I', '-m', 'venv', str(venv)])
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        run([str(python), '-I', '-m', 'pip', 'install', str(wheel),
             'pytest==8.3.5', 'pytest-check==2.5.3'])
        run([str(python), '-I', '-m', 'pip', 'check'])
        probe = json.loads(run([str(python), '-I', '-c',
            'import json,sys,mountainash_settings;print(json.dumps(dict(prefix=sys.prefix,file=mountainash_settings.__file__)))'], cwd=copied, env=env))
        assert Path(probe['file']).is_relative_to(venv)
        junit = output / (kind + '.xml')
        result = subprocess.run([str(python), '-I', '-m', 'pytest', '--import-mode=importlib',
            '--confcutdir=' + str(copied / 'tests'), '--junitxml=' + str(junit), '-q',
            str(copied / 'tests/settings/app'), str(copied / 'tests/settings_cache')],
            cwd=copied, env=env, text=True, capture_output=True)
        (output / (kind + '.log')).write_text(result.stdout + result.stderr)
        cases = list(ET.parse(junit).iter('testcase'))
        skips = [c.attrib for c in cases if c.find('skipped') is not None]
        failures = [c.attrib for c in cases if c.find('failure') is not None or c.find('error') is not None]
        report['installed'].append(dict(kind=kind, sha256=digest, probe=probe,
            cases=len(cases), skips=skips, failures=failures, exit_code=result.returncode))
        print(result.stdout, flush=True)
        assert result.returncode == 0 and not failures
        assert len(cases) >= 100
        assert all(os.name == 'nt' and 'fork' in c['name'] for c in skips), skips
    report['status'] = 'passed'
finally:
    (output / 'receipt.json').write_text(json.dumps(report, indent=2))
