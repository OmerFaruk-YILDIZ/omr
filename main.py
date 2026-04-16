
from flask import Flask, request, jsonify, render_template, send_file
import config as cfg
from omr_engine import process_single, compare_answers
from export import create_batch_excel, get_export_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = cfg.SECRET_KEY


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze_key", methods=["POST"])
def analyze_key():
   
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Dosya yuklenmedi"}), 400
    nq = int(request.form.get("num_questions", cfg.DEFAULT_NUM_QUESTIONS))
    nc = int(request.form.get("num_choices", cfg.DEFAULT_NUM_CHOICES))
    rpc = int(request.form.get("rows_per_col", cfg.DEFAULT_ROWS_PER_COLUMN))
    try:
        result = process_single(f.read(), nq, nc, rpc)
        if "error" in result and "answers" not in result:
            return jsonify({"error": result["error"]}), 400
        key = [a["answer"] for a in result.get("answers", [])]
        return jsonify({"answer_key": key, "total": len(key)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze_batch", methods=["POST"])
def analyze_batch():
   
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Dosya yuklenmedi"}), 400

    nq = int(request.form.get("num_questions", cfg.DEFAULT_NUM_QUESTIONS))
    nc = int(request.form.get("num_choices", cfg.DEFAULT_NUM_CHOICES))
    rpc = int(request.form.get("rows_per_col", cfg.DEFAULT_ROWS_PER_COLUMN))
    ak_str = request.form.get("answer_key", "").strip()
    answer_key = [k.strip() for k in ak_str.split(",") if k.strip()] if ak_str else None

    results = []
    for f in files:
        try:
            r = process_single(f.read(), nq, nc, rpc)
            if "error" in r and "answers" not in r:
                r = {"student_info": r.get("student_info", {"name": f.filename, "number": ""}),
                     "answers": [], "total_questions": nq, "filled": 0, "blank": nq, "error": r["error"]}
            if answer_key and r.get("answers"):
                r["comparison"] = compare_answers(r, answer_key)
            r["filename"] = f.filename
            results.append(r)
        except Exception as e:
            results.append({
                "filename": f.filename,
                "student_info": {"name": f.filename, "number": ""},
                "answers": [], "total_questions": nq,
                "error": str(e)
            })

 
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

    return jsonify({"results": results, "stats": stats, "answer_key": answer_key})


@app.route("/export/excel", methods=["POST"])
def export_excel():
    try:
        data = request.get_json()
        results = data.get("results", [])
        ak = data.get("answer_key")
        if not results:
            return jsonify({"error": "Sonuc yok"}), 400
        buf = create_batch_excel(results, ak)
        return send_file(buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=get_export_filename())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  OMR Scanner - Toplu Optik Form Okuyucu")
    print("=" * 55)
    print("  * Toplu ogrenci kagidi isleme")
    print("  * Ad-Soyad & Ogrenci No okuma")
    print("  * Cevap anahtari ile karsilastirma")
    print("  * Excel rapor (ozet + detay + istatistik)")
    print()
    print("  http://localhost:5000")
    print("  Ctrl+C ile durdur")
    print("=" * 55)
    print()
    app.run(debug=True, host="0.0.0.0", port=5000)
