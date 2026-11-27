import './verify-finance-export.mjs';
import { createHash } from 'node:crypto';
import { build } from 'esbuild';
import { mkdir, mkdtemp, readFile, writeFile, copyFile, rename, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('.', import.meta.url));
const dest = path.join(root, 'dist');
const stage = await mkdtemp(path.join(root, '.pages-build-'));
try {
  const assets = path.join(stage, 'assets');
  await mkdir(assets);
  let html = await readFile(path.join(root, 'index.html'), 'utf8');
  const start = html.indexOf('<form id="login-form">');
  const end = html.indexOf('</div>', html.indexOf('<div class="security-hint">', start));
  if (start < 0 || end < start) throw Error('Markup login Phase 3.8 berubah');
  html = html.slice(0, start) + '<a class="btn primary full" href="/api/auth/google/start">Masuk dengan Google</a>' + html.slice(end + 6);
  html = html.replace('<body>', '<body data-host="pages">').replace('LOCAL DEVELOPMENT • V0.1', 'AKSES OWNER')
    .replace('Local Development <small>v0.1 • Data tersimpan di SQLite lokal', 'MHS Expense Automation <small>Workspace Owner')
    .replace('DEVELOPMENT MODE', 'WORKSPACE OWNER');
  for (const name of ['style.css', 'workspace-shell.css', 'storage-dashboard.css']) {
    await copyFile(path.join(root, 'assets', name), path.join(assets, name));
  }
  let js = await readFile(path.join(root, 'assets/app.js'), 'utf8');
  const demo = js.indexOf('for(let button of document.querySelectorAll(\'[data-demo]\'))');
  const boot = js.indexOf('(async()=>{try{state.me=', demo);
  if (demo < 0 || boot < demo) throw Error('Inisialisasi aplikasi berubah');
  js = js.slice(0, demo) + js.slice(boot);
  const version = createHash('sha256').update(js).digest('hex').slice(0,16);
  html = html.replace(/src="\/assets\/app\.js(?:\?[^"]*)?"/, `src="/assets/app.js?v=${version}"`);
  await writeFile(path.join(stage, 'index.html'), html);
  await writeFile(path.join(assets, 'app.js'), js);
  await build({ entryPoints: [path.join(root, 'ocr-engine-entry.js')], bundle: true,
    platform: 'browser', format: 'iife', outfile: path.join(assets, 'ocr-engine.final.bundle.js') });
  const ocrAssets=path.join(assets,'ocr');
  await mkdir(ocrAssets);
  const modules=path.join(root,'node_modules');
  await copyFile(path.join(modules,'tesseract.js/dist/worker.min.js'),path.join(ocrAssets,'worker.min.js'));
  for(const variant of ['','-simd','-relaxedsimd']){
    const filename='tesseract-core'+variant+'-lstm.wasm.js';
    await copyFile(path.join(modules,'tesseract.js-core',filename),path.join(ocrAssets,filename));
  }
  for(const lang of ['ind','eng']){
    const filename=lang+'.traineddata.gz';
    await copyFile(path.join(modules,'@tesseract.js-data',lang,'4.0.0_best_int',filename),path.join(ocrAssets,filename));
  }
  for (const name of ['pages-excel','pages-pdf']) {
    await build({entryPoints:[path.join(root,name+'.mjs')],bundle:true,platform:'browser',format:'esm',outfile:path.join(assets,name+'.js')});
  }
  await copyFile(path.join(root,'node_modules/pdfjs-dist/build/pdf.worker.min.mjs'),path.join(assets,'pages-pdf.worker.mjs'));
  await writeFile(path.join(stage, '_headers'), '/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  X-Frame-Options: SAMEORIGIN\n');
  await rm(dest, { recursive: true, force: true });
  await rename(stage, dest);
} finally {
  await rm(stage, { recursive: true, force: true });
}
