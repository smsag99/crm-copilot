/* اسلایدهای ارائهٔ ۱۰ دقیقه‌ای — ساختار پیشنهادی راهنمای داوران
   پاسخ اول · دامنه و کاربر · دموی زنده · چطور کار می‌کند · اعتبارسنجی · ارزش و محدودیت */
const pptx = require('pptxgenjs');
const P = new pptx();

P.layout = 'LAYOUT_WIDE';           // 13.3 × 7.5 اینچ
P.rtlMode = true;
P.author = 'نفیس نخ · هکاتون پل سوم';
P.title = 'دستیار هوشمند تحلیل مشتریان B2B';

const NAVY = '1E2761', ICE = 'CADCFC', WHITE = 'FFFFFF';
const CHERRY = 'A4161A', INK = '15192E', MUTE = '5B6178', PAPER = 'FFFFFF';
const GOOD = '1B7F4B', WARN = 'C77700';
const F = 'Tahoma';
const W = 13.3, H = 7.5, M = 0.62;

const rtl = (o = {}) => ({ fontFace: F, rtlMode: true, align: 'right', ...o });

function slide(dark = false) {
  const s = P.addSlide();
  s.background = { color: dark ? NAVY : PAPER };
  return s;
}

function title(s, txt, dark = false, sub) {
  s.addText(txt, rtl({ x: M, y: 0.42, w: W - 2 * M, h: 0.85, fontSize: 32, bold: true,
    color: dark ? WHITE : INK, valign: 'middle', margin: 0 }));
  if (sub) s.addText(sub, rtl({ x: M, y: 1.24, w: W - 2 * M, h: 0.42, fontSize: 14,
    color: dark ? ICE : MUTE, valign: 'top', margin: 0 }));
}

function stat(s, x, y, w, big, lab, color, note) {
  s.addText(big, rtl({ x, y, w, h: 0.72, fontSize: 34, bold: true, color,
    align: 'center', margin: 0, valign: 'middle' }));
  s.addText(lab, rtl({ x, y: y + 0.7, w, h: 0.4, fontSize: 12.5, color: INK,
    align: 'center', margin: 0 }));
  if (note) s.addText(note, rtl({ x, y: y + 1.06, w, h: 0.62, fontSize: 10.5, color: MUTE,
    align: 'center', margin: 0, valign: 'top' }));
}

function card(s, x, y, w, h, fill, line) {
  s.addShape(P.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.09,
    fill: { color: fill }, line: { color: line || fill, width: 1 } });
}

/* گلوله را دستی می‌گذاریم: در راست‌به‌چپ، گلولهٔ خودکار pptxgenjs
   سمت چپ سطر می‌افتد و متن را وسط‌چین نشان می‌دهد. */
function bullets(s, x, y, w, items, size = 14.5, color = INK) {
  s.addText(items.map((t, i) => ({ text: '• ' + t,
    options: { breakLine: i < items.length - 1 } })),
    rtl({ x, y, w, h: 0.46 * items.length + 0.5, fontSize: size, color,
      paraSpaceAfter: 9, lineSpacingMultiple: 1.15, margin: 0, valign: 'top' }));
}

