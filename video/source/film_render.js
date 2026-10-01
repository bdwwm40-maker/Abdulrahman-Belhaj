const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// usage: node film_render.js <outdir> [t1,t2,...]  (no times = full 48 s at 30 fps)
const out = process.argv[2];
const times = process.argv[3] ? process.argv[3].split(',').map(Number) : null;
const FPS = 30, DUR = 48;

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', (e) => console.error('PAGE ERROR', e.message));
  await page.goto('file://' + path.join(__dirname, 'film.html'));
  await page.evaluate(() => window.ready);
  fs.mkdirSync(out, { recursive: true });
  const list = times || [...Array(FPS * DUR).keys()].map((i) => i / FPS);
  for (let i = 0; i < list.length; i++) {
    await page.evaluate((t) => window.setT(t), list[i]);
    const name = times ? `t${list[i]}.jpg` : `f${String(i).padStart(4, '0')}.jpg`;
    await page.screenshot({ path: path.join(out, name), type: 'jpeg', quality: 94 });
  }
  await browser.close();
})();
