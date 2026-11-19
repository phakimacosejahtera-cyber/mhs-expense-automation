# Rencana melanjutkan implementasi menuju MVP final

Paket V0.1 sudah memiliki API FastAPI, database SQLite lokal, UI responsif, dan aturan bisnis dasar yang telah diuji. Urutan berikut **bukan brainstorming ulang**, tetapi urutan development sesuai baseline:

1. Verifikasi startup `.bat` dan uji UI secara manual di Windows (login admin/uploader, upload, edit, approve, XLSX). Dokumentasikan error aktual.
2. Refactor frontend HTML/JS menjadi Next.js + TypeScript **tanpa mengubah kontrak API/rules**, tambah Playwright browser tests dan desain yang mempertahankan identitas oranye–hitam.
3. Migrasikan database ke PostgreSQL/Supabase, Auth dan Storage dengan private policies + RLS yang cocok, transactional audit, migrations, indeks, locking, backup.
4. Tambahkan OCR vision-capable adapter sungguhan dengan enqueued job, extract data terstruktur, confidence/risk, raw extraction immutable, manual fallback, MIME/malware processing, idempotency.
5. Lengkapi aktivitas dan retensi berdasarkan closure; document access log; filter/pagination review queue; user invitation email; background job persistence dan retry.
6. Lengkapi holiday sync sumber resmi SKB via stage/diff/approve, business hour configuration/version snapshots, explicit recalculation, verified year horizons, reminder aggregation per issue dan SLA UX.
7. Lengkapi security P0/P1 dan E2E termasuk race conditions, SoD no eligible backup, export formula injection, year boundary, restart worker recovery, access across users.
8. Deployment ke infra terkelola, staging, security assessment, backup recovery test, audit acceptance sebelum data produksi.

**Sumber kebenaran:** `FINAL_BUSINESS_RULES.md`; `IMPLEMENTATION_MATRIX.md` menandai apa yang belum selesai. Jangan ubah status sebuah fitur menjadi 'selesai' hanya karena menunya sudah muncul.
