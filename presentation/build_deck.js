// Builds the Physiotherapy Department introduction deck (Arabic, RTL).
// Run: NODE_PATH=<dir with pptxgenjs, react-icons, react, react-dom, sharp> node build_deck.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const SKILL = process.env.PPTX_SKILL_DIR;
const OUT = path.join(__dirname, "قسم_العلاج_الطبيعي_العجيلات.pptx");

const THEME = {
  name: "Physio Ajaylat",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "1B2B34", lt1: "FFFFFF", dk2: "0E5E6F", lt2: "EAF4F5",
    accent1: "0E5E6F", accent2: "3A9CA8", accent3: "F2A65A",
    accent4: "7FC8C2", accent5: "5B6B73", accent6: "D9534F",
    hlink: "0E5E6F", folHlink: "3A9CA8",
  },
};
const HEX = THEME.colors;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + color, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const RTL = { rtlMode: true, lang: "ar-LY", align: "right" };

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "قسم العلاج الطبيعي - كلية العلوم الصحية العجيلات";
  pres.author = "قسم العلاج الطبيعي";
  const C = pres.SchemeColor;

  // ---------- Layouts ----------
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: C.accent1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.4,
          fontSize: 44, bold: true, color: C.background1, align: "right", valign: "middle" }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    margin: [0.5, 0.6, 0.6, 0.6],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.13, h: 0.9,
          fontSize: 36, bold: true, color: C.accent1, align: "right", valign: "middle" }, text: "" } },
      { text: { text: "قسم العلاج الطبيعي | كلية العلوم الصحية العجيلات - جامعة الزاوية",
          options: { x: 0.6, y: 6.95, w: 8, h: 0.35, fontSize: 10, color: C.accent5, align: "left", rtlMode: true } } },
    ],
    slideNumber: { x: 12.2, y: 6.95, w: 0.6, h: 0.35, fontSize: 10, color: C.accent5, align: "right" },
  });

  const addTitle = (slide, t) => slide.addText(t, { placeholder: "title", rtlMode: true, lang: "ar-LY", align: "right" });

  // icon in colored circle; returns nothing
  const circleIcon = async (slide, Comp, x, y, d, fill, iconColor, name) => {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: name + " circle" });
    const pad = d * 0.25;
    slide.addImage({ data: await icon(Comp, iconColor), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name + " icon", altText: name });
  };

  // ---------- 1. Title ----------
  pres.addSection({ title: "الافتتاح" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "الافتتاح" });
    // decorative large soft circles (motif)
    s.addShape(pres.shapes.OVAL, { x: -1.6, y: 3.6, w: 5.5, h: 5.5, fill: { color: C.accent2, transparency: 60 }, line: { color: C.accent2, transparency: 100 }, objectName: "deco circle 1" });
    s.addShape(pres.shapes.OVAL, { x: 1.4, y: -1.8, w: 3.2, h: 3.2, fill: { color: C.accent4, transparency: 75 }, line: { color: C.accent4, transparency: 100 }, objectName: "deco circle 2" });
    await circleIcon(s, fa.FaUserMd, 1.2, 2.0, 2.4, HEX.lt1, HEX.accent1, "physiotherapy");
    s.addText("جامعة الزاوية  •  كلية العلوم الصحية العجيلات", { x: 4.2, y: 1.2, w: 8.3, h: 0.6, fontSize: 20, color: C.accent4, isTextBox: true, ...RTL, objectName: "university" });
    s.addText("قسم العلاج الطبيعي", { placeholder: "title", ...RTL });
    s.addText("التعريف بالقسم: الرؤية • الرسالة • الأهداف", { x: 4.2, y: 3.7, w: 8.3, h: 0.6, fontSize: 22, color: C.background1, isTextBox: true, ...RTL, objectName: "subtitle" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.7, y: 4.9, w: 4.8, h: 1.1, rectRadius: 0.15, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: "head card" });
    s.addText([
      { text: "رئيس القسم", options: { fontSize: 14, color: C.text1, breakLine: true } },
      { text: "د. سناء بلق", options: { fontSize: 24, bold: true, color: C.text1 } },
    ], { x: 7.9, y: 4.95, w: 4.4, h: 1.0, isTextBox: true, valign: "middle", ...RTL, objectName: "head name" });
    s.addNotes("مرحباً بكم. يسعدنا تقديم تعريف بقسم العلاج الطبيعي بكلية العلوم الصحية العجيلات - جامعة الزاوية، برئاسة الدكتورة سناء بلق.");
  }

  // ---------- 2. About ----------
  pres.addSection({ title: "التعريف بالقسم" });
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "التعريف بالقسم" });
    addTitle(s, "نبذة عن القسم");
    s.addText([
      { text: "قسم العلاج الطبيعي أحد الأقسام العلمية بكلية العلوم الصحية العجيلات - جامعة الزاوية، ويُعنى بإعداد أخصائيين مؤهلين علمياً وعملياً في مجال التأهيل والعلاج الطبيعي.", options: { breakLine: true } },
      { text: "يجمع البرنامج بين العلوم الطبية الأساسية والعلوم التخصصية والتدريب السريري في المستشفيات ومراكز التأهيل.", options: { breakLine: true } },
      { text: "يسهم القسم في خدمة المجتمع المحلي بمنطقة العجيلات وما حولها من خلال نشر الوعي الصحي ودعم برامج الوقاية والتأهيل." },
    ], { x: 4.4, y: 1.55, w: 8.33, h: 4.6, fontSize: 18, color: C.text1, paraSpaceAfter: 14, valign: "top", isTextBox: true, ...RTL, objectName: "about text" });
    // left visual: stat-like cards
    const cards = [
      [fa.FaUniversity, "جامعة الزاوية", "مؤسسة أكاديمية حكومية"],
      [fa.FaClinicMedical, "كلية العلوم الصحية", "العجيلات"],
      [fa.FaHandsHelping, "التأهيل والعلاج", "تخصص صحي تطبيقي"],
    ];
    for (let i = 0; i < cards.length; i++) {
      const y = 1.55 + i * 1.6;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 3.4, h: 1.35, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "about card " + (i + 1) });
      await circleIcon(s, cards[i][0], 2.95, y + 0.25, 0.85, HEX.accent1, HEX.lt1, "about " + (i + 1));
      s.addText([
        { text: cards[i][1], options: { bold: true, fontSize: 16, color: C.accent1, breakLine: true } },
        { text: cards[i][2], options: { fontSize: 12, color: C.accent5 } },
      ], { x: 0.7, y: y + 0.15, w: 2.15, h: 1.05, valign: "middle", isTextBox: true, margin: 0, ...RTL, objectName: "about card text " + (i + 1) });
    }
    s.addNotes("نبذة تعريفية عامة عن القسم ودوره الأكاديمي والمجتمعي.");
  }

  // ---------- 3. Vision ----------
  pres.addSection({ title: "الرؤية والرسالة" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "الرؤية والرسالة" });
    s.addShape(pres.shapes.OVAL, { x: 9.8, y: -2.0, w: 5.5, h: 5.5, fill: { color: C.accent2, transparency: 60 }, line: { color: C.accent2, transparency: 100 }, objectName: "deco circle" });
    await circleIcon(s, fa.FaEye, 10.9, 0.9, 1.6, HEX.lt1, HEX.accent1, "vision");
    s.addText("رؤيتنا", { x: 0.8, y: 1.1, w: 9.6, h: 1.2, fontSize: 44, bold: true, color: C.background1, isTextBox: true, ...RTL, objectName: "vision title" });
    s.addText("أن يكون قسم العلاج الطبيعي قسماً رائداً ومتميزاً على المستوى المحلي والإقليمي في التعليم والتدريب والبحث العلمي في مجال العلاج الطبيعي والتأهيل، بما يسهم في الارتقاء بالرعاية الصحية وجودة الحياة في المجتمع.",
      { x: 0.8, y: 2.9, w: 11.7, h: 2.6, fontSize: 26, color: C.background1, italic: true, valign: "top", isTextBox: true, ...RTL, lineSpacingMultiple: 1.2, objectName: "vision text" });
    s.addNotes("الرؤية: الريادة والتميز في التعليم والتدريب والبحث العلمي في العلاج الطبيعي.");
  }

  // ---------- 4. Mission ----------
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "الرؤية والرسالة" });
    addTitle(s, "رسالتنا");
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 1.5, w: 12.13, h: 1.9, rectRadius: 0.15, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "mission card" });
    await circleIcon(s, fa.FaEnvelopeOpenText, 11.4, 1.8, 1.2, HEX.accent1, HEX.lt1, "mission");
    s.addText("إعداد أخصائيين في العلاج الطبيعي يتمتعون بالكفاءة العلمية والمهارة العملية والالتزام بأخلاقيات المهنة، من خلال برامج تعليمية وتدريبية متطورة وبحث علمي هادف، والمشاركة الفاعلة في خدمة المجتمع وتلبية احتياجاته الصحية.",
      { x: 0.9, y: 1.6, w: 10.2, h: 1.7, fontSize: 18, color: C.text1, valign: "middle", isTextBox: true, ...RTL, objectName: "mission text" });
    const pillars = [
      [fa.FaGraduationCap, "تعليم متميز", "مناهج حديثة تواكب التطور العلمي"],
      [fa.FaHospital, "تدريب سريري", "ممارسة عملية في بيئات صحية حقيقية"],
      [fa.FaFlask, "بحث علمي", "أبحاث تطبيقية تخدم الممارسة"],
      [fa.FaUsers, "خدمة المجتمع", "توعية ووقاية وتأهيل"],
    ];
    const w = 2.8, gap = 0.31;
    for (let i = 0; i < 4; i++) {
      const x = 12.73 - (i + 1) * w - i * gap; // RTL order: first pillar on the right
      await circleIcon(s, pillars[i][0], x + (w - 1.0) / 2, 3.85, 1.0, HEX.accent2, HEX.lt1, "pillar " + (i + 1));
      s.addText([
        { text: pillars[i][1], options: { bold: true, fontSize: 18, color: C.accent1, breakLine: true } },
        { text: pillars[i][2], options: { fontSize: 14, color: C.accent5 } },
      ], { x, y: 5.0, w, h: 1.4, valign: "top", isTextBox: true, rtlMode: true, lang: "ar-LY", align: "center", objectName: "pillar text " + (i + 1) });
    }
    s.addNotes("الرسالة تقوم على أربع ركائز: التعليم، التدريب السريري، البحث العلمي، وخدمة المجتمع.");
  }

  // ---------- 5. Goals ----------
  pres.addSection({ title: "الأهداف" });
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "الأهداف" });
    addTitle(s, "أهداف القسم");
    const goals = [
      [fa.FaUserGraduate, "إعداد كوادر مؤهلة", "تخريج أخصائيين أكفاء قادرين على تقييم المرضى ووضع الخطط العلاجية وتنفيذها."],
      [fa.FaStethoscope, "تنمية المهارات السريرية", "تزويد الطلاب بالمهارات العملية عبر التدريب الميداني في المستشفيات ومراكز التأهيل."],
      [fa.FaMicroscope, "تشجيع البحث العلمي", "دعم البحوث في مجالات العلاج الطبيعي وتطبيق الممارسة المبنية على الدليل."],
      [fa.FaBalanceScale, "ترسيخ أخلاقيات المهنة", "غرس قيم الأمانة والمسؤولية واحترام المريض والعمل ضمن الفريق الصحي."],
      [fa.FaHandHoldingHeart, "خدمة المجتمع", "المساهمة في التوعية الصحية والوقاية من الإصابات والإعاقات وتأهيل المصابين."],
      [fa.FaSyncAlt, "التطوير المستمر", "تحديث المناهج وتأهيل أعضاء هيئة التدريس ومواكبة المستجدات العالمية."],
    ];
    const cw = 3.85, ch = 2.45, gx = 0.29, gy = 0.3;
    for (let i = 0; i < goals.length; i++) {
      const col = i % 3, row = Math.floor(i / 3);
      const x = 12.73 - (col + 1) * cw - col * gx; // RTL
      const y = 1.45 + row * (ch + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "goal card " + (i + 1) });
      await circleIcon(s, goals[i][0], x + cw - 0.95, y + 0.2, 0.75, HEX.accent1, HEX.lt1, "goal " + (i + 1));
      s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.2, y: y + 0.2, w: 0.9, h: 0.6, fontSize: 24, bold: true, color: C.accent3, isTextBox: true, margin: 0, objectName: "goal num " + (i + 1) });
      s.addText(goals[i][1], { x: x + 0.2, y: y + 1.0, w: cw - 0.4, h: 0.45, fontSize: 17, bold: true, color: C.accent1, isTextBox: true, margin: 0, ...RTL, objectName: "goal title " + (i + 1) });
      s.addText(goals[i][2], { x: x + 0.2, y: y + 1.45, w: cw - 0.4, h: 0.9, fontSize: 13, color: C.text1, valign: "top", isTextBox: true, margin: 0, ...RTL, objectName: "goal text " + (i + 1) });
    }
    s.addNotes("ستة أهداف رئيسية توجه عمل القسم.");
  }

  // ---------- 6. Fields ----------
  pres.addSection({ title: "البرنامج الدراسي" });
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "البرنامج الدراسي" });
    addTitle(s, "مجالات العلاج الطبيعي التي يغطيها البرنامج");
    const fields = [
      [fa.FaBone, "العظام والعضلات", "الكسور، آلام الظهر والرقبة، خشونة المفاصل"],
      [fa.FaBrain, "الأعصاب", "الجلطات الدماغية، إصابات الحبل الشوكي"],
      [fa.FaHeartbeat, "القلب والجهاز التنفسي", "التأهيل القلبي والرئوي"],
      [fa.FaChild, "الأطفال", "الشلل الدماغي وتأخر النمو الحركي"],
      [fa.FaRunning, "الإصابات الرياضية", "الوقاية والتأهيل والعودة للنشاط"],
      [fa.FaWheelchair, "كبار السن والتأهيل", "الحفاظ على الحركة والاستقلالية"],
    ];
    const cw = 5.9, ch = 1.45, gx = 0.33, gy = 0.3;
    for (let i = 0; i < fields.length; i++) {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 12.73 - (col + 1) * cw - col * gx;
      const y = 1.5 + row * (ch + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.12, fill: { color: C.background1 }, line: { color: C.accent4, width: 1.25 }, objectName: "field card " + (i + 1) });
      await circleIcon(s, fields[i][0], x + cw - 1.25, y + 0.2, 1.05, HEX.accent2, HEX.lt1, "field " + (i + 1));
      s.addText([
        { text: fields[i][1], options: { bold: true, fontSize: 18, color: C.accent1, breakLine: true } },
        { text: fields[i][2], options: { fontSize: 14, color: C.accent5 } },
      ], { x: x + 0.25, y: y + 0.15, w: cw - 1.7, h: ch - 0.3, valign: "middle", isTextBox: true, margin: 0, ...RTL, objectName: "field text " + (i + 1) });
    }
    s.addNotes("يغطي البرنامج أهم مجالات العلاج الطبيعي التخصصية.");
  }

  // ---------- 7. Study journey ----------
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "البرنامج الدراسي" });
    addTitle(s, "المسيرة التعليمية للطالب");
    const steps = [
      [fa.FaBookMedical, "العلوم الأساسية", "التشريح، وظائف الأعضاء، الفيزياء الحيوية"],
      [fa.FaDumbbell, "العلوم التخصصية", "العلاج بالتمرين، العلاج اليدوي، الوسائل الكهربائية"],
      [fa.FaHospitalUser, "التدريب السريري", "تطبيق عملي بالمستشفيات ومراكز التأهيل"],
      [fa.FaAward, "التخرج والامتياز", "مشروع التخرج والاستعداد لسوق العمل"],
    ];
    const n = steps.length, w = 2.75, gap = 0.38;
    const lineY = 2.55;
    s.addShape(pres.shapes.LINE, { x: 1.9, y: lineY, w: 9.5, h: 0, line: { color: C.accent4, width: 3, dashType: "dash" }, objectName: "timeline line" });
    for (let i = 0; i < n; i++) {
      const x = 12.73 - (i + 1) * w - i * gap;
      const d = 1.3;
      await circleIcon(s, steps[i][0], x + (w - d) / 2, lineY - d / 2, d, i === n - 1 ? HEX.accent3 : HEX.accent1, HEX.lt1, "step " + (i + 1));
      s.addText("المرحلة " + (i + 1), { x, y: 3.45, w, h: 0.4, fontSize: 14, color: C.accent3, bold: true, isTextBox: true, rtlMode: true, lang: "ar-LY", align: "center", objectName: "step label " + (i + 1) });
      s.addText([
        { text: steps[i][1], options: { bold: true, fontSize: 20, color: C.accent1, breakLine: true } },
        { text: steps[i][2], options: { fontSize: 14, color: C.text1 } },
      ], { x, y: 3.9, w, h: 1.7, valign: "top", isTextBox: true, rtlMode: true, lang: "ar-LY", align: "center", paraSpaceAfter: 6, objectName: "step text " + (i + 1) });
    }
    s.addText("يتدرج الطالب من الأساس النظري إلى الممارسة السريرية تحت إشراف أعضاء هيئة التدريس.", { x: 0.6, y: 5.95, w: 12.13, h: 0.5, fontSize: 15, italic: true, color: C.accent5, isTextBox: true, ...RTL, objectName: "journey note" });
    s.addNotes("المراحل عامة؛ تُضبط التفاصيل الدقيقة (عدد الفصول والمقررات) وفق اللائحة الدراسية المعتمدة بالقسم.");
  }

  // ---------- 8. Graduate profile & careers ----------
  pres.addSection({ title: "الخريج وسوق العمل" });
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "الخريج وسوق العمل" });
    addTitle(s, "خريج القسم ومجالات عمله");
    // right column: graduate attributes
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.85, y: 1.5, w: 5.88, h: 4.95, rectRadius: 0.15, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "attributes card" });
    await circleIcon(s, fa.FaUserCheck, 11.65, 1.75, 0.85, HEX.accent1, HEX.lt1, "attributes");
    s.addText("صفات الخريج", { x: 7.1, y: 1.8, w: 4.4, h: 0.75, fontSize: 22, bold: true, color: C.accent1, isTextBox: true, margin: 0, ...RTL, objectName: "attributes title" });
    s.addText([
      { text: "تقييم الحالة وتشخيص المشكلة الحركية", options: { bullet: true, breakLine: true } },
      { text: "تصميم خطة علاجية وتنفيذها ومتابعتها", options: { bullet: true, breakLine: true } },
      { text: "التواصل الفعّال مع المريض والفريق الصحي", options: { bullet: true, breakLine: true } },
      { text: "الالتزام بأخلاقيات المهنة", options: { bullet: true, breakLine: true } },
      { text: "التعلم المستمر والبحث العلمي", options: { bullet: true } },
    ], { x: 7.1, y: 2.75, w: 5.4, h: 3.5, fontSize: 16, color: C.text1, paraSpaceAfter: 10, valign: "top", isTextBox: true, ...RTL, objectName: "attributes list" });
    // left: careers grid
    const jobs = [
      [fa.FaHospital, "المستشفيات العامة والخاصة"],
      [fa.FaClinicMedical, "مراكز العلاج الطبيعي والتأهيل"],
      [fa.FaRunning, "الأندية والفرق الرياضية"],
      [fa.FaSchool, "مراكز ذوي الاحتياجات الخاصة"],
      [fa.FaHome, "الرعاية المنزلية"],
      [fa.FaChalkboardTeacher, "التدريس والبحث العلمي"],
    ];
    const cw = 2.95, ch = 1.45, gx = 0.2, gy = 0.3;
    for (let i = 0; i < jobs.length; i++) {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 6.5 - (col + 1) * cw - col * gx;
      const y = 1.5 + row * (ch + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.12, fill: { color: C.background1 }, line: { color: C.accent4, width: 1.25 }, objectName: "job card " + (i + 1) });
      await circleIcon(s, jobs[i][0], x + (cw - 0.65) / 2, y + 0.15, 0.65, HEX.accent2, HEX.lt1, "job " + (i + 1));
      s.addText(jobs[i][1], { x: x + 0.1, y: y + 0.85, w: cw - 0.2, h: 0.5, fontSize: 13, bold: true, color: C.text1, isTextBox: true, margin: 0, rtlMode: true, lang: "ar-LY", align: "center", valign: "middle", objectName: "job text " + (i + 1) });
    }
    s.addNotes("صفات الخريج ومجالات العمل المتاحة له بعد التخرج.");
  }

  // ---------- 9. Closing ----------
  pres.addSection({ title: "الختام" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "الختام" });
    s.addShape(pres.shapes.OVAL, { x: 9.6, y: 3.4, w: 5.5, h: 5.5, fill: { color: C.accent2, transparency: 60 }, line: { color: C.accent2, transparency: 100 }, objectName: "deco circle" });
    s.addText("شكراً لحسن استماعكم", { placeholder: "title", ...RTL });
    s.addText("نحو كوادر مؤهلة تُعيد للإنسان قدرته على الحركة وجودة الحياة", { x: 0.8, y: 3.6, w: 11.7, h: 0.7, fontSize: 22, italic: true, color: C.accent4, isTextBox: true, ...RTL, objectName: "tagline" });
    s.addText([
      { text: "قسم العلاج الطبيعي - كلية العلوم الصحية العجيلات - جامعة الزاوية", options: { fontSize: 16, color: C.background1, breakLine: true } },
      { text: "رئيس القسم: د. سناء بلق", options: { fontSize: 18, bold: true, color: C.accent3 } },
    ], { x: 0.8, y: 4.9, w: 11.7, h: 1.0, isTextBox: true, ...RTL, objectName: "closing info" });
    s.addNotes("ختام العرض وفتح باب الأسئلة.");
  }

  await pres.writeFile({ fileName: OUT });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts/apply_theme.js"));
    await applyTheme(OUT, THEME);
  }
  console.log("Wrote", OUT);
})();
