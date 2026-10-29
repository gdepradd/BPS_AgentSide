import sys
from pathlib import Path

# Tambahkan project root ke sys.path agar bps_mcp bisa diimport oleh pytest
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT)) 
    
import re
from pathlib import Path
import pytest
from dotenv import dotenv_values

def _swap_db(url: str, db: str) -> str:
    return re.sub(r"/[^/]+$", f"/{db}", url)

@pytest.fixture(scope="session")
def urls():
    values = dotenv_values(Path.cwd() / ".env")
    admin = _swap_db(values["DB_ADMIN_URL"],   "bps_agent_test")
    ro    = _swap_db(values["DB_AGENT_RO_URL"], "bps_agent_test")
    return {"admin": admin, "ro": ro}