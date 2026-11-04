// 작품 미리보기 사진 만들기 (build.py 가 부른다)
//   node thumbs.mjs <jobs.json>   jobs = [{ glb: "works/10101/model.glb", out: "works/10101/thumb.webp" }, ...]  (이 폴더 기준 경로)
// - 이 폴더를 작은 웹 서버로 열고, 헤드리스 크롬에서 model-viewer(작품 뷰어와 같은 판)로 모델을 띄워 비스듬한 각도에서 찍는다.
// - 바탕은 투명(webp). 카드 색이 그대로 비쳐 밝은·어두운 화면 모두 어울린다.
import { createServer } from 'node:http';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const ROOT = dirname(fileURLToPath(import.meta.url));
const { chromium } = createRequire(import.meta.url)('C:/Users/j333333/Projects/algeo3d-paint/node_modules/playwright-core');
const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const SIZE = 360;
const PAGE = `<!doctype html><meta charset="utf-8">
<script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>
<style>html,body{margin:0;background:transparent}model-viewer{width:${SIZE}px;height:${SIZE}px;background:transparent;--poster-color:transparent}</style>
<model-viewer id="mv" camera-orbit="35deg 68deg auto" field-of-view="auto" shadow-intensity="1" exposure="1" environment-image="neutral" interaction-prompt="none"></model-viewer>`;
const TYPES = { '.glb': 'model/gltf-binary', '.html': 'text/html; charset=utf-8' };
const server = createServer((req, res) => {
  const u = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (u === '/__thumb') { res.writeHead(200, { 'Content-Type': TYPES['.html'] }); return res.end(PAGE); }
  try { const b = readFileSync(join(ROOT, u)); res.writeHead(200, { 'Content-Type': TYPES[extname(u)] || 'application/octet-stream' }); res.end(b); }
  catch { res.writeHead(404); res.end(); }
}).listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE } });
await page.goto(base + '/__thumb');
await page.waitForFunction(() => customElements.get('model-viewer'), null, { timeout: 30000 });
let ok = 0;
for (const j of jobs) {
  try {
    const data = await page.evaluate(async (src) => {
      const mv = document.getElementById('mv');
      await new Promise((res, rej) => {
        const t = setTimeout(() => rej(new Error('모델을 불러오지 못함')), 30000);
        mv.addEventListener('load', () => { clearTimeout(t); res(); }, { once: true });
        mv.addEventListener('error', () => { clearTimeout(t); rej(new Error('모델 오류')); }, { once: true });
        mv.src = src;
      });
      mv.jumpCameraToGoal();
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const blob = await mv.toBlob({ mimeType: 'image/webp', qualityArgument: 0.85, idealAspect: false });
      const buf = new Uint8Array(await blob.arrayBuffer());
      let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
      return btoa(s);
    }, '/' + j.glb.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/'));
    writeFileSync(join(ROOT, j.out), Buffer.from(data, 'base64'));
    ok++;
  } catch (e) { console.log(`  미리보기 실패: ${j.glb} (${e.message.split('\n')[0]})`); }
}
await browser.close(); server.close();
console.log(`미리보기 ${ok}/${jobs.length}장 새로 찍음`);
