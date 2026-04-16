"""
config.py - Yapilandirma (v2 - otomatik kalibrasyon)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_CONTENT_LENGTH = 50 * 1024 * 1024
SECRET_KEY = os.environ.get("SECRET_KEY", "omr-scanner-key")

# Form yapisi varsayilanlari
DEFAULT_NUM_QUESTIONS = 200
DEFAULT_NUM_CHOICES = 5
DEFAULT_ROWS_PER_COLUMN = 30
CHOICE_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"]

# Goruntu olcekleme (cok yuksek cozunurlukleri kuculterek tutarlilik saglar)
# Goruntu olceklemesi:
# - TARGET_IMAGE_DIM'den kucukse (telefon fotosu gibi): buyut
# - MAX_IMAGE_DIM'den buyukse: kucult
# Hough parametreleri bu aralik icin ayarli.
TARGET_IMAGE_DIM = 3000  # En kisa kenar (h veya w). Kucuk goruntuyu bu boyuta buyut.
MAX_IMAGE_DIM = 4000     # A4 300dpi (3507px) downscale edilmesin

# Hough Circle parametreleri (A4 300dpi tarama icin)
HOUGH_DP = 1
HOUGH_MIN_DIST = 20   # Baloncuklar ~50px aralikli, 20 guvenli
HOUGH_PARAM1 = 50
HOUGH_PARAM2 = 25     # 20'den 25'e: yanlis daire sayisi azalir
HOUGH_MIN_RADIUS = 10 # 300dpi'da baloncuk yaricapi ~14
HOUGH_MAX_RADIUS = 18

# Isaretleme esikleri (ISTATISTIKSEL)
# En koyu baloncuk, diger 4 baloncugun ortalamasindan:
#   - en az MARK_MIN_DIFF birim koyu olmali
#   - en az MARK_Z_MIN standart sapma uzaklikta olmali
#   - kendisi MARK_MAX_DARKEST'in altinda olmali (cok acik olmasin)
MARK_MAX_DARKEST = 220   # En koyu baloncuk bu degerin ustundeyse hicbir zaman isaretli sayilmaz
MARK_MIN_DIFF = 13       # Diger 4 sikkin ortalamasina gore en az bu kadar daha koyu olmali
MARK_Z_MIN = 2.0         # Z-score: en az 2 std sapma (istatistiksel anlamli)
DOUBLE_MARK_TOLERANCE = 15   # Ikinci isareti kabul icin koyuluk farki

# ESKI PARAMETRELER (geriye donuk uyumluluk icin saklanir ama istatistiksel sisteme kullanilmaz):
FILL_THRESHOLD = 170
FILL_RELATIVE_RATIO = 0.85
FILL_CONTRAST_MIN = 25

# Kume toleranslari (ayni sutun/satir kabul edilecek piksel farki)
X_GROUP_GAP_MULTIPLIER = 1.6  # Soru gruplari arasi bosluk / medyan bosluk
Y_CLUSTER_TOLERANCE = 12
X_CLUSTER_TOLERANCE = 15

# PDF destegi
PDF_DPI = 300  # PDF sayfasini bu DPI'da goruntuye cevir.
               # 300 = tarayici kalitesi (onerilen), dogru okuma garantilemek icin.
               # 200 daha hizli ama ad-soyad/numara okumada sapma olabilir.

TURKISH_ALPHA = [
    " ", "A", "B", "C", "Ç", "D", "E", "F", "G", "Ğ", "H",
    "I", "İ", "J", "K", "L", "M", "N", "O", "Ö", "P", "Q", "R",
    "S", "Ş", "T", "U", "Ü", "V", "W", "X", "Y", "Z"
]
