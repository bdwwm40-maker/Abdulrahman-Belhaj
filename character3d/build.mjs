// Renders the character (PNG stills, animation frames) and exports a GLB.
// Usage: node build.mjs [--frames]
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const { chromium } = createRequire(import.meta.url)('playwright');
const OUT = 'output';
fs.mkdirSync(`${OUT}/frames`, { recursive: true });
const server = spawn('python3', ['-m', 'http.server', '8765'], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 800));

const save = (file, dataUrl) =>
  fs.writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', (m) => console.log('[page]', m.text()));
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto('http://localhost:8765/render.html');
  await page.waitForFunction(() => window.ready === true, null, { timeout: 60000 });

  const views = { front: 0, three_quarter: 0.6, side: Math.PI / 2, back: Math.PI };
  for (const [name, yaw] of Object.entries(views)) {
    save(`${OUT}/character_${name}.png`, await page.evaluate((y) => window.renderView(y), yaw));
  }
  save(`${OUT}/character_wave.png`, await page.evaluate(() => window.renderView(0.25, 'Wave', 0.7)));
  save(`${OUT}/character_closeup.png`,
    await page.evaluate(() => window.renderView(0.15, null, 0, { dist: 2.2, ty: 1.45, cy: 0.05 })));

  fs.writeFileSync(`${OUT}/character.glb`, Buffer.from(await page.evaluate(() => window.exportGLB()), 'base64'));

  if (process.argv.includes('--frames')) {
    const fps = 30;
    let n = 0;
    const seq = [['Idle', 2], ['Wave', 2], ['Walk', 2]];
    for (const [clip, dur] of seq) {
      for (let i = 0; i < dur * fps; i++, n++) {
        const yaw = clip === 'Walk' ? 0.9 : 0.2;
        const png = await page.evaluate(([c, t, y]) => window.renderView(y, c, t), [clip, i / fps, yaw]);
        save(`${OUT}/frames/f_${String(n).padStart(4, '0')}.png`, png);
      }
    }
  }
} finally {
  await browser.close();
  server.kill();
}
