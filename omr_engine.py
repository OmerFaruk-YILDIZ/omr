"""
omr_engine.py - OpenCV OMR motoru (Gelişmiş Izgara & Dinamik Kontrast Destekli)
"""
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


def create_mathematical_grid(values, expected_count=None):
    """
    Eksik algılanan yuvarlaklar olsa bile, ilk ve son yuvarlağa bakarak
    kusursuz bir matematiksel satır/sütun ızgarası oluşturur.
    """
    if len(values) < 2: return values
    
    # Uçlardaki hatalı tespitleri (yazı vb.) filtrele
    q1 = np.percentile(values, 10)
    q3 = np.percentile(values, 90)
    core_vals = [v for v in values if q1 - 20 <= v <= q3 + 20]
    if len(core_vals) < 2: core_vals = values
    
    start, end = core_vals[0], core_vals[-1]
    
    if expected_count:
        step = (end - start) / max(1, expected_count - 1)
        return [start + i * step for i in range(expected_count)]
        
    gaps = [core_vals[i+1] - core_vals[i] for i in range(len(core_vals)-1)]
    median_gap = np.median(gaps)
    if median_gap < 5: return core_vals
    
    count = int(round((end - start) / median_gap)) + 1
    step = (end - start) / max(1, count - 1)
    return [start + i * step for i in range(count)]


def find_question_groups(x_columns, num_choices):
    if len(x_columns) < num_choices:
        return []
    gaps = [x_columns[i+1] - x_columns[i] for i in range(len(x_columns)-1)]
    if not gaps:
        return [x_columns]
    median_gap = np.median(gaps)
    threshold = median_gap * cfg.X_GROUP_GAP_MULTIPLIER
    groups, current = [], [x_columns[0]]
    for i, gap in enumerate(gaps):
        if gap > threshold:
            groups.append(current)
            current = [x_columns[i+1]]
        else:
            current.append(x_columns[i+1])
    groups.append(current)
    return groups


def find_answer_region(image):
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    ranges = [
        (np.array([5,80,150]), np.array([25,255,255])),
        (np.array([0,80,150]), np.array([10,255,255])),
        (np.array([160,80,150]), np.array([180,255,255])),
    ]
    best = -1
    for lo, hi in ranges:
        mask = cv2.inRange(hsv, lo, hi)
        rows = np.where(mask.sum(axis=1) > w * 0.3 * 255)[0]
        if len(rows) > 5 and rows.max() > best:
            best = rows.max()
    if best > 0 and best < h * 0.85:
        return best + 5, True
    return 0, False


def read_name(circles, gray, x_min, x_max, y_min, y_max):
    region = circles[(circles[:,0]>=x_min)&(circles[:,0]<=x_max)&(circles[:,1]>=y_min)&(circles[:,1]<=y_max)]
    if len(region) < 20: return ""
    
    raw_x = cluster_values(region[:,0].tolist(), 12)
    raw_y = cluster_values(region[:,1].tolist(), 10)
    
    if len(raw_x) < 2 or len(raw_y) < 15: return ""
    
    y_grid = create_mathematical_grid(raw_y)
    radius = int(np.median(region[:,2])) if len(region) > 0 else 8
    
    name = ""
    for cx in raw_x:
        vals = []
        for cy in y_grid:
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (int(cx), int(cy)), max(2, radius-2), 255, -1)
            val = cv2.mean(gray, mask=mask)[0]
            vals.append((val, cy))
            
        vals.sort(key=lambda x: x[0])
        darkest_val, darkest_cy = vals[0]
        
        # Dinamik Kontrast Tespiti
        is_marked = False
        if len(vals) > 2:
            median_empty = np.median([v[0] for v in vals[1:]])
            if (median_empty - darkest_val) > 25 or darkest_val < 140:
                is_marked = True
        elif darkest_val < 160:
            is_marked = True
            
        if is_marked:
            row_idx = int(np.argmin([abs(darkest_cy - yr) for yr in y_grid]))
            
            # Formun ilk yuvarlağı genelde 'A' harfidir. cfg.TURKISH_ALPHA'da boşluk varsa onu atla
            offset = 0
            if " " in cfg.TURKISH_ALPHA and len(cfg.TURKISH_ALPHA) > len(y_grid):
                offset = 1
                
            target_idx = row_idx + offset
            if 0 <= target_idx < len(cfg.TURKISH_ALPHA):
                name += cfg.TURKISH_ALPHA[target_idx]
            else:
                name += " "
        else:
            name += " "
            
    return name.strip()


def read_student_number(circles, gray, x_min, x_max, y_min, y_max):
    region = circles[(circles[:,0]>=x_min)&(circles[:,0]<=x_max)&(circles[:,1]>=y_min)&(circles[:,1]<=y_max)]
    if len(region) < 10: return ""
    
    raw_x = cluster_values(region[:,0].tolist(), 12)
    raw_y = cluster_values(region[:,1].tolist(), 10)
    
    if len(raw_y) < 5: return ""
    
    # Sayılar bloğunda her zaman 0-9 arası tam 10 satır vardır. Yukarıdaki yazıları ekarte et
    raw_y = raw_y[-10:] if len(raw_y) > 10 else raw_y
    y_grid = create_mathematical_grid(raw_y, 10)
    radius = int(np.median(region[:,2])) if len(region) > 0 else 8
    
    number = ""
    for cx in raw_x:
        vals = []
        for cy in y_grid:
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (int(cx), int(cy)), max(2, radius-2), 255, -1)
            val = cv2.mean(gray, mask=mask)[0]
            vals.append((val, cy))
            
        vals.sort(key=lambda x: x[0])
        darkest_val, darkest_cy = vals[0]
        
        # Dinamik Kontrast Tespiti
        is_marked = False
        if len(vals) > 2:
            median_empty = np.median([v[0] for v in vals[1:]])
            if (median_empty - darkest_val) > 25 or darkest_val < 140:
                is_marked = True
        elif darkest_val < 160:
            is_marked = True
            
        if is_marked:
            best_d = int(np.argmin([abs(darkest_cy - yr) for yr in y_grid]))
            number += str(best_d)
            
    return number


