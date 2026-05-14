import os
import shutil
import subprocess
import logging
from pathlib import Path
import sys

# Ensure backend is in path
sys.path.append(str(Path(__file__).parent.parent))

from ingest_all import main as run_ingestion_logic

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-7s | %(message)s')
logger = logging.getLogger("sync_and_ingest")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp_repos"

REPOS = {
    "selenium": "https://github.com/PramodDutta/ATB14xSeleniumAdvanceFrameworks",
    "playwright": "https://github.com/PramodDutta/Advance-Playwright-Framework",
    "blueprint": "https://github.com/PramodDutta/AITesterBlueprint2x"
}

def run_git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)

import stat

def on_rm_error(func, path, exc_info):
    # path contains the name of the file that caused the error
    # func is the function that caused the error (os.remove or os.rmdir)
    # exc_info is the tuple returned by sys.exc_info()
    os.chmod(path, stat.S_IWRITE)
    func(path)

def sync_repos():
    logger.info("Cleaning up old data and temp files...")
    if DATA_DIR.exists():
        # Keep the directory but clear contents to avoid git issues if it's a repo
        for item in DATA_DIR.iterdir():
            if item.is_dir(): shutil.rmtree(item, onerror=on_rm_error)
            else: item.unlink()
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, onerror=on_rm_error)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Sync Blueprint Data (Subdirectory)
    logger.info(f"Cloning {REPOS['blueprint']} (sparse)...")
    blueprint_path = TEMP_DIR / "blueprint"
    run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse", REPOS['blueprint'], str(blueprint_path)])
    run_git(["sparse-checkout", "set", "Chapter_09_Project_QACopilot/data"], cwd=str(blueprint_path))
    
    src_data = blueprint_path / "Chapter_09_Project_QACopilot" / "data"
    if src_data.exists():
        for item in src_data.iterdir():
            dest = DATA_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        logger.info("Blueprint data synced.")
    else:
        logger.error("Could not find blueprint data directory!")

    # 2. Sync Selenium Repo
    logger.info(f"Cloning Selenium repo...")
    sel_dest = DATA_DIR / "selenium_repo"
    run_git(["clone", "--depth", "1", REPOS['selenium'], str(sel_dest)])
    logger.info("Selenium repo synced.")

    # 3. Sync Playwright Repo
    logger.info(f"Cloning Playwright repo...")
    pw_dest = DATA_DIR / "playwright_repo"
    run_git(["clone", "--depth", "1", REPOS['playwright'], str(pw_dest)])
    logger.info("Playwright repo synced.")

    # Cleanup temp
    shutil.rmtree(TEMP_DIR, onerror=on_rm_error)
    logger.info("Sync complete.")

def main():
    try:
        sync_repos()
        logger.info("Starting ingestion...")
        run_ingestion_logic()
        logger.info("Sync and Ingest finished.")
    except Exception as e:
        logger.error(f"Sync/Ingest failed: {e}")

if __name__ == "__main__":
    main()