/* ═════════════════════════ ۱ — عنوان و پاسخ اول */
{
  const s = slide(true);
  s.addText('دستیار هوشمند تحلیل مشتریان B2B', rtl({ x: M, y: 1.55, w: W - 2 * M, h: 0.95,
    fontSize: 40, bold: true, color: WHITE, margin: 0 }));
  s.addText('نفیس نخ · هکاتون پل سوم · کارخانه هوش مصنوعی ایران',
    rtl({ x: M, y: 2.5, w: W - 2 * M, h: 0.4, fontSize: 15, color: ICE, margin: 0 }));
  card(s, M, 3.22, W - 2 * M, 1.72, '2A3670', '3C4C8E');
  s.addText('کاربر — مدیر فروش با ۶۴۴ حساب و تیمی با ظرفیت ثابت',
    rtl({ x: M + 0.28, y: 3.4, w: W - 2 * M - 0.56, h: 0.45, fontSize: 15.5, color: ICE, bold: true, margin: 0, valign: 'middle' }));
  s.addText('تصمیم — وقت این هفته را روی کدام حساب‌ها بگذاریم و از کدام برداریم',
    rtl({ x: M + 0.28, y: 3.84, w: W - 2 * M - 0.56, h: 0.45, fontSize: 15.5, color: ICE, bold: true, margin: 0, valign: 'middle' }));
  s.addText('محصول، سبد را به فهرست ۴۰ حسابی می‌بُرد که ۶۵ درصد فروش را پوشش می‌دهد — و برای هر حذف دلیل می‌نویسد',
    rtl({ x: M + 0.28, y: 4.32, w: W - 2 * M - 0.56, h: 0.5, fontSize: 15.5, color: WHITE, margin: 0, valign: 'middle' }));
  ['۱۷٬۶۳۶ رفرنس قابل ردیابی', '۱۲۰ آزمون خودکار، همه سبز', '۳۰ از ۳۰ عدد در آزمون دستی منطبق']
    .forEach((t, i) => s.addText(t, rtl({ x: W - M - 4.0 - i * 4.1, y: 5.25, w: 4.0, h: 0.4,
      fontSize: 13, color: ICE, margin: 0, align: 'center' })));
  s.addNotes('یک جمله: کاربر مدیر فروش است، تصمیم «وقت تیم کجا برود»، و محصول سبد ۶۴۴ نفره را به ۴۰ حساب می‌برد با دلیل هر حذف.');
}

/* ═════════════════════════ ۲ — دامنه و کاربر */
{
  const s = slide();
  title(s, 'دامنه: یک تصمیم، تا انتها', false,
    'از شش خروجی صورت‌مسئله، «ریسک و فرصت» و «اقدام بعدی» را انتخاب کردیم و تا اقدام قابل اجرا بردیم.');
  const items = [
    ['ساختیم', ['فهرست تمرکز با دلیل هر حذف', 'موتور سیگنال و اقدام با رفرنس', 'هزینهٔ پول و سود واقعی هر حساب', 'دستیار متکی بر همان محاسبات'], GOOD],
    ['عمداً نساختیم', ['سامانهٔ CRM کامل و احراز هویت', 'مدل یادگیری ماشین جعبه‌سیاه', 'رابط بی‌نقص و پشتیبانی هر پرسش', 'خط لولهٔ زندهٔ اتصال به ERP'], MUTE],
  ];
  items.forEach(([h, list, col], i) => {
    const x = i === 0 ? W / 2 + 0.12 : M;
    card(s, x, 1.95, W / 2 - M - 0.12, 3.5, 'F4F6FB', 'DDE3F0');
    s.addText(h, rtl({ x: x + 0.25, y: 2.12, w: W / 2 - M - 0.62, h: 0.45, fontSize: 19, bold: true, color: col, margin: 0 }));
    bullets(s, x + 0.25, 2.68, W / 2 - M - 0.62, list, 14, INK);
  });
  s.addText('«عمق روی یک جریان تصمیم واقعی از ده قابلیت نیم‌ساخته ارزشمندتر است.» — راهنمای داوران',
    rtl({ x: M, y: 5.7, w: W - 2 * M, h: 0.4, fontSize: 12.5, italic: true, color: MUTE, margin: 0 }));
  s.addNotes('دامنه را عمداً باریک کردیم. آنچه نساختیم را هم می‌گوییم، چون داوران دقیقاً همین را می‌پرسند.');
}

