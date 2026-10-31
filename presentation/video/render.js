// Renders animated.html frame by frame (deterministic seeking) and pipes JPEG frames into ffmpeg.
// Run: node render.js [out.mp4] [fps]
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const out = process.argv[2] || path.join(__dirname, "out.mp4");
const FPS = parseInt(process.argv[3] || "30", 10);
const ONLY = process.env.ONLY_T; // e.g. "3.5,20" -> write PNG stills instead of a video
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto("file://" + path.join(__dirname, "animated.html"));
  await page.evaluate(() => document.fonts.ready);
  const total = await page.evaluate(() => { document.getAnimations().forEach(a => a.pause()); return window.TOTAL; });
  const seek = (t) => page.evaluate((ms) => document.getAnimations().forEach(a => (a.currentTime = ms)), t * 1000);
  if (ONLY) {
    for (const t of ONLY.split(",").map(Number)) { await seek(t); await page.screenshot({ path: path.join(path.dirname(out), `still-${t}.png`) }); }
    await browser.close(); return;
  }
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], { stdio: ["pipe", "inherit", "inherit"] });
  const n = Math.round(total * FPS);
  for (let f = 0; f < n; f++) {
    await seek(f / FPS);
    const buf = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    if (f % 300 === 0) console.log(`frame ${f}/${n}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on("close", r));
  await browser.close();
  console.log("done", out, total + "s");
})();
