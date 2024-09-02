from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJ_ROOT / "data"
PARAMS_DIR = PROJ_ROOT / "params"
MODELS_DIR = PROJ_ROOT / "models"
DATA_FILEPATH = "C:/Users/jrnas/Downloads/ZGMH_NHL_2023_playoffs_Round_1.json"

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

except ModuleNotFoundError:
    pass

