// 유튜브 시청 페이지에서 특정 시점 프레임 캡처 (임베드는 헤드리스에서 오류 153).
// Usage: node yt_frames.js <videoId> <seconds> <outfile>
// 주의: 한 프로세스 = 한 시점. 같은 세션에서 연속 시킹하면 프레임이 갱신되지 않는다.
const puppeteer = require('puppeteer-core');

const CHROME =
  process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
  const [vid, sec, out] = process.argv.slice(2);
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--window-size=1920,1080', '--hide-scrollbars',
           '--autoplay-policy=no-user-gesture-required', '--mute-audio', '--lang=ko-KR'],
    defaultViewport: { width: 1920, height: 1080 },
  });
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36');
  await page.goto(`https://www.youtube.com/watch?v=${vid}`, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {});
  await new Promise(r => setTimeout(r, 4000));

  // 쿠키/동의 배너가 있으면 가장 보수적인 선택(거부)
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')]
      .find(x => /모두 거부|Reject all/i.test(x.textContent));
    if (b) b.click();
  }).catch(() => {});
  await new Promise(r => setTimeout(r, 1500));

  await page.evaluate(() => {
    const v = document.querySelector('video');
    if (v) { v.muted = true; v.play().catch(() => {}); }
  }).catch(() => {});

  // 실제 프레임이 나올 때까지 대기 (videoWidth > 0)
  for (let i = 0; i < 15; i++) {
    const ok = await page.evaluate(() => {
      const v = document.querySelector('video');
      return v && v.videoWidth > 0 && !v.paused;
    }).catch(() => false);
    if (ok) break;
    await page.evaluate(() => { const v = document.querySelector('video'); if (v) { v.muted = true; v.play().catch(() => {}); } }).catch(() => {});
    await new Promise(r => setTimeout(r, 1000));
  }

  await page.evaluate(s => {
    const v = document.querySelector('video');
    if (v) { v.currentTime = s; v.play().catch(() => {}); }
  }, Number(sec)).catch(() => {});
  await new Promise(r => setTimeout(r, 2500));

  await page.evaluate(() => {
    document.querySelectorAll('.ytp-chrome-top,.ytp-chrome-bottom,.ytp-gradient-top,.ytp-gradient-bottom,.ytp-ce-element,.ytp-paid-content-overlay,.ytp-spinner')
      .forEach(e => (e.style.display = 'none'));
  }).catch(() => {});
  await new Promise(r => setTimeout(r, 400));

  const box = await page.evaluate(() => {
    const v = document.querySelector('video');
    if (!v) return null;
    const r = v.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  }).catch(() => null);
  if (box && box.width > 100) {
    await page.screenshot({ path: out, clip: box });
  } else {
    await page.screenshot({ path: out });
  }
  const state = await page.evaluate(() => {
    const v = document.querySelector('video');
    return v ? { t: Math.round(v.currentTime), w: v.videoWidth } : null;
  }).catch(() => null);
  console.log('saved', out, JSON.stringify(state));
  await browser.close();
})();
