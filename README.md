# PT Mulia Hakimaco Sejahtera — Expense Automation

**Paket implementasi lokal V0.1 • Windows / VS Code • Warna merek oranye–hitam**

Aplikasi web demo yang **dapat dijalankan** di Windows dengan Python dan browser. Dirancang berdasarkan baseline bisnis Expense Automation MVP yang disepakati: satu kuitansi = satu transaksi, role Uploader/Admin, batch upload, draft, approval hybrid, koreksi, reversal, reinstatement, audit, dan ekspor APPROVED-only.

> **WAJIB DIBACA:** V0.1 bukan sistem produksi dan belum memuat semua modul MVP akhir. Integrasi AI OCR sungguhan, Supabase/PostgreSQL, Next.js, sinkronisasi otomatis SKB, keamanan produksi dan sejumlah rincian governance **belum selesai**. Jangan gunakan untuk data keuangan perusahaan sungguhan, jangan deploy secara publik, dan jangan memakai password demonstrasi untuk akun nyata.

## 1 — Yang perlu diinstal

- Windows 10/11, VS Code (sudah terinstal).
- **Python 3.11–3.13**, dengan Python Launcher (`py`) atau PATH diaktifkan. Download resmi: https://www.python.org/downloads/windows/
- Koneksi internet **saat instalasi dependency Python pertama kali**.
- Browser modern (Chrome/Edge/Firefox).

**Node.js dan Git belum diperlukan untuk menjalankan V0.1 lokal.** Next.js, Supabase, dan GitHub tetap merupakan arah arsitektur final yang akan ditambahkan pada fase selanjutnya. Ini keputusan pengemasan sementara agar proyek pertama mudah dijalankan dan dapat diuji, bukan perubahan baseline bisnis.

## 2 — Buka di VS Code

1. Extract ZIP ke folder biasa, misalnya `Documents\PT_Mulia_Hakimaco_Sejahtera_Expense_Automation`.
2. Buka VS Code → **File → Open Folder** → pilih folder hasil extract (yang berisi `START_WINDOWS.bat`).
3. Pilih **Trust** hanya jika file ini memang berasal dari ZIP yang kamu periksa.
4. Di VS Code pilih **Terminal → New Terminal**. Pada terminal PowerShell, jalankan:

   ```powershell
   .\START_WINDOWS.bat
   ```

   Alternatif: double-click `START_WINDOWS.bat` melalui File Explorer.
5. Saat terminal menampilkan alamat aplikasi, buka **http://127.0.0.1:8000** di browser.
6. Biarkan terminal pertama terbuka selama aplikasi dipakai. Untuk menghentikan, gunakan `Ctrl+C`.

Jika `py` / `python` tidak ditemukan, instal Python dan buka ulang terminal. Jika pip tidak bisa mengunduh dependency, periksa internet dan proxy kantor. **Tidak ada API key yang perlu dimasukkan untuk mode demo.**

## 3 — Login demonstrasi (HANYA LOCALHOST)

| Peran | Email | Password demo |
|---|---|---|
| Admin Utama | `admin@mhs.local` | `AdminDemo123!` |
| Admin Cadangan | `backup@mhs.local` | `BackupDemo123!` |
| Uploader | `uploader@mhs.local` | `UploaderDemo123!` |

Login hanya untuk demontrasi multi-role. Admin dapat menambahkan akun uploader baru lewat Management. Email invitation otomatis belum tersedia.

## 4 — Cara mencoba alur utama

