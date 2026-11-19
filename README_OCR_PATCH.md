# PT Mulia Hakimaco Sejahtera — Integrasi Tesseract.js untuk V0.1

**Tujuan:** mengganti pemanggilan OCR Gemini menjadi Tesseract.js berbasis browser pada alur upload yang sudah ada. **Tidak** mengubah aturan approval, correction, reversal, reinstatement, Excel, atau database keuangan yang sudah berjalan.

## Isi patch
- `frontend/assets/app.js` **file lengkap** yang menggantikan `app.js` sebelumnya, tanpa memotong fitur lain.
- `frontend/ocr-engine-entry.js` modul OCR yang menggunakan `tesseract.js` yang sudah terinstal via npm.
- `frontend/ocr-parser.mjs` parser saran nominal/tanggal, konservatif tanpa otomatis menetapkan angka resmi.
- `backend/app/ocr.py` mematikan permintaan Gemini otomatis ketika upload.
- `backend/requirements.txt` menambahkan `tzdata` agar timezone Asia/Jakarta tersedia di Windows.
- `backend/app/main.py` versi lengkap yang menambahkan endpoint terautentikasi penyimpanan histori OCR browser (status EXTRACTED, bukan VERIFIED).
- `tests/` unit test parser dan API baru.
- `install_patch.py` installer yang **menolak menimpa file berbeda** dari versi ZIP acuan dan membuat backup terlebih dahulu.

## Panduan Windows (project sebelumnya sudah berjalan di VS Code)

1. Download ZIP dan extract ke folder baru, **jangan** mengganti project asli dengan ZIP penuh.
2. Buka Terminal VS Code di **folder utama project** yang memuat `backend` dan `frontend`.
3. Dari File Explorer Windows, buka folder patch hasil extract dan **Copy as path** untuk file `install_patch.py`.
4. Jalankan ini di PowerShell VS Code, lalu ganti `PATH_INSTALLER` dengan path lengkap file yang disalin:

```powershell
py -3.13 "PATH_INSTALLER" .
```

Jika path disalin dari Windows Explorer sudah memakai tanda kutip, jangan tambahkan tanda kutip kedua. Installer membuat backup di `.ocr_patch_backups` dan **tidak mengubah `.env` atau data**.

5. Setelah muncul `PATCH BERHASIL DIPASANG`, jalankan:

```powershell
.\.venv-win\Scripts\python.exe -m pip install -r .\backend\requirements.txt
cd .\frontend
npm.cmd exec -- esbuild .\ocr-engine-entry.js --bundle --platform=browser --format=iife --outfile=.\assets\ocr-engine.bundle.js
cd ..
$env:MHS_MODE="demo"
.\.venv-win\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

6. Buka `http://127.0.0.1:8000`, login demo lokal, pilih Upload Receipt, pilih aktivitas, unggah **gambar kuitansi contoh** (JPG/PNG/WebP). Setelah OCR selesai, klik **Periksa & Edit** dan pilih angka/tanggal berdasarkan kuitansi asli. Isi deskripsi dan kategori secara manual, lalu Simpan Draft. Submit mengikuti alur review admin.

## Tes terarah

Dari folder project:

```powershell
cd .\frontend
node --test ..\tests\test_ocr_parser.mjs
cd ..
.\.venv-win\Scripts\python.exe -m pip install pytest httpx
.\.venv-win\Scripts\python.exe -m pytest -q tests\test_browser_ocr_api.py
```

Tes API menggunakan DB sementara. Pengujian browser nyata (Tesseract wasm, data bahasa, network, gambar aktual) **harus dilakukan di Windows**, tidak diklaim sudah lulus sebelum user mengujinya.

## Batasan yang penting
- **Gambar JPG/PNG/WebP**: Tesseract.js berjalan pada browser; proses awal dapat mengunduh worker/WASM/model bahasa. Bundler sudah lokal, tetapi **belum sepenuhnya offline**.
- **PDF**: masih bisa diunggah, tetapi OCR PDF belum tersedia pada patch ini. Isi draft manual. Konversi PDF.js menjadi gambar adalah pekerjaan lanjutan yang terpisah.
- Angka nominal seperti subtotal, pajak, potongan dan jumlah dibayar dapat sama-sama terdeteksi; pengguna **wajib** menentukan angka yang sesuai. Tidak otomatis mengambil nilai terbesar.
- OCR browser dicatat sebagai `EXTRACTED` / **belum terverifikasi**, sehingga transaksi yang disubmit dari OCR ini tetap masuk `PENDING_REVIEW` pada backend demo.
- File `.env` tidak ikut paket. API key Gemini lama yang pernah terlihat harus dicabut dari Google AI Studio dan jangan dipublikasikan. Jangan upload ZIP perusahaan mentah, `.env`, `.venv`, data SQLite, atau kuitansi asli ke GitHub.
- Full regression tests lama dari ZIP acuan diketahui tidak sejalan dengan akun seed terbaru (hanya admin dibuat otomatis), jadi kegagalannya tidak boleh disalahartikan sebagai regresi OCR. Perlu merapikan fixture test yang terpisah pada tahap berikutnya.

## Pemulihan
- Matikan server (`Ctrl+C`).
- Salin kembali `frontend/assets/app.js`, `backend/app/main.py`, `backend/app/ocr.py` dari `.ocr_patch_backups/<timestamp>/...` sesuai struktur folder jika ingin rollback.
- Perubahan ini bersifat development lokal saja; jangan deploy ke internet sebelum security audit, migrasi database dan storage, serta pengujian final.
