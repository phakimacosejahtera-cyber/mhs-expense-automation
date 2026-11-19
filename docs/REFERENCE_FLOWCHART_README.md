# Referensi visual dari percakapan

File di `docs/references/flowchart_visual_reference.png` adalah gambar ringkasan yang diberikan/digunakan sebagai referensi fitur, **bukan flowchart teknis tervalidasi 100%**. Ada kekeliruan posisi OCR sebelum/ sesudah submit pada gambar. Aturan FINAL yang benar:

1. Uploader pilih aktivitas → upload kuitansi (1 file = 1 transaksi) → OCR asinkron / fallback manual → review draft → submit sebagian/semua.
2. Sistem validasi & risk flags → risiko rendah auto-approve, pengecualian admin review → approve atau reject dengan alasan.
3. Correction request hanya mengubah data/versi aktif setelah approved admin; status transaksi resmi tetap sampai keputusan.
4. Admin dapat reverse approved → reversed keluar laporan; requester dapat ajukan reinstatement → reviewer admin eligible → approved kembali, atau tetap reversed.
5. SLA provisional jika hari libur belum terverifikasi, alert dan reminder; **tidak ada auto escalation** sampai due final.
6. Dashboard & Excel hanya APPROVED, snapshot ekspor tidak diubah; seluruh perubahan penting audited.

Detail aturan yang tidak muat di diagram: `docs/FINAL_BUSINESS_RULES.md`.

`docs/references/XTROI_UI_reference.html` dipakai **hanya sebagai inspirasi tampilan**, tidak sebagai codebase atau logika akses.
