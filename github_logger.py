import subprocess
import os
import logging
from datetime import datetime
import pytz

log = logging.getLogger(__name__)
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
ET = pytz.timezone("America/New_York")


def git_push():
    """Commit portfolio.json and trade_log.json then push to GitHub."""
    try:
        timestamp = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

        subprocess.run(
            ["git", "add", "portfolio.json", "trade_log.json"],
            cwd=REPO_PATH, check=True, capture_output=True
        )

        # Only commit if there are staged changes
        check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_PATH, capture_output=True
        )
        if check.returncode == 0:
            log.debug("No changes to commit")
            return

        subprocess.run(
            ["git", "commit", "-m", f"bot: update trades {timestamp}"],
            cwd=REPO_PATH, check=True, capture_output=True
        )

        subprocess.run(
            ["git", "push"],
            cwd=REPO_PATH, check=True, capture_output=True
        )

        log.info("Pushed to GitHub")

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        log.error(f"Git error: {stderr}")
