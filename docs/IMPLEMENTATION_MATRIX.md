# Implementasi aktual vs baseline final

Versi: **V0.1 LOCAL DEVELOPMENT**. Label `BERFUNGSI` bermakna API telah diuji dan UI dasar tersedia; bukan production assurance. `TERBATAS` bermakna hanya sebagian aturan bisnis telah diimplementasikan. `BELUM` artinya perlu pengerjaan lanjutan, dan **tidak boleh diklaim sudah tersedia**.

| Modul | Status V0.1 | Keterangan |
|---|---|---|
| Brand PT Mulia Hakimaco Sejahtera, oranye–hitam | BERFUNGSI | Browser UI responsif; visual audit end-to-end browser belum selesai |
| Login dua role, pembatasan backend | BERFUNGSI | Akun demo lokal, cookies HttpOnly + CSRF; bukan Supabase Auth |
| Invite-only | TERBATAS | Admin provisioning uploader; email invitation belum tersedia |
| Aktivitas & kategori | BERFUNGSI | Kelola sederhana; fitur archive dan retention advanced terbatas |
| Batch multi-file & partial submit | BERFUNGSI | Proses upload sinkron per file pada V0.1 |
| OCR AI | **BELUM** | Manual entry dengan penanda MANUAL_REQUIRED; tidak ada AI OCR palsu |
| File validation | TERBATAS | Ukuran + magic bytes; malware scanning belum terpasang |
| Duplicate detection | TERBATAS | SHA-256 sama; similarity metadata belum ada |
| Risk-based hybrid approval | TERBATAS | Aturan risiko tersedia; auto-approval membutuhkan VERIFIED trusted extraction (disimulasikan hanya pada automated tests), semua demo manual masuk admin review |
| Admin individual review | BERFUNGSI | Alasan untuk approval berisiko & rejection; transactional writes |
| Correction request | BERFUNGSI | Menunggu admin, update data resmi saat approve |
| Document replacement/version history | BERFUNGSI | Candidate private; active version switched on approval |
| Reversal | BERFUNGSI | APPROVED → REVERSED; rejected/pending correction handled atomically |
| Reinstatement & strict SoD | BERFUNGSI | Request pending, assigned reviewer; 2 admin demo |
| Calendar & SLA | TERBATAS | Provisional, manual staging + admin publish, finalization, assigned backup |
| Holiday Sync Now / official API | **BELUM** | Tidak ada SKB API otomatis; admin wajib verifikasi sumber sendiri |
| Reminder, auto escalation worker | TERBATAS | Worker 60 detik; dedup & backup, aggregation rudimentary |
| Snooze once | TERBATAS | Sekali per request; governance per calendar-issue belum disempurnakan |
| Dashboard / financial calculations | BERFUNGSI | Hanya APPROVED |
| XLSX on demand & snapshot | BERFUNGSI | Transactions/Summary/Report Info, export log, formula safety |
| Retention draft 30 hari + purge | BERFUNGSI | Worker: soft-delete, admin restore, purge expired draft |
| Submitted retention tied to closure | **BELUM** | Closure activity ada; retention policy engine belum ada |
| Notifications | TERBATAS | In-app record, UI reload manual; polling 30–60s belum aktif |
| Audit trail | TERBATAS | Atomic DB audit; belum immutable/tamper-resistant storage produksi |
| Supabase PostgreSQL/Storage | **BELUM** | Lokal SQLite + private folder; migration ke PG belum dibuat |
| Next.js + TypeScript frontend | **BELUM** | Frontend HTML/CSS/JS vanilla untuk mudah mulai di VS Code |
| Password reset / MFA / rate limit / public deployment | **BELUM** | Jangan paparkan demo ke internet |
| End-to-end browser / Windows native validation | **BELUM** | Testing API otomatis + JS syntax; Windows nyata belum diuji di sini |

**Syarat rilis produksi:** implementasikan item BELUM dan tutup gap TERBATAS yang termasuk P0/P1. Selesaikan uji integrasi provider, backup, auth, keamanan dokumen, UI browser, dan pengujian Windows.