/* ═════════════════════════ ۳ — یافتهٔ اصلی */
{
  const s = slide();
  title(s, 'حاشیهٔ ناخالص مشتریان را از هم جدا نمی‌کند — هزینهٔ پول می‌کند', false,
    'پول این سبد به‌طور میانگین ۵۴ روز نزد مشتری می‌ماند. با نرخ ۴٪ ماهانه:');
  s.addChart(P.ChartType.bar, [{
    name: 'میلیون تومان', labels: ['سود ناخالص', 'هزینهٔ پول', 'سود واقعی', 'ذخیرهٔ مشکوک‌الوصول', 'سود خالص'],
    values: [443.2, -468.6, -25.4, -167.6, -193.0],
  }], {
    x: M, y: 1.95, w: W - 2 * M, h: 3.2, barDir: 'col',
    chartColors: [NAVY, CHERRY, CHERRY, WARN, CHERRY],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 12,
    dataLabelFontFace: F, dataLabelColor: INK,
    catAxisLabelFontFace: F, catAxisLabelFontSize: 12, catAxisLabelColor: INK,
    valAxisLabelFontFace: F, valAxisLabelFontSize: 10, valAxisLabelColor: MUTE,
    valGridLine: { color: 'E8EBF2', size: 1 }, catGridLine: { style: 'none' },
    showLegend: false, showTitle: false, valAxisTitle: '',
    catAxisOrientation: 'maxMin', dataLabelFormatCode: '#,##0;(#,##0)',
  });
  const row = 5.4, sw = 3.6;
  [['۳۱۹', 'مشتری زیان‌ده روی حاشیهٔ واقعی', CHERRY, 'در برابر ۵۷ مشتری روی حاشیهٔ ناخالص'],
   ['۴۸٫۶ واحد', 'دامنهٔ حاشیهٔ واقعی', CHERRY, 'در برابر ۲۶٫۷ واحد روی حاشیهٔ ناخالص — رتبه‌بندی روی ناخالص، رتبه‌بندی روی نویز است'],
   ['۴۱۴', 'مشتری با جابه‌جایی رتبه', WARN, 'بیش از ۵۰ پله میان دو رتبه‌بندی']]
    .forEach(([b, l, c, n], i) => stat(s, W - M - sw - i * (sw + 0.2), row, sw, b, l, c, n));
  s.addNotes('این اسلاید قلب ارائه است. سود ناخالص ۴۴۳ میلیون، هزینهٔ تأمین مالی همین مشتریان ۴۶۹ میلیون. سود واقعی سبد منفی است.');
}

/* ═════════════════════════ ۴ — آزمون قیمت‌گذاری اعتبار */
{
  const s = slide();
  title(s, 'آیا اعتبار در قیمت لحاظ شده است؟ آزمودیم، فرض نکردیم', false,
    'قیمت واحد همان کد کالا در همان ماه، بین شرایط پرداخت مقایسه شد.');
  const rows = [
    ['شرط پرداخت', 'روز تا نقد', 'مارک‌آپ مورد انتظار', 'مشاهده‌شده', 'نتیجه'],
    ['نقدی', '۲۳ روز', '—', 'مبنا', '—'],
    ['۳۰ روزه', '۵۲ روز', '۴٫۰٪', '۱٫۸٪', 'کمتر از نیمی از انتظار'],
    ['۹۰ روزه', '۱۱۳ روز', '۱۲٫۰٪', '۲٫۰٪', 't = ۱٫۵ — بی‌معنا'],
  ];
  /* جدول در pptxgenjs راست‌به‌چپ نمی‌شود؛ ستون‌ها را خودمان معکوس می‌کنیم
     تا ستون اول در سمت راست بنشیند. */
  s.addTable(rows.map((r, ri) => [...r].reverse().map(c => ({
    text: c,
    options: { fontFace: F, rtlMode: true, align: 'right', fontSize: ri === 0 ? 12 : 14,
      bold: ri === 0 || (ri === 3), color: ri === 0 ? WHITE : (ri === 3 ? CHERRY : INK),
      fill: { color: ri === 0 ? NAVY : (ri % 2 ? 'F4F6FB' : PAPER) }, margin: 6 },
  }))), { x: M, y: 2.0, w: W - 2 * M, colW: [2.86, 2.0, 2.9, 1.9, 2.4], rowH: 0.5 });
  card(s, M, 4.45, W - 2 * M, 1.42, 'FDF1F1', 'F0CFCF');
  s.addText('نتیجه — اعتبار قیمت‌گذاری نشده است',
    rtl({ x: M + 0.28, y: 4.6, w: W - 2 * M - 0.56, h: 0.42, fontSize: 15.5, bold: true, color: CHERRY, margin: 0, valign: 'middle' }));
  s.addText('مشتری ۹۰ روزه پول را ۹۰ روز بیشتر نگه می‌دارد و تقریباً همان قیمت مشتری نقدی را می‌پردازد',
    rtl({ x: M + 0.28, y: 5.0, w: W - 2 * M - 0.56, h: 0.4, fontSize: 14.5, color: INK, margin: 0, valign: 'middle' }));
  s.addText('پس هزینهٔ پول را خودمان به حساب مشتری می‌گذاریم، و این دوباره‌شماری نیست',
    rtl({ x: M + 0.28, y: 5.38, w: W - 2 * M - 0.56, h: 0.4, fontSize: 14.5, color: INK, margin: 0, valign: 'middle' }));
  s.addText('۱٬۷۱۴ و ۱٬۵۰۳ سلول «کد کالا × ماه» که هر دو شرط پرداخت را هم‌زمان دارند.',
    rtl({ x: M, y: 6.15, w: W - 2 * M, h: 0.35, fontSize: 12, color: MUTE, margin: 0 }));
  s.addNotes('داوران صریح خواستند این آزمون را خودمان اجرا کنیم و نتیجه را نشان دهیم. این اسلاید همان است.');
}

