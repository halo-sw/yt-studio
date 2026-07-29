// 예린이의 부동산 뽀개기 — 데이터 주도 매물 브리핑 덱 생성기.
// Usage: node deck.js <spec.json> <out.pptx>
// spec: episode.py의 build_spec() 산출물. slides[] 순서대로 렌더한다.
const pptxgen = require('pptxgenjs');
const fs = require('fs');

const [specPath, outPath] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5
const W = 13.33, H = 7.5;

const INK = '23262E', AMBER = 'FFB300', MUTED = '6B7280', CARD = 'F5F6F8', WHITE = 'FFFFFF';
const KR = 'Apple SD Gothic Neo';

function chip(s, x, y, text, w) {
  s.addShape('roundRect', { x, y, w, h: 0.42, rectRadius: 0.21, fill: { color: AMBER }, line: { type: 'none' } });
  s.addText(text, { x, y, w, h: 0.42, align: 'center', valign: 'middle', margin: 0, fontFace: KR, fontSize: 12, bold: true, color: INK });
}
function captionBar(s, head, body) {
  s.addShape('rect', { x: 0, y: H - 1.28, w: W, h: 1.28, fill: { color: INK, transparency: 18 }, line: { type: 'none' } });
  s.addText([
    { text: head + '  ', options: { fontSize: 17, bold: true } },
    { text: body, options: { fontSize: 13.5, color: 'D8DADF' } },
  ], { x: 0.6, y: H - 1.28, w: W - 1.2, h: 1.28, fontFace: KR, color: WHITE, valign: 'middle', margin: 0 });
}
function fullBleed(s, img) {
  s.background = { color: INK };
  s.addImage({ path: img, x: 0, y: 0, w: W, h: H, sizing: { type: 'cover', w: W, h: H } });
}
function title(s, text) {
  s.addText(text, { x: 0.7, y: 0.55, w: 12, h: 0.8, fontFace: KR, fontSize: 32, bold: true, color: INK, margin: 0 });
}

