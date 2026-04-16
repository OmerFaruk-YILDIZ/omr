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


TARGET_IMAGE_DIM = 3000  
MAX_IMAGE_DIM = 4000     


HOUGH_DP = 1
HOUGH_MIN_DIST = 20   
HOUGH_PARAM1 = 50
HOUGH_PARAM2 = 25    
HOUGH_MIN_RADIUS = 10 
HOUGH_MAX_RADIUS = 18


MARK_MAX_DARKEST = 220   
MARK_MIN_DIFF = 13     
MARK_Z_MIN = 2.0       
DOUBLE_MARK_TOLERANCE = 15   


FILL_THRESHOLD = 170
FILL_RELATIVE_RATIO = 0.85
FILL_CONTRAST_MIN = 25


X_GROUP_GAP_MULTIPLIER = 1.6  
Y_CLUSTER_TOLERANCE = 12
X_CLUSTER_TOLERANCE = 15

TURKISH_ALPHA = [
    " ", "A", "B", "C", "Ç", "D", "E", "F", "G", "Ğ", "H",
    "I", "İ", "J", "K", "L", "M", "N", "O", "Ö", "P", "Q", "R",
    "S", "Ş", "T", "U", "Ü", "V", "W", "X", "Y", "Z"
]
