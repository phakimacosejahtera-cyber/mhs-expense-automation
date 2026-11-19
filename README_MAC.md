# Panduan MacBook — PT Mulia Hakimaco Sejahtera Expense Automation V0.1

Paket ini **berisi kode aplikasi yang sama** dengan paket Windows V0.1, ditambah skrip macOS. **Tidak semua fitur MVP final sudah diimplementasikan**, dan belum ada integrasi AI OCR sungguhan/Supabase/Next.js. Penggunaan **hanya demo lokal**; jangan masukkan data keuangan perusahaan nyata.

## Persiapan
1. Instal **Visual Studio Code** (macOS) dan **Python 3.11–3.13** dari https://www.python.org/downloads/macos/. Bisa pada MacBook Apple Silicon (M1/M2/M3/M4) atau Intel jika menggunakan installer Python yang sesuai.
2. Unduh ZIP ini, ekstrak ke folder biasa dan buka folder `PT_Mulia_Hakimaco_Sejahtera_Expense_Automation` di VS Code menggunakan File → Open Folder.
3. Buka terminal VS Code lewat **Terminal → New Terminal**, atau shortcut **Control + backtick** (bukan Command+backtick), tergantung konfigurasi keyboard.
4. Jalankan `python3 --version`. Pastikan versinya 3.11, 3.12, atau 3.13. Kalau di Mac ada banyak versi Python, `python3` harus mengarah ke versi yang didukung.
5. Di terminal yang berada dalam root project, jalankan:

```bash
bash START_MAC.sh
```

Ini akan membuat `.venv`, memasang dependency menggunakan pip (butuh internet saat instalasi pertama), dan menjalankan server **hanya di** `http://127.0.0.1:8000`.

**Biarkan terminal tetap terbuka**. Buka URL itu dengan Chrome/Safari.

## Background worker (opsional, setelah server pertama berjalan)
Buka terminal VS Code kedua:

```bash
bash START_WORKER_MAC.sh
```

## Testing (opsional)
Buka terminal ketiga:

```bash
bash TEST_MAC.sh
```

## Login khusus demo
- Admin utama: `admin@mhs.local` / `AdminDemo123!`
- Admin cadangan: `backup@mhs.local` / `BackupDemo123!`
- Uploader: `uploader@mhs.local` / `UploaderDemo123!`

## Catatan
- Skrip `START_WINDOWS.bat`, `START_WORKER_WINDOWS.bat`, dan `TEST_WINDOWS.bat` **hanya untuk Windows**. Di Mac gunakan `.sh` sesuai panduan ini.
- Tidak perlu Node.js, Git, atau Supabase untuk **menjalankan V0.1 demo**.
- `storage/` akan menyimpan data demo lokal. Jangan unggah database, `.env`, atau dokumen privat ke repository publik.
- Jika `python3` tidak ditemukan, install Python dari python.org, tutup dan buka lagi VS Code. Jika port 8000 dipakai aplikasi lain, tutup server yang memakainya sebelum menjalankan aplikasi ini.
- Pengujian tersedia di `docs/TEST_REPORT.md`, tetapi skrip `.sh` ini **belum diuji di Mac fisik**. Sebelum ZIP dibuat, pemeriksaan sintaks shell dilakukan dalam lingkungan Linux dan unit/API tests dijalankan di lingkungan tersedia.
- Sumber aturan bisnis: `docs/FINAL_BUSINESS_RULES.md`; daftar kemampuan aktual V0.1: `docs/IMPLEMENTATION_MATRIX.md`.