/* ═════════════════════════ ۵ — دمو ۱: برش فهرست */
{
  const s = slide();
  title(s, 'دمو ۱ — از ۶۴۴ حساب به ۴۰ حسابی که وقت تیم را می‌ارزند', false,
    'برش روی «پول در حرکت»: بیشینهٔ سه مسیر — نگهداشت، رشد، یا اصلاح شرایط پرداخت.');
  const boxes = [
    ['رشد بده', '۹۴', 'سود واقعی بالای میانه و ظرفیت رشد باز', GOOD],
    ['حفظ کن', '۲۱۸', 'سودآور و سهم سبد تقریباً پر — تلاش کم، مراقبت زیاد', NAVY],
    ['اصلاح کن', '۶۲', 'حجم هست، سود واقعی نیست — بازمذاکره با مهلت', WARN],
    ['کاهش بده', '۲۵۰', 'سود واقعی منفی و ظرفیت کم — تماس کم‌بسامد', CHERRY],
  ];
  const bw = (W - 2 * M - 0.36) / 4;
  boxes.forEach(([h, n, d, c], i) => {
    const x = W - M - bw - i * (bw + 0.12);
    card(s, x, 1.95, bw, 2.05, 'F4F6FB', 'DDE3F0');
    s.addShape(P.ShapeType.rect, { x, y: 1.95, w: bw, h: 0.07, fill: { color: c }, line: { color: c } });
    s.addText(h, rtl({ x: x + 0.18, y: 2.14, w: bw - 0.36, h: 0.4, fontSize: 17, bold: true, color: c, margin: 0 }));
    s.addText(n + ' مشتری', rtl({ x: x + 0.18, y: 2.58, w: bw - 0.36, h: 0.45, fontSize: 22, bold: true, color: INK, margin: 0 }));
    s.addText(d, rtl({ x: x + 0.18, y: 3.06, w: bw - 0.36, h: 0.85, fontSize: 11.5, color: MUTE, margin: 0, valign: 'top' }));
  });
  card(s, M, 4.25, W - 2 * M, 1.95, NAVY, NAVY);
  s.addText('', { x: 0, y: 0, w: 0.01, h: 0.01 });
  s.addText('۴۰ حساب فهرست تمرکز', rtl({ x: M + 0.3, y: 4.42, w: 4.6, h: 0.45, fontSize: 18, bold: true, color: WHITE, margin: 0 }));
  const facts = ['۶۴٫۶ درصد فروش سبد را پوشش می‌دهد',
    '۱۴۹٫۳ از ۲۴۲٫۶ میلیون پول در حرکت را می‌گیرد',
    '۲۲۴ حساب با سود واقعی منفی ۴۶٫۹ میلیون کنار گذاشته می‌شوند'];
  const fw = (W - 2 * M - 0.6 - 0.4) / 3;
  facts.forEach((t, i) => s.addText(t, rtl({ x: W - M - 0.3 - fw - i * (fw + 0.2), y: 4.88,
    w: fw, h: 0.62, fontSize: 13.5, color: WHITE, margin: 0, align: 'center', valign: 'middle' })));
  s.addText('هر حذف دلیل دارد و می‌گوید چه چیزی نظر ما را عوض می‌کند — مثلاً تغییر شرط پرداخت به نقدی، یا به‌روز شدن برآورد سهم سبد',
    rtl({ x: M + 0.3, y: 5.58, w: W - 2 * M - 0.6, h: 0.5, fontSize: 12.5, color: ICE, margin: 0, valign: 'middle' }));
  s.addNotes('روی داشبورد: تب فهرست تمرکز. لغزندهٔ نرخ را جابه‌جا می‌کنیم تا ببینند رتبه‌بندی درجا عوض می‌شود.');
}

