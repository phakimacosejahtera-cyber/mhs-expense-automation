# Business Rules — FINAL BASELINE (v1.0)

**PT Mulia Hakimaco Sejahtera — Expense Automation**

Dokumen ini menjelaskan aturan bisnis yang **dikunci** melalui brainstorming. Tidak semua aturan sudah diimplementasikan di V0.1. Jangan menafsirkan flowchart ilustratif sebagai aturan bisnis bila ada panah atau status yang menyimpang dari spesifikasi ini.

## A. Users & access

- Hanya admin yang dapat mengundang uploader; tidak ada registrasi publik.
- Uploader hanya mengakses transaksi, dokumen, laporan, dan notifikasi miliknya. Admin dapat mengelola seluruh data sesuai kewenangan.
- Admin tidak boleh meng-approve atau meng-reject reinstatement request yang ia ajukan sendiri; tidak ada pengecualian. Harus ada reviewer admin lain yang memenuhi syarat. Jika tidak tersedia, request tetap pending.
- Otorisasi harus selalu diperiksa oleh backend, bukan hanya menu UI.

## B. Receipt intake & batch

- **Satu kuitansi = satu transaksi**, tidak ada itemization atau split otomatis.
- Uploader memilih satu aktivitas sebelum upload batch. Setiap receipt memiliki file asli immutable.
- Upload diproses asinkron per kuitansi pada target final; OCR failure memungkinkan input manual.
- OCR tidak boleh mengarang nilai yang tidak ditemukan. Simpan raw extraction terpisah.
- Uploader memeriksa draft yang berisiko/tidak lengkap dan boleh mengirim sebagian batch. Draft tidak memiliki batas waktu kedaluwarsa otomatis, tetapi uploader boleh soft-delete dan hanya admin boleh restore dalam 30 hari. Setelah itu worker boleh purge draft.
- Hash duplikat dan kemiripan metadata memicu flag review admin, bukan auto rejection.
- Kuitansi multi-kategori wajib review; tetap satu receipt satu transaksi.

## C. Submit & approval

- Field wajib: tanggal, jumlah, keterangan, aktivitas, kategori, uploader, dan referensi dokumen asli.
- Validasi risiko rendah → sistem dapat auto-approve; risiko tinggi, flag, duplikat, late → admin review.
- Dua jalur keputusan terpisah. Manual review **tidak boleh kembali ke auto-approval**.
- Admin mengambil keputusan per transaksi; approval berisiko wajib alasan; semua rejection wajib alasan.
- Transaksi REJECTED tidak dihitung; rejection **tidak otomatis membuat correction request**.

## D. Corrections & versions

- Submitted transaction tidak boleh langsung diedit oleh uploader. Gunakan correction_request dengan alasan dan data usulan.
- Data approved resmi tetap berlaku selama request pending. Admin approve/reject, semua keputusan audited.
- Penggantian file melalui request admin-approved; old versions immutable dan active document pointer atomik.
- Request disetujui mengubah reporting dinamis; historic XLSX snapshots tetap seperti saat ekspor.
- Dokumen asli, histori versi, dan request submitted tidak boleh dipurge otomatis dalam MVP.

## E. Reversal and reinstatement

- Hanya admin boleh reverse APPROVED; wajib alasan dan konfirmasi. Status REVERSED keluar dari total dan ekspor baru, bukan hilang dari audit.
- Reinstatement dibuat oleh original uploader atau admin; selama pending tetap REVERSED. Satu pending request per transaksi.
- Persetujuan admin eligible mengaktifkan transaksi yang sama dengan data/versi resmi terakhir; status kembali APPROVED, bukan status transaksi REINSTATED permanen.
- Segregation of duties wajib untuk request yang diinisiasi admin: admin pemohon tidak boleh menjadi approver atau rejector.
- Manual escalation beralasan atau automatic escalation setelah 24 jam kerja (FINAL only), hanya mengganti assignment reviewer, tidak mengubah status finansial.

## F. Calendar, SLA & reminders

- Kalender global berdasarkan zona waktu IANA Asia/Jakarta; jam kerja dapat dikonfigurasi (contoh awal Sen–Jum 09:00–17:00, tanpa overnight).
- Hari libur bersumber dari SKB resmi pemerintah Indonesia. Sync mingguan + Sync Now, staging/validation/diff dan **persetujuan admin** sebelum publish. Tahun berjalan + tahun berikutnya. Hari libur belum tersedia tidak boleh diasumsikan kosong.
- SLA 24 jam kerja = 1440 menit kerja. Simpan versi kalender saat request dibuat. Edit kalender tidak boleh mengubah SLA final sebelumnya tanpa recalculation terotorisasi/audited.
- Jika kalender relevan belum terverifikasi: SLA PROVISIONAL, `review_due_at`/final due NULL, estimasi provisional ditampilkan, **auto-escalation dilarang**.
- Estimasi provisional lewat tenggat → priority alert admin pengelola kalender, tidak mengubah status reinstatement/transaksi. Reminder setiap 24 jam kerja, deduplikasi dan agregasi, jangan membanjiri saat downtime.
- Snooze reminder maksimal sekali selama 24 jam kerja dengan alasan wajib; tidak mengubah due, request, assignment, atau overdue indicator.
- Saat kalender dipublikasikan, hitung due FINAL lalu bila terlambat dapat eskalasi pada evaluasi berikut.

## G. Activities, retention & late receipts

- Aktivitas berstatus ACTIVE / COMPLETED / ARCHIVED terpisah dari closure OPEN / CLOSED. Status closed tidak membekukan laporan.
- Retensi terikat closure eksplisit, admin mengelola kebijakan; reassignment tidak boleh memperpendek retensi secara diam-diam.
- Submission setelah closure wajib alasan keterlambatan dan admin review; ketika approved masuk laporan terbaru. Historical exports tidak berubah.

## H. Dashboard, reports, audit

- Dashboard/Excel wajib menghitung **hanya APPROVED**; bukan reversed, rejected, drafts, atau pending review.
- Export XLSX on-demand dengan sheet Transactions, Summary, Report Info. User export only own approved; admin all approved. Catat waktu dan filter ekspor; cegah spreadsheet formula injection.
- Receipt link stabil menuju versi aktif terbaru dengan auth; version history tersedia. Catat akses dokumen.
- Keputusan finansial atomik, optimistic revision, no double-approval, audit append-only, private storage, idempotency; backup & job recovery production.

## I. UX

- Uploader: Upload Receipt, My Transactions, My Reports, Notifications. Tidak harus memahami OCR, SLA, database.
- Admin: Dashboard, Unified Review Queue, Calendar & SLA, Management, Reports, Audit. Approval/rejection individual dan risk confirmations.
- Responsive web; native mobile, WhatsApp bot, live Excel sync, external notification channel bukan MVP.

## J. Code delivery

- Target arsitektur: Next.js + TypeScript frontend, FastAPI backend, PostgreSQL/Supabase Auth/Storage, worker, OCR AI adapter, openpyxl.
- **V0.1 lokal ini** memakai FastAPI + HTML/CSS/JavaScript tanpa bundler dan SQLite development adapter untuk mengurangi prasyarat awal Windows. Lihat IMPLEMENTATION_MATRIX agar perubahan teknologi sementara tidak disalahartikan sebagai implementasi final selesai.
