# Laporan Pengujian — V0.1 (sebelum ZIP diserahkan)

**Produk:** PT Mulia Hakimaco Sejahtera — Expense Automation

**Hasil:** **16/16 automated backend/API tests LULUS**. Pengujian benar-benar dieksekusi pada lingkungan Python 3.13.5 dan Node.js 22.16.0 di Linux sandbox. Karena sistem pengerjaan bukan Windows, **startup `.bat` belum diuji di Windows asli**. Pembukaan UI melalui browser headless dibatasi lingkungan; karena itu **UI visual E2E belum diverifikasi**. Jangan menganggap ini sertifikasi siap produksi.

## Yang benar-benar dijalankan

| Pengujian | Hasil | Keterangan |
|---|---|---|
| `pytest -q tests/test_workflows.py` | **16 passed** | Keamanan dua role, upload, SQL transaksi, workflow approval, koreksi, reversal, reinstatement, SLA, ekspor |
| `python -m compileall -q backend tests` | **LULUS** | Python source parse |
| `node --check frontend/assets/app.js` | **LULUS** | JavaScript syntax parse; bukan browser integration |
| Uvicorn HTTP GET `/api/health` | **200 OK** | Server berjalan pada localhost 8189 di sandbox |
| GET `/` + `/assets/style.css` + `/assets/app.js` | **200 OK** | HTML/CSS/JS served |
| HTTP login uploader + GET `/api/me` | **200 OK** | Cookie session berfungsi pada permintaan HTTP |
| HTTP unauthorized `/api/admin/review-queue` | **403 Forbidden** | Pembatasan role backend berfungsi pada smoke test |
| Playwright Chromium UI E2E | **BELUM** | Browser diblokir kebijakan lingkungan (`ERR_BLOCKED_BY_ADMINISTRATOR`), tidak diklaim lulus |
| Windows BAT install/start | **BELUM** | Harus diverifikasi pada mesin Windows pengguna |
| PostgreSQL/Supabase/AI provider | **BELUM** | Tidak dikonfigurasi; tidak ada klaim integrasi sukses |

## Daftar 16 tes

1. Login & backend role authorization
2. Upload, trusted-extraction test signal, auto-approval & XLSX
3. Duplikat harus manual review, admin approval, double-decision conflict
4. Correction pending tidak mengubah total; approval, reversal, historical Excel
5. Admin-initiated reinstatement SoD; different admin decision
6. Provisional SLA, snooze sekali, calendar stage & publish, SLA finalization
7. Soft-delete draft dan restore admin
8. Closed activity butuh late reason & manual review
9. File invalid ditolak
10. Partial submission batch dan duplicate submission guard
11. Uploader lain tidak bisa membuka kuitansi atau transaksi milik orang
12. Candidate version tetap nonaktif sampai admin approve
13. Formula injection di XLSX dinetralisasi
14. Background worker tidak auto-escalate provisional
15. Final SLA worker melakukan escalation assignment ke admin berbeda
16. Manual entry tanpa trusted OCR **tidak boleh auto-approve**

## Keputusan kualitas

- Semua kondisi yang **diimplementasikan dan dapat diujikan lewat backend** dalam daftar di atas lolos.
- **Jangan** memakai real company finance data; keamanan produksi, OCR eksternal, storage cloud, rate limiting, malware scan, dan instruksi installer Windows asli belum diverifikasi.
- Mode demo akan selalu menahan input manual untuk **review admin**. Ini disengaja supaya aplikasi tidak auto-approve kuitansi tanpa validasi OCR tepercaya.
- Lihat `docs/IMPLEMENTATION_MATRIX.md` untuk gap baseline final yang belum selesai.
