from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
STAGE1_SCRIPT = SCRIPT_DIR / "stage1.py"
STAGE2_SCRIPT = SCRIPT_DIR / "stage2.py"
STAGE4_SCRIPT = SCRIPT_DIR / "stage4.py"
STAGE5_SCRIPT = SCRIPT_DIR / "stage5.py"
STAGE6_SCRIPT = SCRIPT_DIR / "stage6.py"
STAGE7_SCRIPT = SCRIPT_DIR / "stage7.py"
E2E_SCRIPT = SCRIPT_DIR / "e2e_mvp.py"
PENDING_STAGE_SCRIPTS = [
    SCRIPT_DIR / "stage3.py",
]


def main() -> None:
    subprocess.run([sys.executable, str(STAGE1_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(STAGE2_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(STAGE4_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(STAGE5_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(STAGE6_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(STAGE7_SCRIPT)], check=True)
    subprocess.run([sys.executable, str(E2E_SCRIPT)], check=True)

    print("Pending stage validation scripts:")
    for script in PENDING_STAGE_SCRIPTS:
        print(f"- TODO {script.name}")


if __name__ == "__main__":
    main()
