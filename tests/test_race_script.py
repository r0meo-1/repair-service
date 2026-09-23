import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="Bash harness runs in Linux CI")
@pytest.mark.parametrize("mode,expected", [("one", 0), ("all", 1), ("denied", 1)])
def test_race_script_requires_one_winner(tmp_path, mode, expected):
    # Replace curl with an offline stub; no network or credentials are used.
    curl = tmp_path / "curl"
    curl.write_text(
        '#!/usr/bin/env bash\n'
        'case "$RACE_MODE" in\n'
        '  all) printf 200;;\n'
        '  denied) printf 403;;\n'
        '  one) if mkdir "$RACE_LOCK" 2>/dev/null; then printf 200; else printf 409; fi;;\n'
        'esac\n', encoding="utf-8",
    )
    curl.chmod(0o700)
    cookies = tmp_path / "session.cookies"
    cookies.touch()
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
               RACE_MODE=mode, RACE_LOCK=str(tmp_path / "winner"))
    script = Path(__file__).resolve().parents[1] / "race_test.sh"
    result = subprocess.run(["bash", str(script), "1", str(cookies)], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == expected, result.stdout + result.stderr
