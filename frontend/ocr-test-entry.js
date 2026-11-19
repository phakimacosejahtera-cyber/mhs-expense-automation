
import { createWorker } from "tesseract.js";

const fileInput = document.getElementById("ocr-file");
const runButton = document.getElementById("ocr-run");
const status = document.getElementById("ocr-status");
const output = document.getElementById("ocr-result");

runButton.addEventListener("click", async () => {
  const file = fileInput.files?.[0];

  if (!file || !file.type.startsWith("image/")) {
    status.textContent = "Pilih gambar JPG atau PNG dahulu.";
    return;
  }

  let worker;
  runButton.disabled = true;
  output.textContent = "";

  try {
    status.textContent = "Memuat mesin OCR...";

    worker = await createWorker("ind+eng", 1, {
      logger: (message) => {
        if (message.status) {
          status.textContent =
            `${message.status} ${Math.round((message.progress || 0) * 100)}%`;
        }
      }
    });

    const result = await worker.recognize(file);
    output.textContent = result.data.text || "Teks tidak terbaca.";
    status.textContent = "OCR selesai. Periksa teks dengan kuitansi asli.";
  } catch (error) {
    status.textContent = "OCR gagal: " + error.message;
  } finally {
    if (worker) await worker.terminate();
    runButton.disabled = false;
  }
});
