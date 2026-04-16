"""
omr_engine.py - Otomatik Kalibrasyonlu OMR Motoru (v4)
============================================================
Duzeltmeler:
- Y grid offset hatasi giderildi (ilk satir artik dogru)
- Fazla tespit edilen satirlar trim'leniyor (31 -> 30)
- Ad-soyad bolgesi daraltildi (spiral/baslik gurultusu haric)
- Numara bolgesi 10 sutuna ekstrapole edilir
- Dinamik kontrast (golge/matbaa izi reddi)
- Coklu isaret tespiti (cift sik)
- ISTATISTIKSEL isaret tespiti (z-score tabanli)
- PDF destegi (cok sayfali PDF'leri otomatik ayiklar)
"""
import cv2
import numpy as np
import base64
import config as cfg

# PDF destegi (opsiyonel)
try:
    import fitz  # PyMuPDF
    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False


# ============================================================
# DOSYA DECODE (JPG/PNG/PDF)
# ============================================================

def is_pdf_bytes(data):
    """Byte dizisi PDF mi? Magic bytes kontrolu: %PDF"""
    return len(data) >= 4 and data[:4] == b"%PDF"


def pdf_to_images(pdf_bytes, dpi=None):
    """
    PDF'i sayfa basina bir OpenCV BGR goruntuye cevir.
    Stratejі:
      1) Sayfada tek bir gomulu TAM SAYFA resim varsa (tarayici/fotograf PDF'i),
         onu KAYIPSIZ olarak cikar (yeniden render etme).
      2) Aksi takdirde sayfayi istenen DPI'da render et (metin/vektorel icerik).
    dpi: render fallback'i icin cozunurluk (varsayilan cfg.PDF_DPI).
    """
    if not _HAS_PDF:
        raise RuntimeError(
            "PDF okuma icin PyMuPDF gerekli. Kurulum: pip install PyMuPDF"
        )
    if dpi is None:
        dpi = getattr(cfg, "PDF_DPI", 300)

    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            img_array = _extract_embedded_image(doc, page)
            if img_array is None:
                img_array = _render_page(page, dpi)
            images.append(img_array)
    finally:
        doc.close()
    return images


def _extract_embedded_image(doc, page):
    """
    Sayfada tek bir buyuk (tam sayfa) gomulu resim varsa, onu kayipsiz cikar.
    Aksi takdirde None doner.
    """
    img_list = page.get_images(full=True)
    if len(img_list) != 1:
        return None  # cok resim ya da hic resim yok -> render'a dus

    xref = img_list[0][0]
    try:
        base_image = doc.extract_image(xref)
        img_bytes = base_image["image"]
        # Byte dizisini OpenCV'ye cevir
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        # Gomulu resim cok kucukse (kupartilmis mini ikon gibi), render'a dus
        if min(img.shape[:2]) < 500:
            return None
        return img
    except Exception:
        return None


def _render_page(page, dpi):
    """Sayfayi verilen DPI'da raster'a cevir."""
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_array = np.frombuffer(pix.samples, dtype=np.uint8)
    img_array = img_array.reshape(pix.height, pix.width, pix.n)
    if pix.n == 3:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    return img_array


def decode_to_images(file_bytes):
    """
    Yuklenen dosyayi (JPG/PNG/PDF) bir VEYA birden fazla OpenCV goruntuye cevir.
    PDF ise her sayfa ayri bir goruntu olur.
    Donus: liste of numpy arraylar (coklu sayfa icin birden fazla).
    """
    if is_pdf_bytes(file_bytes):
        return pdf_to_images(file_bytes)
    # Normal resim
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []
    return [img]


# ============================================================
# YARDIMCI FONKSIYONLAR
# ============================================================

def cluster_values(values, tolerance):
    if not values:
        return []
    values = sorted(values)
    groups, current = [], [values[0]]
    for v in values[1:]:
        if v - current[-1] <= tolerance:
            current.append(v)
        else:
            groups.append(int(np.mean(current)))
            current = [v]
    groups.append(int(np.mean(current)))
    return groups


