"""
config.py - Yapilandirma
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_CONTENT_LENGTH = 50 * 1024 * 1024
SECRET_KEY = os.environ.get("SECRET_KEY", "omr-scanner-key")

DEFAULT_NUM_QUESTIONS = 200
DEFAULT_NUM_CHOICES = 5
DEFAULT_ROWS_PER_COLUMN = 30
CHOICE_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"]

MAX_IMAGE_DIM = 1800

HOUGH_DP = 1
HOUGH_MIN_DIST = 12
HOUGH_PARAM1 = 50
HOUGH_PARAM2 = 20
HOUGH_MIN_RADIUS = 5
HOUGH_MAX_RADIUS = 15

FILL_THRESHOLD = 200

X_GROUP_GAP_MULTIPLIER = 1.8
Y_CLUSTER_TOLERANCE = 8
X_CLUSTER_TOLERANCE = 8

TURKISH_ALPHA = [
    " ", "A", "B", "C", "Ç", "D", "E", "F", "G", "Ğ", "H",
    "I", "İ", "J", "K", "L", "M", "N", "O", "Ö", "P", "Q", "R",
    "S", "Ş", "T", "U", "Ü", "V", "W", "X", "Y", "Z"
]