/* ═════════════════════════ ۶ — دمو ۲: یک حساب */
{
  const s = slide();
  title(s, 'دمو ۲ — یک حساب، از داده تا اقدام', false,
    'C_245948 — رتبهٔ یک ارزش طول عمر، و در فهرست تمرکز جایگاه اول.');
  const steps = [
    ['داده', 'فروش، وصول، شکایت، آفر و سهم سبد از پنج سامانه'],
    ['سیگنال', '۹۳ روز پول قفل‌شده در برابر مبنای ۱۶ روزهٔ سبد'],
    ['تفسیر', 'حاشیهٔ ناخالص ۱۶٫۱٪ منهای هزینهٔ پول ۱۲٫۴٪ = سود واقعی ۳٫۶٪'],
    ['اقدام', 'مذاکرهٔ شرایط پرداخت — سالانه ۱۵٫۰ میلیون سود آزاد می‌شود'],
    ['شاهد', 'کلیک روی «منبع»: شیت، شناسهٔ رکورد، تاریخ و فیلد'],
  ];
  const rh = 0.72, y0 = 2.0;
  steps.forEach(([h, d], i) => {
    const y = y0 + i * (rh + 0.16);
    s.addShape(P.ShapeType.ellipse, { x: W - M - 0.56, y: y + 0.09, w: 0.54, h: 0.54,
      fill: { color: i === 3 ? CHERRY : NAVY }, line: { color: i === 3 ? CHERRY : NAVY } });
    s.addText(String(i + 1), { x: W - M - 0.56, y: y + 0.09, w: 0.54, h: 0.54, fontSize: 15,
      bold: true, color: WHITE, align: 'center', valign: 'middle', margin: 0, fontFace: F });
    s.addText(h, rtl({ x: W - M - 2.35, y: y + 0.1, w: 1.65, h: 0.5, fontSize: 15, bold: true,
      color: i === 3 ? CHERRY : NAVY, margin: 0, valign: 'middle' }));
    s.addText(d, rtl({ x: M, y: y + 0.1, w: W - 2 * M - 2.5, h: 0.5, fontSize: 14,
      color: INK, margin: 0, valign: 'middle' }));
  });
  s.addNotes('روی داشبورد: کلیک روی سطر رسیدگی، کشو باز می‌شود، سیگنال حوزهٔ مشکل، اقدام و رفرنس.');
}