1. Masuk sebagai **Uploader** → Upload Receipt → pilih aktivitas → upload PNG/JPEG/WEBP/PDF (maksimum 8 MB/file).
2. Klik **Periksa & Edit** pada draft. Isi tanggal, nominal, kategori, dan keterangan secara manual. Untuk V0.1, AI OCR **belum dihubungkan**. Sistem secara eksplisit menandai `MANUAL_REQUIRED`.
3. Pilih draft → **Submit Terpilih**. **Dalam mode demo tanpa OCR terpercaya, semua submission manual akan menjadi `PENDING_REVIEW`**. Auto-approval hanya akan aktif jika ekstraksi benar-benar terverifikasi pada integrasi mendatang.
4. Untuk menguji review, upload ulang file yang sama, lengkapi draft, dan submit. Masuk sebagai **Admin** → Review Queue → masukkan alasan dan approve/reject.
5. Untuk transaksi approved, uji **Koreksi** (usulan data tidak langsung mengganti data resmi), atau **Reverse** oleh admin.
6. Ajukan **Reinstatement** pada transaksi reversed. Jika admin yang mengajukan, admin tersebut tidak bisa menyetujui atau menolak request sendiri. Masuk sebagai admin lain untuk memutuskan.
7. Pada **Reports & Excel**, klik Download Excel. File `MHS_Approved_Expenses.xlsx` memiliki tiga sheet: Transactions, Summary, Report Info.
8. Di **Calendar & SLA**, admin dapat stage daftar hari libur manual dan mem-publish setelah verifikasi. Reinstatement provisional tidak boleh dieskalasi otomatis.

## 5 — Worker terpisah

Buka terminal VS Code kedua dan jalankan:

```powershell
.\START_WORKER_WINDOWS.bat
```

Worker memeriksa SLA final, pengingat provisional, dan purge draft kedaluwarsa setiap ±60 detik. **Jalankan terminal web dulu**; worker membutuhkan database yang sudah diinisialisasi. Cron/scheduler production belum dibangun.

## 6 — Pengujian otomatis

Pada terminal VS Code yang lain:

```powershell
.\TEST_WINDOWS.bat
```

Atau jalankan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

Pengujian developer dilakukan dengan `TestClient` dan SQLite sementara, bukan database demo kamu. Lihat `docs/TEST_REPORT.md` untuk hasil yang benar-benar dijalankan sebelum ZIP ini dibuat.

## 7 — Struktur file

```text
backend/app/             API FastAPI, keamanan, database, rules, worker
backend/requirements.txt Dependency Python
frontend/index.html      Layout UI oranye-hitam
frontend/assets/         JavaScript & CSS dashboard
 database/               Salinan skema SQL SQLite dari backend
 tests/                  Pytest skenario end-to-end API
 docs/                   Baseline dan cakupan fitur
 docs/references/        File XTROI + flowchart (hanya referensi)
 START_WINDOWS.bat        Bootstrap + jalankan aplikasi di localhost
 START_WORKER_WINDOWS.bat Background worker lokal
 TEST_WINDOWS.bat         Jalankan automated tests
 storage/                 SQLite dan kuitansi pribadi di folder lokal (diabaikan Git)
```

## 8 — Keamanan data & keterbatasan

- Server default hanya `127.0.0.1:8000` (tidak dapat diakses secara publik).
- Dokumen disimpan di `storage/private_docs`, **tidak dilayani sebagai static directory**.
- Hak akses diverifikasi oleh backend dan tiap write membutuhkan token CSRF.
- Audit terkait perubahan disimpan dalam SQLite lokal; ini **belum append-only/tamper-resistant production audit**.
- Belum ada antivirus scanning, email invitation, MFA, HTTPS/TLS production, backup/disaster recovery terkelola, rate limiting login, AI OCR eksternal, maupun deployment cloud.
- Link kuitansi Excel membuka dokumen jika browser sudah login dan role berwenang.
- `storage/` dan `.env` tidak boleh dipush ke GitHub. Jangan pernah membagikan file database hasil penggunaan atau screenshot berisi data nyata.

## 9 — Sumber kebenaran implementasi

`docs/FINAL_BUSINESS_RULES.md` adalah referensi aturan bisnis yang disepakati. Gambar di `docs/references/` **hanya ilustrasi** dan masih mengandung beberapa penyederhanaan/panah yang keliru. Jika bertentangan, ikuti dokumen aturan bisnis dan test. Daftar cakupan aktual ada di `docs/IMPLEMENTATION_MATRIX.md`.

Paket ini bukan “kode final produksi yang sudah lulus semua tes”; ini adalah **fondasi runnable dan teruji** untuk pengembangan bertahap sampai implementasi final.
