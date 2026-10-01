const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const [w, h, out] = [Number(process.argv[2]), Number(process.argv[3]), process.argv[4]];
const FPS = 30, DUR = 8;

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto('file://' + path.join(__dirname, 'endcard.html'));
  await page.evaluate(() => document.fonts.ready);
  fs.mkdirSync(out, { recursive: true });
  for (let i = 0; i < FPS * DUR; i++) {
    await page.evaluate((t) => window.setT(t), i / FPS);
    await page.screenshot({ path: path.join(out, `f${String(i).padStart(4, '0')}.png`) });
  }
  await browser.close();
})();
