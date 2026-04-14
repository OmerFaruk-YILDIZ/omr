"""
omr_engine.py - OpenCV OMR motoru
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
    if len(region) < 20:
        return ""
    x_cols = cluster_values(region[:,0].tolist(), 7)
    y_rows = cluster_values(region[:,1].tolist(), 7)
    if len(y_rows) < 10:
        return ""
    name = ""
    for cx_t in x_cols:
        best_row, best_val = -1, 999
        for (cx, cy, r) in region:
            if abs(cx - cx_t) > 10:
                continue
            ri = int(np.argmin([abs(cy - yr) for yr in y_rows]))
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            val = cv2.mean(gray, mask=mask)[0]
            if val < 190 and val < best_val:
                best_val = val
                best_row = ri
        if 0 <= best_row < len(cfg.TURKISH_ALPHA):
            name += cfg.TURKISH_ALPHA[best_row]
    return name.strip()


def read_student_number(circles, gray, x_min, x_max, y_min, y_max):
    region = circles[(circles[:,0]>=x_min)&(circles[:,0]<=x_max)&(circles[:,1]>=y_min)&(circles[:,1]<=y_max)]
    if len(region) < 10:
        return ""
    x_cols = cluster_values(region[:,0].tolist(), 7)
    y_rows = cluster_values(region[:,1].tolist(), 7)
    if len(y_rows) < 10:
        return ""
    offset = max(0, len(y_rows) - 10)
    digit_rows = y_rows[offset:offset+10]
    number = ""
    for cx_t in x_cols:
        best_d, best_v = -1, 999
        for (cx, cy, r) in region:
            if abs(cx - cx_t) > 10:
                continue
            dists = [abs(cy - yr) for yr in digit_rows]
            di = int(np.argmin(dists))
            if min(dists) > 20:
                continue
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            val = cv2.mean(gray, mask=mask)[0]
            if val < 180 and val < best_v:
                best_v = val
                best_d = di
        if best_d >= 0:
            number += str(best_d)
    return number


def read_student_info(image, bar_y):
    if bar_y <= 0:
        return {"name": "", "number": ""}
    h, w = image.shape[:2]
    upper = image[:bar_y]
    gu = cv2.cvtColor(upper, cv2.COLOR_BGR2GRAY)
    c = cv2.HoughCircles(gu, cv2.HOUGH_GRADIENT, 1, 10, param1=50, param2=18, minRadius=4, maxRadius=13)
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
        cv2.circle(mask, (cx, cy), r, 255, -1)
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
