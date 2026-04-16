# 📊 OMR Scanner — Akıllı Optik Form Okuyucu

https://omr-aw8f.onrender.com/

Yapay zeka ve görüntü işleme teknolojileriyle çalışan, tarayıcı tabanlı toplu optik form okuyucu uygulaması.

## ✨ Özellikler

### 📥 Çoklu Dosya Formatı Desteği
- **JPG / PNG / WEBP / BMP** — Tek bir resim = 1 öğrenci
- **PDF** — Çoklu sayfalı PDF = her sayfa ayrı öğrenci (tek dosyayla sınıfın tamamını yükleyebilirsiniz)
- **Akıllı PDF çıkarma** — PDF'te gömülü orijinal görüntü varsa kayıpsız çıkarılır, yoksa 300 DPI'da render edilir

### 🔍 Otomatik Algılama
- **Otomatik ölçek** — Telefonla çekilmiş düşük çözünürlüklü fotoğrafları otomatik büyütür, yüksek DPI taramaları standart boyuta getirir
- **Otomatik CEVAPLAR bandı tespiti** — Turuncu bandı fiducial olarak kullanır, sabit koordinat yok
- **Otomatik soru sayısı** — Form yapısına bakıp gerçek soru sayısını bulur
- **Otomatik dizilim** — Sütun sayısı, satır sayısı, şık konumları otomatik hesaplanır

### 🎯 Akıllı İşaret Tespiti
- **İstatistiksel eşikleme** — Z-score tabanlı; farklı ışık/kalem koşullarında çalışır
- **Dinamik kontrast** — Soluk kalem izlerini (telefon fotosu) de yakalar, matbaa izlerini reddeder
- **Çift işaret tespiti** — Öğrenci yanlışlıkla 2 şık işaretlerse algılar
- **Ad-Soyad & Numara okuma** — Türkçe alfabe (Ç, Ğ, İ, Ö, Ş, Ü) dahil

### 👁️ Görsel Doğrulama
- **Overlay görüntü** — Her öğrencinin işaretlerini **yeşil (doğru) / kırmızı (yanlış) / sarı X (kaçırılmış)** daireleriyle gösteren debug image
- **7 sütunlu cevap grid'i** — Formun fiziksel yapısı gibi, kolay tarama
- **Modal büyütme** — Kağıdı büyüterek manuel kontrol

### ✏️ Manuel Düzeltme
- Tıkla-değiştir modu ile yanlış okunan cevapları öğretmen düzeltebilir
- Düzeltme sonrası puan otomatik yeniden hesaplanır
- Excel ve JSON çıktılarına düzeltilmiş haliyle yansır

### 💾 Oturum Korunması
- Sayfa yenilense bile sonuçlar kaybolmaz (localStorage)
- "Kayıtlı oturum" banner'ı ile kullanıcı bilgilendirilir

### 📊 Analiz & Raporlama
- Sınıf istatistikleri (ortalama, medyan, std sapma, vs.)
- Top 3 başarılı öğrenci leaderboard'u
- **Gerçek blok bazlı radar chart** (Soru 1-40, 41-80, ... ortalamaları)
- **Excel rapor** (3 sayfa: Özet, Detay, İstatistik)
- JSON export

### 🎨 UI Özellikleri
- 3 farklı tema (Siberpunk, Matrix, Gündüz)
- Özel vurgu rengi seçici
- Entegre hesap makinesi ve harf notu çevirici
- Responsive tasarım (mobil uyumlu)

## 🚀 Kurulum

```bash
# Gerekli kütüphaneleri kur
pip install -r requirements.txt

# Uygulamayı başlat
python main.py
```

Tarayıcıdan `http://localhost:5000` adresine gidin.

### Production modu

```bash
export FLASK_ENV=production
python main.py
```

## 📁 Proje Yapısı

```
omr/
├── main.py               # Flask uygulaması (API endpoints)
├── omr_engine.py         # OCR motoru (OpenCV)
├── config.py             # Yapılandırma
├── export.py             # Excel rapor üreticisi
├── requirements.txt
├── templates/
│   └── index.html        # Ana sayfa
└── static/
    ├── style.css         # Stiller
    └── app.js            # Frontend mantığı
```

## 🔧 İnce Ayar (`config.py`)

Motor farklı form veya kağıt tipinde sorun yaşarsa aşağıdaki parametreler ayarlanabilir:

```python
# İşaret tespiti
MARK_MAX_DARKEST = 220   # Mutlak eşik - üstündekiler işaretli sayılmaz
MARK_MIN_DIFF = 13       # Diğer şıklardan en az bu kadar koyu olmalı
MARK_Z_MIN = 2.0         # Z-score (istatistiksel anlamlılık)

# PDF çözünürlüğü
PDF_DPI = 300            # Render fallback için (gömülü resim varsa bu kullanılmaz)

# Görüntü boyutu
TARGET_IMAGE_DIM = 3000  # Küçük görüntüler buna kadar büyütülür
MAX_IMAGE_DIM = 4000     # Büyük görüntüler buna kadar küçültülür
```

## 📡 API Endpoints

- `GET /` — Ana sayfa
- `POST /analyze_key` — Cevap anahtarı formu oku (JPG/PNG/PDF)
- `POST /analyze_batch` — Toplu öğrenci formu analizi (multiple files, PDF destekli)
- `POST /recompute` — Manuel düzeltme sonrası puan yeniden hesaplama
- `POST /export/excel` — Excel raporu indir

## 🧠 Algoritma Akışı

1. **Dosya decode**: JPG/PNG normal, PDF gömülü resim çıkarma → OpenCV BGR görüntü
2. **Ölçek normalleştirme**: Resize if needed (telefon fotosu büyütme, büyük tarama küçültme)
3. **Fiducial tespiti**: Turuncu CEVAPLAR bandını bul → bar_y
4. **Ad-Soyad & Numara**: Akıllı ROI ile üst bölgedeki baloncukları oku
5. **Daire tespiti**: Hough Circle ile cevap bölgesindeki baloncukları bul
6. **Izgara oluşturma**: X sütunlarını 7 grup × 5 şık olarak ayır, Y için düzgün izgara
7. **İstatistiksel okuma**: Her soru için 5 şıkkın parlaklık değerlerini ölç, z-score ile işaretli olanı seç
8. **Overlay oluştur**: İşaretlemeleri renkli dairelerle debug image'e çiz
9. **Karşılaştırma**: Cevap anahtarıyla karşılaştır, doğru/yanlış hesapla
10. **Sonuç**: JSON + base64 overlay image frontend'e gönderilir

## ✍️ Geliştirici

**Ömer Faruk Yıldız** — Software Developer Assistant Specialist

- Instagram: [@omerfarukyldz_](https://www.instagram.com/omerfarukyldz_/)
- LinkedIn: [omerfaruk-yildiz](https://www.linkedin.com/in/omerfaruk-yildiz)

## 📄 Lisans

MIT