/* ═════════════════════════ ۶.۵ — دمو ۳: آفر — اهرم، مهلت است نه تخفیف */
{
  const s = slide();
  title(s, 'در آفر، اهرم مهلت است نه تخفیف', false,
    'پنج فرضیه را روی ۲٬۵۰۰ آفر تاریخی آزمودیم. چهارتا رد شد، یکی ماند.');
  s.addChart(P.ChartType.bar, [{
    /* برچسب محور که با عدد دورقمی شروع شود، در بازنمایی دوجهته عدد را به
       انتهای رشته پرت می‌کند. RLM ابتدای هر برچسب، جهت پاراگراف را قفل می‌کند. */
    name: 'نرخ پذیرش', labels: ['۴ تا ۷ روز', '۸ تا ۱۰ روز', '۱۱ تا ۱۴ روز',
      '۱۵ تا ۱۸ روز', '۱۹ تا ۲۱ روز', '۲۲ روز و بیشتر'].map(t => '\u200F' + t),
    values: [53.1, 60.6, 63.1, 46.5, 42.7, 42.7],
  }], {
    x: W / 2 + 0.12, y: 1.95, w: W / 2 - M - 0.12, h: 3.05, barDir: 'col',
    chartColors: ['9AA3BC', GOOD, GOOD, '9AA3BC', '9AA3BC', '9AA3BC'],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 11,
    dataLabelFontFace: F, dataLabelColor: INK, dataLabelFormatCode: '0.0"٪"',
    catAxisLabelFontFace: F, catAxisLabelFontSize: 10, catAxisLabelColor: INK,
    catAxisOrientation: 'maxMin',
    valAxisLabelFontFace: F, valAxisLabelFontSize: 9, valAxisLabelColor: MUTE,
    valAxisMaxVal: 75, valGridLine: { color: 'E8EBF2', size: 1 },
    catGridLine: { style: 'none' }, showLegend: false,
  });
  const rows = [
    ['فرضیه', 'آزمون', 'حکم'],
    ['عمق تخفیف', 'p = ۰٫۹۰', 'رد'],
    ['دلیل آفر', 'p = ۰٫۵۶', 'رد'],
    ['نوع آفر', 'p = ۰٫۱۴', 'رد'],
    ['سابقهٔ پذیرش خودش', 'p = ۰٫۳۵', 'رد'],
    ['طول اعتبار آفر', 'p < ۰٫۰۰۰۱', 'ماند'],
  ];
  s.addTable(rows.map((r, ri) => [...r].reverse().map(c => ({
    text: c,
    options: { fontFace: F, rtlMode: true, align: 'right', fontSize: ri === 0 ? 11.5 : 13,
      bold: ri === 0 || ri === 5, color: ri === 0 ? WHITE : (ri === 5 ? GOOD : INK),
      fill: { color: ri === 0 ? NAVY : (ri === 5 ? 'EAF6EF' : (ri % 2 ? 'F4F6FB' : PAPER)) },
      margin: 5 },
  }))), { x: M, y: 1.95, w: W / 2 - M - 0.12, colW: [1.15, 1.55, 2.83], rowH: 0.44 });
  card(s, M, 4.62, W / 2 - M - 0.12, 1.28, 'EAF6EF', 'C3E3D2');
  s.addText('اثر در هر سه نوع آفر جداگانه تکرار می‌شود و با عمق تخفیف هم‌بسته نیست',
    rtl({ x: M + 0.22, y: 4.74, w: W / 2 - M - 0.56, h: 1.04, fontSize: 13, color: INK,
      margin: 0, valign: 'middle' }));
  card(s, M, 6.02, W - 2 * M, 0.92, NAVY, NAVY);
  s.addText('پذیرش داخل پنجرهٔ ۸ تا ۱۴ روزه ۶۲٫۲٪ و بیرون از آن ۴۵٫۲٪ — شرکت امروز میانهٔ مهلت ۱۸ روز می‌دهد. ۱٫۷ میلیون ارزش انتظاری، فقط از تغییر مهلت.',
    rtl({ x: M + 0.3, y: 6.1, w: W - 2 * M - 0.6, h: 0.76, fontSize: 14, color: WHITE,
      margin: 0, valign: 'middle' }));
  s.addNotes('نکتهٔ صداقت اگر پرسیدند: آزمون ششمی هم زدیم — آیا پذیرش آفر به خرید بیشتر منجر می‌شود؟ ۷۰٫۲٪ در برابر ۶۹٫۶٪، فیشر p=۰٫۸۶. پس ستون پول را «آوردهٔ هدف» نامیدیم، نه لیفت. همین قید زیر هر کارت آفر نوشته می‌شود.');
}

