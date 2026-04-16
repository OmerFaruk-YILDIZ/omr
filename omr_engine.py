import cv2
import numpy as np
import base64
import config as cfg


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
   
    if cy + r < 0 or cy - r >= h or cx + r < 0 or cx - r >= w:
        return 255.0
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
  
    total = int(mask.sum() / 255)  
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
       
        scale = target_dim / longest
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC), scale
    elif longest > max_dim:
       
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

       
        others = [m[1] for m in sorted_m[1:]]
        others_mean = float(np.mean(others))
        others_std = float(np.std(others))
        abs_diff = others_mean - darkest_val
        z_distance = abs_diff / max(others_std, 1.0)

        marked = []
       
        if darkest_val < cfg.MARK_MAX_DARKEST \
           and abs_diff > cfg.MARK_MIN_DIFF \
           and z_distance > cfg.MARK_Z_MIN:
            if darkest_ci < len(cfg.CHOICE_LABELS):
                marked.append(cfg.CHOICE_LABELS[darkest_ci])
          
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




def read_name_region(img, bar_y):
    
    h, w = img.shape[:2]
    x_min = int(w * 0.40)
    x_max = int(w * 0.985)
    y_max = bar_y - 30
    num_letters = len(cfg.TURKISH_ALPHA) - 1  # 32

  
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

        if n_rows >= num_letters:
            best_result = (y_min, roi, gray, c)
            break
      
        if best_result is None:
            best_result = (y_min, roi, gray, c)

    if best_result is None:
        return ""
    y_min, roi, gray, c = best_result

    x_cols = cluster_values(c[:, 0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    y_rows = cluster_values(c[:, 1].tolist(), cfg.Y_CLUSTER_TOLERANCE)

    if len(x_cols) < 10 or len(y_rows) < 15:
        return ""

   
    y_grid = build_uniform_grid(y_rows, num_letters, trim_outliers=True)

    median_r = int(np.median(c[:, 2]))

 
    if len(x_cols) > 22:
        
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




def detect_num_questions_from_structure(gray, num_choices, rows_per_col, fallback=None):
   
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
   
    valid_groups = [g for g in groups if len(g) >= num_choices]
    return len(valid_groups) * rows_per_col


def process_single(image_bytes, num_questions=None, num_choices=None, rows_per_col=None):
    nq = num_questions or cfg.DEFAULT_NUM_QUESTIONS
    nc = num_choices or cfg.DEFAULT_NUM_CHOICES
    rpc = rows_per_col or cfg.DEFAULT_ROWS_PER_COLUMN

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "Goruntu okunamadi"}

    img, _ = resize_if_needed(img)

    bar_y = detect_answer_bar_y(img)

    student_info = {
        "name": read_name_region(img, bar_y),
        "number": read_number_region(img, bar_y),
    }

    answers_region = img[bar_y:]
    gray_ans = cv2.cvtColor(answers_region, cv2.COLOR_BGR2GRAY)

 
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
