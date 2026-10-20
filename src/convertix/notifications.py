import logging
import shutil
import subprocess


def notify(summary: str, body: str, enabled: bool) -> bool:
    if not enabled or not shutil.which("notify-send"):
        return False
    try:
        p = subprocess.run(["notify-send", "--app-name=Convertix", "--icon=document-export",
                            "--", summary, body], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=4)
        if p.returncode:
            logging.getLogger("convertix").warning("notification_failed %s", p.stderr.decode(errors="replace")[:500])
        return p.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as e:
        logging.getLogger("convertix").warning("notification_failed %s", e)
        return False