/* ═════════════════════════ ۷ — چطور کار می‌کند */
{
  const s = slide(true);
  title(s, 'چطور کار می‌کند', true, 'پنج لایه؛ هر لایه با کد قطعی، و مدل زبانی فقط در جایی که ارزش می‌سازد.');
  const layers = [
    ['لایهٔ داده', '۱۶ شیت، ۷ قاعدهٔ یکپارچه‌سازی، موتور «در تاریخ» با راست‌سانسور'],
    ['موتور سیگنال', '۱۸ قاعده و ۲۱ کد سیگنال، ۶ پیش‌بینی روی نرخ پایهٔ تجربی'],
    ['اقتصاد حساب', 'هزینهٔ پول، حاشیهٔ واقعی، ذخیرهٔ مطالبات، فهرست تمرکز'],
    ['موتور اقدام', 'فوریت × سهم مبلغ، با مالک مشخص و گام فوری'],
    ['لایهٔ اعتماد', '۱۷٬۶۳۶ رفرنس، فرض‌ها و عدم‌قطعیت روی صفحه'],
  ];
  const cw = (W - 2 * M - 0.4) / 5;
  layers.forEach(([h, d], i) => {
    const x = W - M - cw - i * (cw + 0.1);
    card(s, x, 2.05, cw, 2.5, '2A3670', '3C4C8E');
    s.addText(h, rtl({ x: x + 0.16, y: 2.22, w: cw - 0.32, h: 0.75, fontSize: 14.5, bold: true,
      color: ICE, margin: 0, valign: 'top' }));
    s.addText(d, rtl({ x: x + 0.16, y: 3.0, w: cw - 0.32, h: 1.4, fontSize: 11.5, color: WHITE,
      margin: 0, valign: 'top' }));
  });
  card(s, M, 4.8, W - 2 * M, 1.35, 'A4161A', 'A4161A');
  s.addText('قاعدهٔ سخت: مدل زبانی هیچ عددی تولید نمی‌کند. ۱۲ ابزار پایتونی را صدا می‌زند و خروجی‌شان را روایت می‌کند — فهرست ابزارها زیر هر پاسخ دیده می‌شود.',
    rtl({ x: M + 0.3, y: 4.95, w: W - 2 * M - 0.6, h: 1.05, fontSize: 15, bold: true, color: WHITE, margin: 0, valign: 'middle' }));
  s.addNotes('اگر کلید API نباشد یا شبکه قطع شود، همان ۱۲ ابزار با موتور قاعده‌محور صدا زده می‌شوند. دمو نمی‌میرد.');
}

/* ═════════════════════════ ۸ — اعتبارسنجی */
{
  const s = slide();
  title(s, 'اعتبارسنجی — زنجیرهٔ تصمیم را آزمودیم، نه فقط مدل را', false,
    'داوران گفتند «سه حساب را بردارید و با دست حساب کنید». همین کار را کردیم.');
  const cols = [
    ['۳۰ از ۳۰', 'عدد در آزمون دستی منطبق', GOOD, 'سه حساب با سه پروفایل متفاوت، مستقل از موتور محصول دوباره حساب شد'],
    ['۸۵ از ۸۵', 'آزمون خودکار سبز', GOOD, 'تجمیع، نشتی زمانی، اتحادهای حسابداری، رفرنس، صداقت الگو'],
    ['AUC ۰٫۸۳۱', 'مدل ماندگاری، خارج از زمان', NAVY, 'و صریح می‌گوییم رکود تنها با ۰٫۸۵۲ بهتر است'],
    ['۲۷٪', 'خطای بک‌تست پیش‌بینی فروش', WARN, 'سود ۲۲٪ و وصول ۱۹٪ — خارج از نمونه: ضریب اصلاح هر دور فقط از دوره‌های پیش از خودش'],
  ];
  const cw = (W - 2 * M - 0.36) / 4;
  cols.forEach(([n, l, c, d], i) => {
    const x = W - M - cw - i * (cw + 0.12);
    card(s, x, 2.0, cw, 2.65, 'F4F6FB', 'DDE3F0');
    s.addText(n, rtl({ x: x + 0.14, y: 2.2, w: cw - 0.28, h: 0.6, fontSize: 22, bold: true,
      color: c, align: 'center', margin: 0, valign: 'middle' }));
    s.addText(l, rtl({ x: x + 0.14, y: 2.82, w: cw - 0.28, h: 0.62, fontSize: 12.5, color: INK,
      align: 'center', margin: 0, valign: 'top' }));
    s.addText(d, rtl({ x: x + 0.14, y: 3.5, w: cw - 0.28, h: 1.05, fontSize: 11, color: MUTE,
      align: 'center', margin: 0, valign: 'top' }));
  });
  card(s, M, 4.9, W - 2 * M, 1.25, 'F4F6FB', 'DDE3F0');
  s.addText('و آنچه کار نکرد را هم گزارش می‌کنیم: سه الگو آزموده و رد شدند — شکایت، درخواست توسعه و چک برگشتی هیچ‌کدام پیش‌بین مستقل ریزش نبودند.',
    rtl({ x: M + 0.3, y: 5.05, w: W - 2 * M - 0.6, h: 0.95, fontSize: 14, color: INK, margin: 0, valign: 'middle' }));
  s.addNotes('تب «الگوها، مدل و اعتبارسنجی» جدول آزمون دستی را عدد به عدد نشان می‌دهد. یک کلیک فاصله دارد.');
}

