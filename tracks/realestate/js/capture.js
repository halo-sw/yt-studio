// 카카오맵 로드뷰/지도 스크린샷 러너.
// Usage: node capture.js <url> <outfile> [waitMs]
// stdout: "finalUrl <url>" — 로드뷰 pano/urlX/urlY 파라미터 회수용 (assets.py가 파싱)
const puppeteer = require('puppeteer-core');

const CHROME =
  process.env.CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

(async () => {
  const [url, out, waitMs = '9000'] = process.argv.slice(2);
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--window-size=1600,1000', '--hide-scrollbars', '--enable-unsafe-swiftshader'],
    defaultViewport: { width: 1600, height: 1000 },
  });
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {});
  await new Promise(r => setTimeout(r, Number(waitMs)));
  // 오버레이(지도 설정 풍선 등) 숨김 — 깨끗한 캡처
  await page.evaluate(() => {
    const sels = ['.box_randing', '.layer_mapinfo', '.inner_coach', '.coach_layer', '#dimmedLayer'];
    sels.forEach(s => document.querySelectorAll(s).forEach(e => (e.style.display = 'none')));
  }).catch(() => {});
  await page.screenshot({ path: out });
  console.log('finalUrl', page.url());
  await browser.close();
  console.log('saved', out);
})();
