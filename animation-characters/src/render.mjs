// Render character stages with Playwright.
//   node render.mjs stills <outDir> [scale]         -> <char>_<pose>.png (one key frame per pose)
//   node render.mjs frames <outDir> [fps] [chars] [poses] -> <outDir>/<char>/<pose>/0000.png ...
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// require() honours NODE_PATH, so a globally installed playwright is found too
const { chromium } = createRequire(import.meta.url)('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
const stageDir = path.join(here, '..', 'build', 'stage');
const [mode, outDir, arg3, charsArg, posesArg] = process.argv.slice(2);
const CHARS = charsArg ? charsArg.split(',') : ['ahmed', 'mariam', 'yousef', 'sara'];
// time used for the still image of each pose
const STILL_T = { idle: 0, wave: 0.15, talk: 0.25, 'point-right': 0.6, 'point-left': 0.6 };

const browser = await chromium.launch();
const W = 1080, H = 1350;

for (const id of CHARS) {
  const scale = mode === 'stills' ? Number(arg3 || 2) : 1;
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  await page.goto('file://' + path.join(stageDir, `${id}.html`));
  const poses = posesArg ? posesArg.split(',') : await page.evaluate(() => window.POSES);
  const duration = await page.evaluate(() => window.DURATION);
  for (const pose of poses) {
    if (mode === 'stills') {
      fs.mkdirSync(outDir, { recursive: true });
      await page.evaluate(([p, t]) => window.setPose(p, t), [pose, STILL_T[pose] ?? 0]);
      await page.screenshot({ path: path.join(outDir, `${id}_${pose}.png`), omitBackground: true });
    } else {
      const fps = Number(arg3 || 30);
      const n = Math.round(duration * fps);
      const dir = path.join(outDir, id, pose);
      fs.mkdirSync(dir, { recursive: true });
      for (let i = 0; i < n; i++) {
        await page.evaluate(([p, t]) => window.setPose(p, t), [pose, i / fps]);
        await page.screenshot({ path: path.join(dir, String(i).padStart(4, '0') + '.png'), omitBackground: true });
      }
      console.log(id, pose, n, 'frames');
    }
  }
  await page.close();
}
await browser.close();