def measure_bubble(gray, cx, cy, radius):
    """
    Baloncugun ortalama parlaklik degerini dondur (0=siyah, 255=beyaz).
    Kenara yakin baloncuklar icin: mask'i goruntu sinirina kirp, yine de olc.
    (Eskiden 255 donduruyordu -> ilk/son satiri kaybediyorduk)
    """
    r = max(3, int(radius) - 3)
    h, w = gray.shape[:2]
    cx, cy = int(cx), int(cy)
    # Tamamen disarida mi?
    if cy + r < 0 or cy - r >= h or cx + r < 0 or cx - r >= w:
        return 255.0
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    # cv2.circle kendiligiinden goruntu sinirina klip yapar
    total = int(mask.sum() / 255)  # daire icindeki piksel sayisi
    if total < 1:
        return 255.0
    return float(cv2.mean(gray, mask=mask)[0])


def is_marked_dynamic(measurements, threshold_val=None, contrast_min=None):
    """
    Istatistiksel isaretleme tespiti.
    En koyu baloncuk, diger baloncuklarin ortalamasindan:
      1) Mutlak: en az MARK_MIN_DIFF birim koyuysa VE
      2) Goreli: en az MARK_Z_MIN standart sapma uzaklikta ise VE
      3) Mutlak olarak MARK_MAX_DARKEST'in altindaysa (cok acik olmasin)
    isaretli sayilir.

    Bu yaklasim, farkli isik kosullarinda (soluk telefon fotosu, koyu tarayici)
    ayni mantikla calisir cunku diger 4 baloncuk 'beyaz referans' gorevi gorur.
    """
    if not measurements:
        return None, None
    sorted_m = sorted(measurements, key=lambda x: x[1])
    darkest_idx, darkest_val = sorted_m[0]

    # Diger baloncuklari referans olarak al
    others = [m[1] for m in sorted_m[1:]]
    if not others:
        return None, None
    others_mean = float(np.mean(others))
    others_std = float(np.std(others))

    abs_diff = others_mean - darkest_val
    z_distance = abs_diff / max(others_std, 1.0)

    if darkest_val < cfg.MARK_MAX_DARKEST \
       and abs_diff > cfg.MARK_MIN_DIFF \
       and z_distance > cfg.MARK_Z_MIN:
        return darkest_idx, darkest_val
    return None, None


# ============================================================
# OTOMATIK KALIBRASYON
# ============================================================