def read_student_info(image, bar_y):
    if bar_y <= 0:
        return {"name": "", "number": ""}
    h, w = image.shape[:2]
    upper = image[:bar_y]
    gu = cv2.cvtColor(upper, cv2.COLOR_BGR2GRAY)
    
    # Zayıf basılmış formlardaki halkaları da yakalayabilmek için parametreler esnetildi
    c = cv2.HoughCircles(gu, cv2.HOUGH_GRADIENT, 1, 10, param1=45, param2=16, minRadius=4, maxRadius=15)
    if c is None:
        return {"name": "", "number": ""}
        
    c = np.round(c[0]).astype(int)
    mx = int(w * 0.4)
    my = int(bar_y * 0.45)
    
    return {
        "name": read_name(c, gu, mx, w, 0, bar_y),
        "number": read_student_number(c, gu, 0, mx, my, bar_y),
    }


def read_answers_section(gray, num_questions, num_choices, rows_per_col):
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=cfg.HOUGH_DP,
        minDist=cfg.HOUGH_MIN_DIST, param1=cfg.HOUGH_PARAM1, param2=cfg.HOUGH_PARAM2,
        minRadius=cfg.HOUGH_MIN_RADIUS, maxRadius=cfg.HOUGH_MAX_RADIUS)
    if circles is None:
        return [], "Daire bulunamadi"
        
    circles = np.round(circles[0]).astype(int)
    ah, aw = gray.shape[:2]
    x_pos = cluster_values(circles[:,0].tolist(), cfg.X_CLUSTER_TOLERANCE)
    y_pos = cluster_values(circles[:,1].tolist(), cfg.Y_CLUSTER_TOLERANCE)
    qgroups = find_question_groups(x_pos, num_choices)
    
    if not qgroups:
        return [], "Soru gruplari bulunamadi"
        
    bounds = []
    for i, g in enumerate(qgroups):
        lo = 0 if i == 0 else (qgroups[i-1][-1] + g[0]) // 2
        hi = aw if i == len(qgroups)-1 else (g[-1] + qgroups[i+1][0]) // 2
        bounds.append((lo, hi, g))
        
    grid = {}
    for (cx, cy, r) in circles:
        gi, gc = -1, None
        for idx, (lo, hi, cols) in enumerate(bounds):
            if lo <= cx < hi:
                gi, gc = idx, cols
                break
        if gi < 0 or gc is None:
            continue
            
        ci = int(np.argmin([abs(cx - c) for c in gc]))
        if ci >= num_choices:
            continue
            
        ri = int(np.argmin([abs(cy - yr) for yr in y_pos]))
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (cx, cy), max(2, int(r-2)), 255, -1)
        val = cv2.mean(gray, mask=mask)[0]
        
        key = (gi, ri)
        if key not in grid:
            grid[key] = []
        grid[key].append((ci, val))
        
    answers = []
    for gi in range(len(qgroups)):
        mr = min(rows_per_col, num_questions - gi * rows_per_col)
        if mr <= 0:
            break
        for ri in range(mr):
            qn = gi * rows_per_col + ri + 1
            if qn > num_questions:
                break
            key = (gi, ri)
            if key not in grid:
                answers.append({"question": qn, "answer": "BLANK"})
                continue
                
            marked = [cfg.CHOICE_LABELS[ci] for ci, val in sorted(grid[key]) if val < cfg.FILL_THRESHOLD and ci < len(cfg.CHOICE_LABELS)]
            answers.append({"question": qn, "answer": ",".join(marked) if marked else "BLANK"})
            
    return answers, None


def process_single(image_bytes, num_questions=None, num_choices=None, rows_per_col=None):
    """Tek bir formu isle. Sonuc: dict."""
    nq = num_questions or cfg.DEFAULT_NUM_QUESTIONS
    nc = num_choices or cfg.DEFAULT_NUM_CHOICES
    rpc = rows_per_col or cfg.DEFAULT_ROWS_PER_COLUMN

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "Goruntu okunamadi"}

    h, w = img.shape[:2]
    if max(h, w) > cfg.MAX_IMAGE_DIM:
        s = cfg.MAX_IMAGE_DIM / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s)

    bar_y, found = find_answer_region(img)
    si = read_student_info(img, bar_y) if found and bar_y > 100 else {"name": "", "number": ""}

    region = img[bar_y:] if bar_y > 0 else img
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    answers, err = read_answers_section(gray, nq, nc, rpc)
    if err:
        return {"error": err, "student_info": si}

    blank = sum(1 for a in answers if a["answer"] == "BLANK")
    filled = len(answers) - blank
    
    return {
        "total_questions": len(answers),
        "answers": answers,
        "student_info": si,
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
            blank += 1; status = "blank"
        elif given == expected:
            correct += 1; status = "correct"
        else:
            wrong += 1; status = "wrong"
        details.append({"question": ans["question"], "given": given, "expected": expected, "status": status})
        
    total = len(answers)
    score = round((correct / total) * 100, 1) if total > 0 else 0
    return {"correct": correct, "wrong": wrong, "blank": blank, "total": total, "score": score, "details": details}


def img_to_b64(img):
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
