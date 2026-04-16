import os
from flask import Flask, request, jsonify, render_template, send_file
import config as cfg
from omr_engine import process_single, process_file, compare_answers
from export import create_batch_excel, get_export_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = cfg.SECRET_KEY

# Debug sadece gelistirmede acik olsun, production'da FLASK_ENV=production ayarlansin
DEBUG = os.environ.get("FLASK_ENV", "development") != "production"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze_key", methods=["POST"])
def analyze_key():
    """
    Cevap anahtari formunu oku.
    Desteklenen dosya formatlari: JPG, PNG, PDF
    PDF ise sadece ilk sayfa kullanilir.
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Dosya yuklenmedi"}), 400

    # Parametreler opsiyonel: None verilirse motor otomatik tespit eder
    nq = request.form.get("num_questions")
    nc = request.form.get("num_choices")
    rpc = request.form.get("rows_per_col")
    nq = int(nq) if nq and nq.isdigit() else None
    nc = int(nc) if nc and nc.isdigit() else None
    rpc = int(rpc) if rpc and rpc.isdigit() else None

    try:
        # Anahtar okumak icin overlay'e ihtiyacimiz yok (hiz icin kapatiyoruz)
        result = process_single(f.read(), nq, nc, rpc, make_overlay=False)
        if "error" in result and "answers" not in result:
            return jsonify({"error": result["error"]}), 400
        key = [a["answer"] for a in result.get("answers", [])]
        return jsonify({"answer_key": key, "total": len(key)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze_batch", methods=["POST"])
def analyze_batch():
    """
    Toplu ogrenci formlarini isle.
    - Her yuklenen JPG/PNG = 1 ogrenci
    - Her yuklenen PDF = N ogrenci (her sayfa 1 ogrenci)
    """
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Dosya yuklenmedi"}), 400

    nq = request.form.get("num_questions")
    nc = request.form.get("num_choices")
    rpc = request.form.get("rows_per_col")
    nq = int(nq) if nq and nq.isdigit() else None
    nc = int(nc) if nc and nc.isdigit() else None
    rpc = int(rpc) if rpc and rpc.isdigit() else None

    ak_str = request.form.get("answer_key", "").strip()
    answer_key = [k.strip() for k in ak_str.split(",") if k.strip()] if ak_str else None

    # Overlay'i parametre olarak kabul et (varsayilan: true)
    make_overlay = request.form.get("overlay", "true").lower() != "false"

    results = []
    for f in files:
        fname = f.filename
        try:
            per_page_results = process_file(
                f.read(), nq, nc, rpc,
                answer_key=answer_key,
                make_overlay=make_overlay,
            )
            is_multi_page = len(per_page_results) > 1

            for idx, r in enumerate(per_page_results):
                if is_multi_page:
                    page_label = f"{fname} (sayfa {r.get('page', idx+1)})"
                else:
                    page_label = fname

                if "error" in r and "answers" not in r:
                    r = {
                        "student_info": r.get("student_info", {"name": page_label, "number": ""}),
                        "answers": [], "total_questions": nq or 0,
                        "filled": 0, "blank": nq or 0,
                        "error": r["error"],
                    }

                if answer_key and r.get("answers"):
                    r["comparison"] = compare_answers(r, answer_key)

                r["filename"] = page_label
                r["file_id"] = f"{fname}__{idx}"  # frontend icin benzersiz id
                results.append(r)

        except Exception as e:
            results.append({
                "filename": fname,
                "file_id": f"{fname}__err",
                "student_info": {"name": fname, "number": ""},
                "answers": [], "total_questions": nq or 0,
                "error": str(e),
            })

    # Sinif istatistikleri
    scores = [r["comparison"]["score"] for r in results if "comparison" in r]
    stats = {}
    if scores:
        import statistics
        stats = {
            "count": len(scores),
            "mean": round(statistics.mean(scores), 1),
            "max": round(max(scores), 1),
            "min": round(min(scores), 1),
            "median": round(statistics.median(scores), 1),
            "stdev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
            "pass_count": sum(1 for s in scores if s >= 50),
            "fail_count": sum(1 for s in scores if s < 50),
        }

    # Blok bazli ortalamalar (radar chart icin gercek veri)
    blocks = compute_block_stats(results, answer_key)

    return jsonify({
        "results": results,
        "stats": stats,
        "blocks": blocks,
        "answer_key": answer_key,
    })


def compute_block_stats(results, answer_key):
    """
    Sorulari 5 bloga bolup her blokta sinif ortalamasini hesaplar.
    Radar chart icin gercek veri uretir.
    """
    if not answer_key or not results:
        return []

    total_q = len(answer_key)
    if total_q == 0:
        return []

    block_size = max(1, total_q // 5)
    blocks = []
    for b in range(5):
        start = b * block_size
        end = min(total_q, (b + 1) * block_size) if b < 4 else total_q
        if start >= total_q:
            break

        pct_list = []
        for r in results:
            details = (r.get("comparison") or {}).get("details", [])
            block_details = details[start:end]
            if not block_details:
                continue
            correct = sum(1 for d in block_details if d.get("status") == "correct")
            pct = (correct / len(block_details)) * 100
            pct_list.append(pct)
        avg = round(sum(pct_list) / len(pct_list), 1) if pct_list else 0
        blocks.append({
            "label": f"S{start+1}-{end}",
            "range": [start + 1, end],
            "avg": avg,
        })
    return blocks


@app.route("/export/excel", methods=["POST"])
def export_excel():
    """
    Excel raporu olustur.
    Frontend'den manuel duzeltilmis sonuclar gonderilebilir.
    """
    try:
        data = request.get_json()
        results = data.get("results", [])
        ak = data.get("answer_key")
        if not results:
            return jsonify({"error": "Sonuc yok"}), 400

        # Eger manuel duzeltme yapildiysa comparison'i yeniden hesapla
        if ak:
            for r in results:
                if r.get("answers"):
                    r["comparison"] = compare_answers(r, ak)

        buf = create_batch_excel(results, ak)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=get_export_filename(),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/recompute", methods=["POST"])
def recompute():
    """
    Manuel duzeltme sonrasi puani yeniden hesaplar.
    Frontend kullanicinin cevaplarini duzelttiginde cagirir.
    """
    try:
        data = request.get_json()
        result = data.get("result", {})
        answer_key = data.get("answer_key")
        if not result or not answer_key:
            return jsonify({"error": "Eksik veri"}), 400
        comparison = compare_answers(result, answer_key)
        return jsonify({"comparison": comparison})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(413)
def too_large(e):
    """Dosya boyutu limiti asildiginda kullaniciya net mesaj ver."""
    mb = cfg.MAX_CONTENT_LENGTH // (1024 * 1024)
    return jsonify({"error": f"Dosya cok buyuk. Maksimum {mb} MB."}), 413


if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  OMR Scanner - Toplu Optik Form Okuyucu")
    print("=" * 55)
    print("  * Desteklenen dosyalar: JPG, PNG, PDF")
    print("  * Cok sayfali PDF = her sayfa ayri ogrenci")
    print("  * Otomatik soru sayisi tespiti")
    print("  * Isaretlemeleri gosteren overlay goruntusu")
    print("  * Manuel cevap duzeltme destegi")
    print("  * Excel + JSON rapor (ozet + detay + istatistik)")
    print()
    print("  http://localhost:5000")
    print("  Ctrl+C ile durdur")
    print("=" * 55)
    print(f"  Debug modu: {'ACIK' if DEBUG else 'KAPALI'}")
    print("  Production icin: FLASK_ENV=production olarak ayarlayin")
    print("=" * 55)
    print()
    app.run(debug=DEBUG, host="0.0.0.0", port=5000)