def detect_answer_bar_y(img):
    """Turuncu CEVAPLAR banti. Bar bitimi + 10px dondurur."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, (5, 100, 100), (25, 255, 255))
    row_sums = orange.sum(axis=1)
    threshold = w * 0.3 * 255
    candidates = np.where(row_sums > threshold)[0]
    if len(candidates) == 0:
        return int(h * 0.55)
    return int(candidates.max()) + 10


def resize_if_needed(img, target_dim=None, max_dim=None):
    """
    Goruntuyu standart bir boyuta normalize et:
    - Cok kucukse (<TARGET_IMAGE_DIM) buyut
    - Cok buyukse (>MAX_IMAGE_DIM) kucult
    - Arada ise dokunma
    Bu, Hough parametrelerinin tutarli sekilde calismasini saglar.
    """
    if target_dim is None:
        target_dim = cfg.TARGET_IMAGE_DIM
    if max_dim is None:
        max_dim = cfg.MAX_IMAGE_DIM
    h, w = img.shape[:2]
    longest = max(h, w)

    if longest < target_dim:
        # Kucukse buyut (WhatsApp telefon fotosu gibi)
        scale = target_dim / longest
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC), scale
    elif longest > max_dim:
        # Cok buyukse kucult
        scale = max_dim / longest
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA), scale
    return img, 1.0


def find_question_groups(x_columns, num_choices, gap_multiplier=None):
    if gap_multiplier is None:
        gap_multiplier = cfg.X_GROUP_GAP_MULTIPLIER
    if len(x_columns) < num_choices:
        return []
    gaps = [x_columns[i + 1] - x_columns[i] for i in range(len(x_columns) - 1)]
    if not gaps:
        return [x_columns]
    median_gap = float(np.median(gaps))
    threshold = median_gap * gap_multiplier
    groups, current = [], [x_columns[0]]
    for i, gap in enumerate(gaps):
        if gap > threshold:
            groups.append(current)
            current = [x_columns[i + 1]]
        else:
            current.append(x_columns[i + 1])
    groups.append(current)
    return groups


def build_uniform_grid(values, expected_count, trim_outliers=True):
    """
    Duzgun araliklarla expected_count uzunlugunda izgara uret.
    KRITIK: Ilk dairenin GERCEK merkezinden baslar (medyan degil).
    trim_outliers=True: fazla tespit edilen satirlari outlier kontrolu ile eler.
    """
    if len(values) < 2:
        return list(values) + [0] * max(0, expected_count - len(values))

    values = sorted(values)

    diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
    median_gap = float(np.median(diffs))

    if trim_outliers and len(values) > expected_count:
        while len(values) > expected_count:
            first_gap = values[1] - values[0]
            last_gap = values[-1] - values[-2]
            if first_gap > median_gap * 1.5 and first_gap >= last_gap:
                values = values[1:]
            elif last_gap > median_gap * 1.5:
                values = values[:-1]
            else:
                values = values[:-1]

    y_start = values[0]
    if len(values) >= 2:
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        median_gap = float(np.median(diffs))

    return [int(round(y_start + i * median_gap)) for i in range(expected_count)]


def extend_to_expected_count(values, expected_count):
    """Eksik sutunlari medyan araliga gore sondan ekstrapole et."""
    if len(values) >= expected_count:
        return values[:expected_count]
    if len(values) < 2:
        return values
    diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
    median_gap = float(np.median(diffs))
    result = list(values)
    while len(result) < expected_count:
        result.append(int(round(result[-1] + median_gap)))
    return result


# ============================================================
# CEVAPLARI OKUMA
# ============================================================

def read_answers_section(gray, num_questions, num_choices, rows_per_col):
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=cfg.HOUGH_DP,
        minDist=cfg.HOUGH_MIN_DIST, param1=cfg.HOUGH_PARAM1, param2=cfg.HOUGH_PARAM2,
        minRadius=cfg.HOUGH_MIN_RADIUS, maxRadius=cfg.HOUGH_MAX_RADIUS,
    )
    if circles is None:
        return [], "Cevap bolumunde daire bulunamadi"

    circles = np.round(circles[0]).astype(int)
    median_radius = int(np.median(circles[:, 2]))

    x_cols = cluster_values(circles[:, 0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    y_rows = cluster_values(circles[:, 1].tolist(), cfg.Y_CLUSTER_TOLERANCE)

    if not x_cols or not y_rows:
        return [], "Izgara olusturulamadi"

    groups = find_question_groups(x_cols, num_choices)
    if not groups:
        return [], "Soru gruplari tespit edilemedi"

    y_grid = build_uniform_grid(y_rows, rows_per_col, trim_outliers=True)

    answers = []
    for q in range(num_questions):
        col_idx = q // rows_per_col
        row_idx = q % rows_per_col

        if col_idx >= len(groups):
            answers.append({"question": q + 1, "answer": "BLANK"})
            continue

        group = groups[col_idx]
        if len(group) < num_choices:
            answers.append({"question": q + 1, "answer": "BLANK"})
            continue

        cy = y_grid[row_idx] if row_idx < len(y_grid) else y_rows[-1]

        measurements = []
        for ci, cx in enumerate(group[:num_choices]):
            val = measure_bubble(gray, cx, cy, median_radius)
            measurements.append((ci, val))

        sorted_m = sorted(measurements, key=lambda x: x[1])
        darkest_ci, darkest_val = sorted_m[0]

        # Diger 4 sikki referans al
        others = [m[1] for m in sorted_m[1:]]
        others_mean = float(np.mean(others))
        others_std = float(np.std(others))
        abs_diff = others_mean - darkest_val
        z_distance = abs_diff / max(others_std, 1.0)

        marked = []
        # Istatistiksel isaretleme kriteri
        if darkest_val < cfg.MARK_MAX_DARKEST \
           and abs_diff > cfg.MARK_MIN_DIFF \
           and z_distance > cfg.MARK_Z_MIN:
            if darkest_ci < len(cfg.CHOICE_LABELS):
                marked.append(cfg.CHOICE_LABELS[darkest_ci])
            # Cift isaret tespiti: ikinci en koyu, ilkinden cok az farkliysa
            if len(sorted_m) > 1:
                second_ci, second_val = sorted_m[1]
                if (second_val - darkest_val) < cfg.DOUBLE_MARK_TOLERANCE \
                   and second_val < cfg.MARK_MAX_DARKEST:
                    if second_ci < len(cfg.CHOICE_LABELS):
                        marked.append(cfg.CHOICE_LABELS[second_ci])

        answers.append({
            "question": q + 1,
            "answer": ",".join(sorted(marked)) if marked else "BLANK",
        })

    return answers, None


# ============================================================
# AD-SOYAD OKUMA
# ============================================================

def read_name_region(img, bar_y):
    """
    Ad-soyad matrisi. Akilli ROI: Y sinirini asagidan yukariya
    ilerleterek tam 32 satiri yakalamaya calisir.
    """
    h, w = img.shape[:2]
    x_min = int(w * 0.40)
    x_max = int(w * 0.985)
    y_max = bar_y - 30
    num_letters = len(cfg.TURKISH_ALPHA) - 1  # 32

    # Y_min icin birkac aday dene; en az 30 satir ve en cok 35 satir ver
    # (gurultuye karsi tolerans)
    candidates_y_min = [
        int(h * 0.085),
        int(h * 0.070),
        int(h * 0.055),
        int(h * 0.040),
        int(h * 0.025),
    ]

    best_result = None
    for y_min in candidates_y_min:
        roi = img[y_min:y_max, x_min:x_max]
        if roi.size == 0:
            continue
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        c = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=cfg.HOUGH_DP,
            minDist=cfg.HOUGH_MIN_DIST, param1=cfg.HOUGH_PARAM1, param2=cfg.HOUGH_PARAM2,
            minRadius=cfg.HOUGH_MIN_RADIUS, maxRadius=cfg.HOUGH_MAX_RADIUS,
        )
        if c is None:
            continue
        c = np.round(c[0]).astype(int)
        if len(c) < 100:
            continue
        y_rows_local = cluster_values(c[:, 1].tolist(), cfg.Y_CLUSTER_TOLERANCE)
        n_rows = len(y_rows_local)

        # Ideal: 32-33 satir. Cok az: y_min'i yukari cekmek lazim.
        # Cok fazla: mantikli bir sinirda dur (ust gurultu).
        if n_rows >= num_letters:
            best_result = (y_min, roi, gray, c)
            break
        # En azindan eldekileri tut
        if best_result is None:
            best_result = (y_min, roi, gray, c)

    if best_result is None:
        return ""
    y_min, roi, gray, c = best_result

    x_cols = cluster_values(c[:, 0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    y_rows = cluster_values(c[:, 1].tolist(), cfg.Y_CLUSTER_TOLERANCE)

    if len(x_cols) < 10 or len(y_rows) < 15:
        return ""

    # Y izgarasi: 32 satir olacak sekilde trim/extend
    y_grid = build_uniform_grid(y_rows, num_letters, trim_outliers=True)

    median_r = int(np.median(c[:, 2]))

    # Sutun sayisi: form yazi alani 22 hucre. Fazla varsa baştan veya sondan kirp.
    # Genelde formun sag tarafinda "DTS.836" yazisi / kenar gurultusu oluyor -> sondan kirp.
    if len(x_cols) > 22:
        # Ilk ve son gruplarin yogunlugunu karsilastir; seyrek tarafi at.
        # Basit sezgi: ortadakilerle esit aralikli olmayanlari trimle
        x_cols = x_cols[:22]

    name_chars = []
    for cx in x_cols:
        measurements = []
        for ri, cy in enumerate(y_grid):
            val = measure_bubble(gray, cx, cy, median_r)
            measurements.append((ri, val))
        idx, _ = is_marked_dynamic(measurements)
        if idx is not None:
            target = idx + 1
            if 0 <= target < len(cfg.TURKISH_ALPHA):
                name_chars.append(cfg.TURKISH_ALPHA[target])
            else:
                name_chars.append(" ")
        else:
            name_chars.append(" ")

    return "".join(name_chars).rstrip()


def read_number_region(img, bar_y):
    h, w = img.shape[:2]
    x_min = int(w * 0.06)
    x_max = int(w * 0.26)
    y_min = int(h * 0.32)
    y_max = bar_y - 50

    roi = img[y_min:y_max, x_min:x_max]
    if roi.size == 0:
        return ""
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=cfg.HOUGH_DP,
        minDist=cfg.HOUGH_MIN_DIST, param1=cfg.HOUGH_PARAM1, param2=cfg.HOUGH_PARAM2,
        minRadius=cfg.HOUGH_MIN_RADIUS, maxRadius=cfg.HOUGH_MAX_RADIUS,
    )
    if circles is None:
        return ""
    circles = np.round(circles[0]).astype(int)
    if len(circles) < 20:
        return ""

    x_cols = cluster_values(circles[:, 0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    y_rows = cluster_values(circles[:, 1].tolist(), cfg.Y_CLUSTER_TOLERANCE)

    if len(y_rows) < 5:
        return ""

    x_cols = extend_to_expected_count(x_cols, 10)
    y_grid = build_uniform_grid(y_rows, 10, trim_outliers=True)

    median_r = int(np.median(circles[:, 2])) if len(circles) > 0 else 14

    number = ""
    for cx in x_cols:
        measurements = []
        for di, cy in enumerate(y_grid):
            val = measure_bubble(gray, cx, cy, median_r)
            measurements.append((di, val))
        idx, _ = is_marked_dynamic(measurements)
        if idx is not None:
            number += str(idx)
    return number


# ============================================================
# ANA AKIS
# ============================================================

def detect_num_questions_from_structure(gray, num_choices, rows_per_col, fallback=None):
    """
    Form yapisina bakarak gercek soru sayisini tespit et.
    Daireleri bul, x-sutunlarini grupla, kac tam grup oldugunu say.
    Her grup = 1 sutun = rows_per_col kadar soru.

    Bu, kullanici yanlis soru sayisi gonderse bile (ornegin 100 yazarken
    formda 200 soru varsa) dogru degeri bulmaya yarar.
    """
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=cfg.HOUGH_DP,
        minDist=cfg.HOUGH_MIN_DIST, param1=cfg.HOUGH_PARAM1, param2=cfg.HOUGH_PARAM2,
        minRadius=cfg.HOUGH_MIN_RADIUS, maxRadius=cfg.HOUGH_MAX_RADIUS,
    )
    if circles is None:
        return fallback
    circles = np.round(circles[0]).astype(int)
    x_cols = cluster_values(circles[:, 0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    groups = find_question_groups(x_cols, num_choices)
    if not groups:
        return fallback
    # Her grup tam num_choices sutuna sahip olmali
    valid_groups = [g for g in groups if len(g) >= num_choices]
    return len(valid_groups) * rows_per_col


def _process_image(img, nq, nc, rpc):
    """Tek bir OpenCV goruntuyu isle (PDF'ten gelmis olabilir ya da direkt JPG)."""
    img, _ = resize_if_needed(img)
    bar_y = detect_answer_bar_y(img)

    student_info = {
        "name": read_name_region(img, bar_y),
        "number": read_number_region(img, bar_y),
    }

    answers_region = img[bar_y:]
    gray_ans = cv2.cvtColor(answers_region, cv2.COLOR_BGR2GRAY)

    # Otomatik soru sayisi tespiti
    detected_nq = detect_num_questions_from_structure(gray_ans, nc, rpc, fallback=nq)
    if detected_nq:
        if nq < cfg.DEFAULT_NUM_QUESTIONS and detected_nq >= cfg.DEFAULT_NUM_QUESTIONS:
            nq = cfg.DEFAULT_NUM_QUESTIONS

    answers, err = read_answers_section(gray_ans, nq, nc, rpc)

    if err and not answers:
        return {"error": err, "student_info": student_info}

    blank = sum(1 for a in answers if a["answer"] == "BLANK")
    filled = len(answers) - blank

    return {
        "total_questions": len(answers),
        "answers": answers,
        "student_info": student_info,
        "filled": filled,
        "blank": blank,
    }


def process_single(image_bytes, num_questions=None, num_choices=None, rows_per_col=None):
    """
    Tek form isle. Girdi: JPG/PNG/PDF byte dizisi.
    - Normal resim: tek sonuc doner
    - PDF: YALNIZCA ilk sayfayi isler, diger sayfalar icin process_file kullanin
    """
    nq = num_questions or cfg.DEFAULT_NUM_QUESTIONS
    nc = num_choices or cfg.DEFAULT_NUM_CHOICES
    rpc = rows_per_col or cfg.DEFAULT_ROWS_PER_COLUMN

    try:
        images = decode_to_images(image_bytes)
    except RuntimeError as e:
        return {"error": str(e)}

    if not images:
        return {"error": "Goruntu okunamadi (desteklenmeyen format veya bozuk dosya)"}

    return _process_image(images[0], nq, nc, rpc)


def process_file(file_bytes, num_questions=None, num_choices=None, rows_per_col=None):
    """
    Cok sayfali dosyayi isle (PDF icin ana kullanim).
    Her sayfa ayri bir form olarak islenir.
    Donus: liste of result dict (her biri bir sayfa).
    JPG/PNG icin tek elemanli liste doner.
    """
    nq = num_questions or cfg.DEFAULT_NUM_QUESTIONS
    nc = num_choices or cfg.DEFAULT_NUM_CHOICES
    rpc = rows_per_col or cfg.DEFAULT_ROWS_PER_COLUMN

    try:
        images = decode_to_images(file_bytes)
    except RuntimeError as e:
        return [{"error": str(e)}]

    if not images:
        return [{"error": "Dosya okunamadi (desteklenmeyen format veya bozuk)"}]

    results = []
    for i, img in enumerate(images):
        try:
            r = _process_image(img, nq, nc, rpc)
            r["page"] = i + 1
            results.append(r)
        except Exception as e:
            results.append({"error": f"Sayfa {i+1}: {e}", "page": i + 1})
    return results


def compare_answers(results, answer_key):
    answers = results.get("answers", [])
    correct = wrong = blank = 0
    details = []
    for i, ans in enumerate(answers):
        expected = answer_key[i].strip().upper() if i < len(answer_key) else "?"
        given = ans["answer"].strip().upper()
        is_blank = given in ("BLANK", "BOS", "")
        if is_blank:
            blank += 1
            status = "blank"
        elif given == expected:
            correct += 1
            status = "correct"
        else:
            wrong += 1
            status = "wrong"
        details.append({
            "question": ans["question"],
            "given": given,
            "expected": expected,
            "status": status,
        })

    total = len(answers)
    score = round((correct / total) * 100, 1) if total > 0 else 0
    return {
        "correct": correct, "wrong": wrong, "blank": blank,
        "total": total, "score": score, "details": details,
    }


def img_to_b64(img):
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