/* ═════════════════════════ ۹ — ارزش و محدودیت */
{
  const s = slide();
  title(s, 'چه چیزی بهتر می‌شود، و کجا نمی‌توانیم ادعا کنیم');
  card(s, W / 2 + 0.12, 1.95, W / 2 - M - 0.12, 3.75, 'EFF7F1', 'CDE4D5');
  s.addText('ارزش', rtl({ x: W / 2 + 0.37, y: 2.12, w: W / 2 - M - 0.62, h: 0.45, fontSize: 19, bold: true, color: GOOD, margin: 0 }));
  bullets(s, W / 2 + 0.37, 2.68, W / 2 - M - 0.62, [
    'فهرست هفتگی از ۶۴۴ به ۴۰ حساب، با دلیل هر حذف',
    'رتبه‌بندی روی سود واقعی، نه فروش یا حاشیهٔ ناخالص',
    'بزرگ‌ترین اهرم شناسایی شد: شرایط پرداخت، نه رشد حجم',
    'هر ادعا در سه ثانیه تا رکورد منبع قابل ردیابی است',
  ], 13.5, INK);
  card(s, M, 1.95, W / 2 - M - 0.12, 3.75, 'FDF6EC', 'F0DCC0');
  s.addText('محدودیت', rtl({ x: M + 0.25, y: 2.12, w: W / 2 - M - 0.62, h: 0.45, fontSize: 19, bold: true, color: WARN, margin: 0 }));
  bullets(s, M + 0.25, 2.68, W / 2 - M - 0.62, [
    'نرخ ۴٪ ماهانه فرض بیرونی است، نه یافتهٔ داده — در داشبورد لغزنده است',
    '۶۸ درصد خطوط بهای تمام‌شدهٔ برآوردی دارند؛ حاشیه حدود ۵ واحد خوش‌بینانه‌تر',
    'سهم از سبد برآورد کارشناس است، نه اندازه‌گیری',
    'هزینهٔ خدمت‌دهی از شمارش رویداد ساخته شده، نه از دادهٔ هزینه',
  ], 13.5, INK);
  card(s, M, 5.9, W - 2 * M, 0.95, NAVY, NAVY);
  s.addText('گام بعدی با یک هفتهٔ دیگر: ثبت بازخورد اقدام، تا وزن‌های فوریت را از نتیجهٔ واقعی بیاموزیم نه از قضاوت.',
    rtl({ x: M + 0.3, y: 5.98, w: W - 2 * M - 0.6, h: 0.78, fontSize: 14.5, color: WHITE, margin: 0, valign: 'middle' }));
  s.addNotes('آنچه به نرخ ۴٪ وابسته نیست: پول ۵۴ روز قفل می‌ماند و مارک‌آپ اعتبار در قیمت ثبت نشده. این دو اندازه‌گیری‌اند.');
}

/* ═════════════════════════ ۱۰ — پایان */
{
  const s = slide(true);
  s.addText('یک تصمیم. قابل دفاع. در حال کار.', rtl({ x: M, y: 2.5, w: W - 2 * M, h: 1.0,
    fontSize: 38, bold: true, color: WHITE, margin: 0 }));
  s.addText('داده ← سیگنال ← معنا ← اقدام، با شاهد پیوست.',
    rtl({ x: M, y: 3.5, w: W - 2 * M, h: 0.5, fontSize: 17, color: ICE, margin: 0 }));
  card(s, M, 4.3, W - 2 * M, 1.2, '2A3670', '3C4C8E');
  s.addText('پیوست یک کلیک فاصله دارد: نقشهٔ داده، تعریف متریک‌ها، منطق امتیازدهی، بک‌تست، آزمون دستی و محدودیت‌ها — در مستند فنی ۳۸ بخشی.',
    rtl({ x: M + 0.3, y: 4.45, w: W - 2 * M - 0.6, h: 0.9, fontSize: 14, color: WHITE, margin: 0, valign: 'middle' }));
  s.addNotes('پرسش و پاسخ. اگر پرسیدند «از کجا می‌دانید این اقدام درست است؟»: پول در حرکت، مسیر آن، و رفرنس رکورد منبع.');
}

P.writeFile({ fileName: 'presentation.pptx' }).then(f => console.log('نوشته شد:', f));
