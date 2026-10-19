// Render the stage frame by frame with Playwright and pipe the frames into ffmpeg.
//   node render.mjs                 -> build/frames.mp4 (silent video)
//   node render.mjs --stills 5,20   -> build/still-5.png, build/still-20.png (preview frames)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const stillsArg = args.includes('--stills') ? args[args.indexOf('--stills') + 1] : null;
const fromArg = args.includes('--from') ? +args[args.indexOf('--from') + 1] : 0;
const toArg = args.includes('--to') ? +args[args.indexOf('--to') + 1] : null;

const browser = await chromium.launch({
  executablePath: process.env.CHROME || undefined,
  args: ['--force-color-profile=srgb', '--font-render-hinting=none', '--allow-file-access-from-files'],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.goto('file://' + path.join(ROOT, 'stage', 'index.html'));
await page.evaluate(() => window.stageReady);
const { fps, duration } = await page.evaluate(() => ({ fps: window.TL.fps, duration: window.TL.duration }));

if (stillsArg) {
  for (const s of stillsArg.split(',').map(Number)) {
    await page.evaluate((t) => window.renderAt(t), s);
    await page.screenshot({ path: path.join(ROOT, 'build', `still-${s}.png`) });
    console.log('still', s);
  }
  await browser.close();
  process.exit(0);
}

const first = Math.round(fromArg * fps);
const last = Math.round((toArg ?? duration) * fps);
const out = path.join(ROOT, 'build', toArg || fromArg ? `frames-${fromArg}-${toArg}.mp4` : 'frames.mp4');
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
const t0 = Date.now();
for (let f = first; f < last; f++) {
  await page.evaluate((t) => window.renderAt(t), f / fps);
  const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (f % 150 === 0) console.log(`frame ${f}/${last}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();
console.log('wrote', out);