const R = {
  cover(p) {
    const s = pres.addSlide();
    fullBleed(s, p.image);
    s.addShape('rect', { x: 0, y: 0, w: W, h: H, fill: { color: '15171C', transparency: 40 }, line: { type: 'none' } });
    chip(s, 0.7, 0.75, '예린이의 부동산 뽀개기', 2.9);
    s.addText(p.name, { x: 0.65, y: 2.6, w: 12.0, h: 1.3, fontFace: KR, fontSize: 52, bold: true, color: WHITE, margin: 0 });
    s.addText(p.subtitle, { x: 0.68, y: 3.95, w: 11.8, h: 0.55, fontFace: KR, fontSize: 19, color: 'E8E9EC', margin: 0 });
    s.addText(p.footer, { x: 0.68, y: 6.75, w: 10, h: 0.4, fontFace: KR, fontSize: 11.5, color: 'C9CCD3', margin: 0 });
  },
  summary(p) {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    title(s, '오늘의 결론부터 말씀드리면');
    const cw = 2.86, gap = 0.32;
    p.cards.forEach((c, i) => {
      const x = 0.7 + i * (cw + gap);
      s.addShape('roundRect', { x, y: 1.75, w: cw, h: 2.5, rectRadius: 0.12, fill: { color: CARD }, line: { type: 'none' } });
      s.addShape('ellipse', { x: x + 0.28, y: 2.03, w: 0.42, h: 0.42, fill: { color: AMBER }, line: { type: 'none' } });
      s.addText(String(i + 1), { x: x + 0.28, y: 2.03, w: 0.42, h: 0.42, align: 'center', valign: 'middle', margin: 0, fontFace: KR, fontSize: 14, bold: true, color: INK });
      s.addText(c.big, { x: x + 0.28, y: 2.6, w: cw - 0.5, h: 0.75, fontFace: KR, fontSize: 26, bold: true, color: INK, margin: 0 });
      s.addText(c.small, { x: x + 0.28, y: 3.38, w: cw - 0.5, h: 0.8, fontFace: KR, fontSize: 12.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.15 });
    });
    s.addShape('roundRect', { x: 0.7, y: 4.75, w: 11.93, h: 1.9, rectRadius: 0.12, fill: { color: INK }, line: { type: 'none' } });
    s.addText([
      { text: '한 줄 평  ', options: { bold: true, color: AMBER, fontSize: 16 } },
      { text: p.oneliner, options: { color: 'ECEDEF', fontSize: 15.5 } },
    ], { x: 1.1, y: 4.95, w: 11.1, h: 1.5, fontFace: KR, valign: 'middle', margin: 0, lineSpacingMultiple: 1.25 });
  },
  map(p) {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    title(s, p.title);
    s.addImage({ path: p.image, x: 6.35, y: 0.75, w: 6.3, h: 5.95, sizing: { type: 'cover', w: 6.3, h: 5.95 } });
    s.addText(p.credit, { x: 6.35, y: 6.85, w: 6.3, h: 0.35, fontFace: KR, fontSize: 11, color: MUTED, margin: 0, align: 'right' });
    let y = 1.75;
    p.items.forEach(([h, b], i) => {
      s.addShape('ellipse', { x: 0.7, y: y + 0.03, w: 0.38, h: 0.38, fill: { color: AMBER }, line: { type: 'none' } });
      s.addText(String(i + 1), { x: 0.7, y: y + 0.03, w: 0.38, h: 0.38, align: 'center', valign: 'middle', margin: 0, fontFace: KR, fontSize: 13, bold: true, color: INK });
      s.addText(h, { x: 1.25, y, w: 4.6, h: 0.45, fontFace: KR, fontSize: 17, bold: true, color: INK, margin: 0 });
      s.addText(b, { x: 1.25, y: y + 0.47, w: 4.55, h: 1.05, fontFace: KR, fontSize: 13, color: MUTED, margin: 0, lineSpacingMultiple: 1.2 });
      y += 1.72;
    });
  },
  photo(p) { // 로드뷰/내부 풀블리드 + 칩 + 캡션바
    const s = pres.addSlide();
    fullBleed(s, p.image);
    chip(s, 0.6, 0.55, p.chip, 2.9);
    captionBar(s, p.head, p.body);
  },
  overview(p) {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    title(s, '단지 개요');
    s.addImage({ path: p.image, x: 0.7, y: 1.7, w: 6.4, h: 4.5, sizing: { type: 'cover', w: 6.4, h: 4.5 } });
    s.addText(p.credit, { x: 0.7, y: 6.3, w: 6.4, h: 0.35, fontFace: KR, fontSize: 11, color: MUTED, margin: 0 });
    let y = 1.75;
    p.rows.forEach(([k, v], i) => {
      if (i > 0) s.addShape('line', { x: 7.55, y, w: 5.1, h: 0, line: { color: 'E5E7EB', width: 0.75 } });
      s.addText(k, { x: 7.55, y: y + 0.08, w: 1.5, h: 0.55, fontFace: KR, fontSize: 13, bold: true, color: MUTED, margin: 0, valign: 'middle' });
      s.addText(v, { x: 9.1, y: y + 0.08, w: 3.6, h: 0.55, fontFace: KR, fontSize: 13.5, color: INK, margin: 0, valign: 'middle' });
      y += 0.68;
    });
  },
  price(p) {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    title(s, '그래서, 얼마냐면요');
    [[0.7, '보증금', p.deposit, '최저 타입 기준 · 타입/전환 조건에 따라 상이'],
     [6.78, '월 임대료', p.rent, '보증금을 높이면 월세를 낮추는 전환형 운영']].forEach(([x, label, big, note]) => {
      s.addShape('roundRect', { x, y: 1.7, w: 5.85, h: 2.6, rectRadius: 0.12, fill: { color: CARD }, line: { type: 'none' } });
      s.addText(label, { x: x + 0.4, y: 1.95, w: 3, h: 0.4, fontFace: KR, fontSize: 14, bold: true, color: MUTED, margin: 0 });
      s.addText(big, { x: x + 0.4, y: 2.4, w: 5.0, h: 1.1, fontFace: KR, fontSize: 44, bold: true, color: INK, margin: 0 });
      s.addText(note, { x: x + 0.4, y: 3.6, w: 5.2, h: 0.4, fontFace: KR, fontSize: 11.5, color: MUTED, margin: 0 });
    });
    s.addText('입주 자격 (요약)', { x: 0.7, y: 4.7, w: 4, h: 0.45, fontFace: KR, fontSize: 17, bold: true, color: INK, margin: 0 });
    s.addText([
      { text: '만 19~39세 무주택 청년', options: { bullet: true, breakLine: true } },
      { text: '소득·자산 기준 충족 (전년도 도시근로자 월평균소득 기준 적용)', options: { bullet: true, breakLine: true } },
      { text: '자동차 보유 기준 등 세부 조건은 모집공고문 기준', options: { bullet: true } },
    ], { x: 0.85, y: 5.2, w: 11.6, h: 1.25, fontFace: KR, fontSize: 13.5, color: INK, margin: 0, paraSpaceAfter: 6 });
    s.addText('※ 가격·자격은 서울시 청년안심주택 공개 데이터 기준 요약입니다. 실제 계약 조건은 반드시 최신 모집공고문으로 확인하세요.', {
      x: 0.7, y: 6.7, w: 11.9, h: 0.5, fontFace: KR, fontSize: 11, color: MUTED, margin: 0 });
  },
  rating(p) {
    const s = pres.addSlide();
    s.background = { color: WHITE };
    title(s, '예린이의 부동산 뽀개기 평점');
    let y = 1.75;
    p.rows.forEach(([name, score, note]) => {
      const full = Math.floor(score), half = score % 1 >= 0.5;
      s.addText(String(name), { x: 0.7, y, w: 2.5, h: 0.5, fontFace: KR, fontSize: 15.5, bold: true, color: INK, margin: 0, valign: 'middle' });
      s.addText([
        { text: '★'.repeat(full) + (half ? '☆' : ''), options: { color: AMBER, fontSize: 20, bold: true } },
        { text: '★'.repeat(5 - full - (half ? 1 : 0)), options: { color: 'D9DBE0', fontSize: 20, bold: true } },
        { text: '  ' + score.toFixed(1), options: { color: INK, fontSize: 15, bold: true } },
      ], { x: 3.3, y, w: 2.6, h: 0.5, fontFace: KR, margin: 0, valign: 'middle' });
      s.addText(String(note), { x: 6.1, y, w: 6.5, h: 0.5, fontFace: KR, fontSize: 12.5, color: MUTED, margin: 0, valign: 'middle' });
      y += 0.78;
    });
    s.addShape('roundRect', { x: 0.7, y: 5.85, w: 11.93, h: 1.15, rectRadius: 0.12, fill: { color: INK }, line: { type: 'none' } });
    s.addText([
      { text: '뽀개기 총점  ', options: { bold: true, color: AMBER, fontSize: 17 } },
      { text: p.total.toFixed(1) + ' / 5.0', options: { bold: true, color: WHITE, fontSize: 24 } },
      { text: '   — ' + p.comment, options: { color: 'ECEDEF', fontSize: 14.5 } },
    ], { x: 1.1, y: 5.85, w: 11.1, h: 1.15, fontFace: KR, valign: 'middle', margin: 0 });
    s.addText('※ 평점은 공개 데이터·로드뷰·영상 조사 기반 자동 산출 초안입니다 (발행 전 사람 검토).', { x: 0.7, y: 7.08, w: 11.9, h: 0.32, fontFace: KR, fontSize: 10.5, color: MUTED, margin: 0 });
  },
  verdict(p) {
    const s = pres.addSlide();
    s.background = { color: INK };
    s.addText('총평 — 예린이가 솔직하게 뽀개보면', { x: 0.7, y: 0.55, w: 12, h: 0.8, fontFace: KR, fontSize: 32, bold: true, color: WHITE, margin: 0 });
    [[0.7, '이건 좋았다', p.pros], [6.78, '이건 따져보자', p.cons]].forEach(([x, label, items]) => {
      s.addShape('roundRect', { x, y: 1.7, w: 5.85, h: 3.7, rectRadius: 0.12, fill: { color: '2E3340' }, line: { type: 'none' } });
      s.addText(label, { x: x + 0.35, y: 1.95, w: 3, h: 0.45, fontFace: KR, fontSize: 17, bold: true, color: AMBER, margin: 0 });
      s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
        { x: x + 0.35, y: 2.55, w: 5.15, h: 2.6, fontFace: KR, fontSize: 14, color: 'ECEDEF', margin: 0, paraSpaceAfter: 10 });
    });
    s.addText(p.closing, { x: 0.7, y: 5.75, w: 11.93, h: 0.7, fontFace: KR, fontSize: 18, bold: true, color: WHITE, margin: 0, align: 'center', valign: 'middle' });
    s.addText(p.footer, { x: 0.7, y: 6.75, w: 11.93, h: 0.4, fontFace: KR, fontSize: 11.5, color: 'AEB2BC', margin: 0, align: 'center' });
  },
};

for (const slide of spec.slides) {
  R[slide.type](slide);
}
pres.writeFile({ fileName: outPath }).then(() => console.log('deck written', outPath, spec.slides.length, 'slides'));
