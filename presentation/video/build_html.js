// Generates animated.html: an animated 1920x1080 Arabic (RTL) version of the department deck.
// Every animation is a Web Animation created at load time, so render.js can seek any frame exactly.
// Run: NODE_PATH=<node_modules with react, react-dom, react-icons> FONT_DIR=<dir with cairo-ar.woff2, cairo-lat.woff2> node build_html.js
const fs = require("fs");
const path = require("path");
const React = require("react");
const RDS = require("react-dom/server");
const fa = require("react-icons/fa");

const FONT_DIR = process.env.FONT_DIR;
const b64 = (f) => fs.readFileSync(path.join(FONT_DIR, f)).toString("base64");

const COL = { teal: "#0E5E6F", teal2: "#3A9CA8", mint: "#7FC8C2", ice: "#EAF4F5", orange: "#F2A65A", ink: "#1B2B34", grey: "#5B6B73", white: "#FFFFFF" };

const svg = (name) => RDS.renderToStaticMarkup(React.createElement(fa[name]));
// icon in a colored circle
const circ = (icon, size, bg, fg, t, anim = "pop", extra = "") =>
  `<div class="circ" data-in="${anim}" data-t="${t}" style="width:${size}px;height:${size}px;background:${bg};color:${fg};${extra}">${svg(icon)}</div>`;

const footer = (n) => `
  <div class="footer" data-in="fade" data-t="0.3">قسم العلاج الطبيعي | كلية العلوم الصحية العجيلات - جامعة الزاوية</div>
  <div class="pnum" data-in="fade" data-t="0.3">${n}</div>`;

const title = (t) => `<h1 class="title" data-in="clip" data-t="0.35">${t}</h1>`;

// ---------- scenes ----------
const scenes = [];

// 1. Opening
scenes.push({ dur: 7.5, cls: "dark", html: `
  <div class="deco" data-in="fade" data-t="0" style="width:900px;height:900px;left:-320px;top:520px;background:${COL.teal2};opacity:.45"></div>
  <div class="deco" data-in="fade" data-t="0.2" style="width:480px;height:480px;left:260px;top:-260px;background:${COL.mint};opacity:.25"></div>
  ${circ("FaUserMd", 400, COL.white, COL.teal, 0.6, "pop", "position:absolute;left:220px;top:330px")}
  <div class="abs" data-in="clip" data-t="1.1" style="right:130px;top:200px;font-size:38px;color:${COL.mint};font-weight:600">جامعة الزاوية • كلية العلوم الصحية العجيلات</div>
  <div class="abs" data-in="clip" data-t="1.5" style="right:130px;top:285px;font-size:118px;font-weight:800;color:#fff">قسم العلاج الطبيعي</div>
  <div class="abs" data-in="fadeUp" data-t="2.3" style="right:130px;top:480px;font-size:42px;color:#fff">التعريف بالقسم: الرؤية • الرسالة • الأهداف</div>
  <div class="abs headcard" data-in="pop" data-t="3.0" style="right:130px;top:630px">
    <div style="font-size:28px">رئيس القسم</div>
    <div style="font-size:56px;font-weight:800">د. سناء بلق</div>
  </div>` });

// 2. About
const aboutCards = [["FaUniversity", "جامعة الزاوية", "مؤسسة أكاديمية حكومية"], ["FaClinicMedical", "كلية العلوم الصحية", "العجيلات"], ["FaHandsHelping", "التأهيل والعلاج", "تخصص صحي تطبيقي"]];
const aboutParas = [
  "قسم العلاج الطبيعي أحد الأقسام العلمية بكلية العلوم الصحية العجيلات - جامعة الزاوية، ويُعنى بإعداد أخصائيين مؤهلين علمياً وعملياً في مجال التأهيل والعلاج الطبيعي.",
  "يجمع البرنامج بين العلوم الطبية الأساسية والعلوم التخصصية والتدريب السريري في المستشفيات ومراكز التأهيل.",
  "يسهم القسم في خدمة المجتمع المحلي بمنطقة العجيلات وما حولها من خلال نشر الوعي الصحي ودعم برامج الوقاية والتأهيل.",
];
scenes.push({ dur: 11, cls: "light", html: `
  ${title("نبذة عن القسم")}
  <div class="abs" style="right:90px;top:215px;width:1080px">
    ${aboutParas.map((p, i) => `<p class="para" data-in="fadeUp" data-t="${1.0 + i * 0.9}">${p}</p>`).join("")}
  </div>
  <div class="abs col" style="left:90px;top:215px;width:560px">
    ${aboutCards.map((c, i) => `
      <div class="card row" data-in="slideL" data-t="${1.3 + i * 0.35}" style="height:200px">
        ${circ(c[0], 120, COL.teal, "#fff", 1.6 + i * 0.35)}
        <div><div class="h3">${c[1]}</div><div class="small">${c[2]}</div></div>
      </div>`).join("")}
  </div>
  ${footer(2)}` });

// 3. Vision
const vision = "أن يكون قسم العلاج الطبيعي قسماً رائداً ومتميزاً على المستوى المحلي والإقليمي في التعليم والتدريب والبحث العلمي في مجال العلاج الطبيعي والتأهيل، بما يسهم في الارتقاء بالرعاية الصحية وجودة الحياة في المجتمع.";
scenes.push({ dur: 10.5, cls: "dark", html: `
  <div class="deco" data-in="fade" data-t="0" style="width:1000px;height:1000px;right:-260px;top:-380px;background:${COL.teal2};opacity:.45"></div>
  <div class="deco" data-in="fade" data-t="0.3" style="width:420px;height:420px;left:-120px;bottom:-160px;background:${COL.mint};opacity:.2"></div>
  ${circ("FaEye", 220, "#fff", COL.teal, 0.5, "pop", "position:absolute;right:140px;top:110px")}
  <div class="abs" data-in="clip" data-t="0.9" style="right:400px;top:130px;font-size:120px;font-weight:800;color:#fff">رؤيتنا</div>
  <div class="abs words" data-step="0.09" data-t="1.7" style="right:140px;top:430px;width:1640px;font-size:54px;font-weight:600;line-height:1.8;color:#fff">${vision}</div>` });

// 4. Mission
const mission = "إعداد أخصائيين في العلاج الطبيعي يتمتعون بالكفاءة العلمية والمهارة العملية والالتزام بأخلاقيات المهنة، من خلال برامج تعليمية وتدريبية متطورة وبحث علمي هادف، والمشاركة الفاعلة في خدمة المجتمع وتلبية احتياجاته الصحية.";
const pillars = [["FaGraduationCap", "تعليم متميز", "مناهج حديثة تواكب التطور العلمي"], ["FaHospital", "تدريب سريري", "ممارسة عملية في بيئات صحية حقيقية"], ["FaFlask", "بحث علمي", "أبحاث تطبيقية تخدم الممارسة"], ["FaUsers", "خدمة المجتمع", "توعية ووقاية وتأهيل"]];
scenes.push({ dur: 12, cls: "light", html: `
  ${title("رسالتنا")}
  <div class="abs card row" data-in="fadeUp" data-t="0.8" style="right:90px;left:90px;top:200px;height:290px;padding:0 40px">
    ${circ("FaEnvelopeOpenText", 170, COL.teal, "#fff", 1.1)}
    <div class="words" data-step="0.06" data-t="1.5" style="font-size:36px;line-height:1.75;color:${COL.ink}">${mission}</div>
  </div>
  <div class="abs grid4" style="right:90px;left:90px;top:560px">
    ${pillars.map((p, i) => `
      <div class="center">
        ${circ(p[0], 150, COL.teal2, "#fff", 4.2 + i * 0.4)}
        <div class="h3" data-in="fadeUp" data-t="${4.45 + i * 0.4}" style="margin-top:22px">${p[1]}</div>
        <div class="small" data-in="fadeUp" data-t="${4.6 + i * 0.4}">${p[2]}</div>
      </div>`).join("")}
  </div>
  ${footer(4)}` });

// 5. Goals
const goals = [
  ["FaUserGraduate", "إعداد كوادر مؤهلة", "تخريج أخصائيين أكفاء قادرين على تقييم المرضى ووضع الخطط العلاجية وتنفيذها."],
  ["FaStethoscope", "تنمية المهارات السريرية", "تزويد الطلاب بالمهارات العملية عبر التدريب الميداني في المستشفيات ومراكز التأهيل."],
  ["FaMicroscope", "تشجيع البحث العلمي", "دعم البحوث في مجالات العلاج الطبيعي وتطبيق الممارسة المبنية على الدليل."],
  ["FaBalanceScale", "ترسيخ أخلاقيات المهنة", "غرس قيم الأمانة والمسؤولية واحترام المريض والعمل ضمن الفريق الصحي."],
  ["FaHandHoldingHeart", "خدمة المجتمع", "المساهمة في التوعية الصحية والوقاية من الإصابات والإعاقات وتأهيل المصابين."],
  ["FaSyncAlt", "التطوير المستمر", "تحديث المناهج وتأهيل أعضاء هيئة التدريس ومواكبة المستجدات العالمية."],
];
scenes.push({ dur: 13, cls: "light", html: `
  ${title("أهداف القسم")}
  <div class="abs grid3" style="right:90px;left:90px;top:190px;bottom:120px">
    ${goals.map((g, i) => `
      <div class="card goal" data-in="pop" data-t="${0.8 + i * 0.55}">
        <div class="goalhead">
          ${circ(g[0], 105, COL.teal, "#fff", 1.05 + i * 0.55, "spin")}
          <div class="num">${String(i + 1).padStart(2, "0")}</div>
        </div>
        <div class="h3">${g[1]}</div>
        <div class="txt">${g[2]}</div>
      </div>`).join("")}
  </div>
  ${footer(5)}` });

// 6. Fields
const fields = [["FaBone", "العظام والعضلات", "الكسور، آلام الظهر والرقبة، خشونة المفاصل"], ["FaBrain", "الأعصاب", "الجلطات الدماغية، إصابات الحبل الشوكي"], ["FaHeartbeat", "القلب والجهاز التنفسي", "التأهيل القلبي والرئوي"], ["FaChild", "الأطفال", "الشلل الدماغي وتأخر النمو الحركي"], ["FaRunning", "الإصابات الرياضية", "الوقاية والتأهيل والعودة للنشاط"], ["FaWheelchair", "كبار السن والتأهيل", "الحفاظ على الحركة والاستقلالية"]];
scenes.push({ dur: 11.5, cls: "light", html: `
  ${title("مجالات العلاج الطبيعي في البرنامج")}
  <div class="abs grid2" style="right:90px;left:90px;top:200px;bottom:120px">
    ${fields.map((f, i) => `
      <div class="card row outline" data-in="${i % 2 ? "slideL" : "slideR"}" data-t="${0.8 + i * 0.45}">
        ${circ(f[0], 140, COL.teal2, "#fff", 1.1 + i * 0.45, "spin")}
        <div><div class="h3">${f[1]}</div><div class="small">${f[2]}</div></div>
      </div>`).join("")}
  </div>
  ${footer(6)}` });

// 7. Study journey
const steps = [["FaBookMedical", "العلوم الأساسية", "التشريح، وظائف الأعضاء، الفيزياء الحيوية"], ["FaDumbbell", "العلوم التخصصية", "العلاج بالتمرين، العلاج اليدوي، الوسائل الكهربائية"], ["FaHospitalUser", "التدريب السريري", "تطبيق عملي بالمستشفيات ومراكز التأهيل"], ["FaAward", "التخرج والامتياز", "مشروع التخرج والاستعداد لسوق العمل"]];
scenes.push({ dur: 12, cls: "light", html: `
  ${title("المسيرة التعليمية للطالب")}
  <div class="abs dash" data-in="lineX" data-d="3.0" data-t="0.8" style="right:300px;left:300px;top:397px"></div>
  <div class="abs grid4" style="right:90px;left:90px;top:300px">
    ${steps.map((s, i) => `
      <div class="center">
        ${circ(s[0], 200, i === 3 ? COL.orange : COL.teal, "#fff", 1.0 + i * 0.75)}
        <div class="label" data-in="fadeUp" data-t="${1.3 + i * 0.75}">المرحلة ${i + 1}</div>
        <div class="h2" data-in="fadeUp" data-t="${1.45 + i * 0.75}">${s[1]}</div>
        <div class="small" data-in="fadeUp" data-t="${1.6 + i * 0.75}">${s[2]}</div>
      </div>`).join("")}
  </div>
  <div class="abs note" data-in="fadeUp" data-t="4.8" style="right:90px;bottom:115px">يتدرج الطالب من الأساس النظري إلى الممارسة السريرية تحت إشراف أعضاء هيئة التدريس.</div>
  ${footer(7)}` });

// 8. Graduate & careers
const attrs = ["تقييم الحالة وتشخيص المشكلة الحركية", "تصميم خطة علاجية وتنفيذها ومتابعتها", "التواصل الفعّال مع المريض والفريق الصحي", "الالتزام بأخلاقيات المهنة", "التعلم المستمر والبحث العلمي"];
const jobs = [["FaHospital", "المستشفيات العامة والخاصة"], ["FaClinicMedical", "مراكز العلاج الطبيعي والتأهيل"], ["FaRunning", "الأندية والفرق الرياضية"], ["FaSchool", "مراكز ذوي الاحتياجات الخاصة"], ["FaHome", "الرعاية المنزلية"], ["FaChalkboardTeacher", "التدريس والبحث العلمي"]];
scenes.push({ dur: 12.5, cls: "light", html: `
  ${title("خريج القسم ومجالات عمله")}
  <div class="abs card" data-in="slideR" data-t="0.7" style="right:90px;width:800px;top:200px;bottom:120px;padding:40px 46px">
    <div class="row" style="gap:24px">${circ("FaUserCheck", 110, COL.teal, "#fff", 1.0)}<div class="h2">صفات الخريج</div></div>
    <ul class="bul">${attrs.map((a, i) => `<li data-in="slideR" data-t="${1.4 + i * 0.45}">${a}</li>`).join("")}</ul>
  </div>
  <div class="abs grid2 jobs" style="left:90px;width:900px;top:200px;bottom:120px">
    ${jobs.map((j, i) => `
      <div class="card outline center jc" data-in="pop" data-t="${3.8 + i * 0.35}">
        ${circ(j[0], 90, COL.teal2, "#fff", 4.0 + i * 0.35)}
        <div class="jt">${j[1]}</div>
      </div>`).join("")}
  </div>
  ${footer(8)}` });

// 9. Closing
scenes.push({ dur: 8.5, cls: "dark", html: `
  <div class="deco" data-in="fade" data-t="0" style="width:950px;height:950px;right:-260px;bottom:-420px;background:${COL.teal2};opacity:.45"></div>
  <div class="deco" data-in="fade" data-t="0.2" style="width:420px;height:420px;left:120px;top:-200px;background:${COL.mint};opacity:.22"></div>
  ${circ("FaHandsHelping", 190, "#fff", COL.teal, 0.4, "pop", "position:absolute;right:130px;top:170px")}
  <div class="abs" data-in="zoom" data-t="0.9" style="right:130px;top:390px;font-size:112px;font-weight:800;color:#fff">شكراً لحسن استماعكم</div>
  <div class="abs" data-in="fadeUp" data-t="1.8" style="right:130px;top:575px;font-size:44px;color:${COL.mint}">نحو كوادر مؤهلة تُعيد للإنسان قدرته على الحركة وجودة الحياة</div>
  <div class="abs" data-in="fadeUp" data-t="2.5" style="right:130px;top:720px;font-size:34px;color:#fff">قسم العلاج الطبيعي - كلية العلوم الصحية العجيلات - جامعة الزاوية</div>
  <div class="abs" data-in="fadeUp" data-t="2.9" style="right:130px;top:790px;font-size:42px;font-weight:800;color:${COL.orange}">رئيس القسم: د. سناء بلق</div>` });

const html = `<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>قسم العلاج الطبيعي</title>
<style>
@font-face{font-family:Cairo;src:url(data:font/woff2;base64,${b64("cairo-ar.woff2")}) format("woff2");font-weight:200 1000;unicode-range:U+0600-06FF,U+0750-077F,U+FB50-FDFF,U+FE70-FEFC,U+200C-200E;}
@font-face{font-family:Cairo;src:url(data:font/woff2;base64,${b64("cairo-lat.woff2")}) format("woff2");font-weight:200 1000;}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#000}
body{font-family:Cairo,sans-serif;color:${COL.ink}}
#stage{position:relative;width:1920px;height:1080px;overflow:hidden;background:${COL.teal}}
.scene{position:absolute;inset:0;opacity:0;overflow:hidden}
.dark{background:${COL.teal};color:#fff}
.light{background:#fff}
.abs{position:absolute}
.deco{position:absolute;border-radius:50%}
.circ{border-radius:50%;display:flex;align-items:center;justify-content:center;flex:none}
.circ svg{width:50%;height:50%}
.title{position:absolute;right:90px;top:55px;font-size:66px;font-weight:800;color:${COL.teal}}
.footer{position:absolute;left:90px;bottom:34px;font-size:20px;color:${COL.grey}}
.pnum{position:absolute;right:90px;bottom:34px;font-size:20px;color:${COL.grey}}
.para{font-size:33px;line-height:1.75;margin-bottom:26px}
.card{background:${COL.ice};border-radius:28px}
.outline{background:#fff;border:3px solid ${COL.mint}}
.row{display:flex;align-items:center;gap:30px;padding:0 30px}
.col{display:flex;flex-direction:column;gap:40px}
.center{display:flex;flex-direction:column;align-items:center;text-align:center}
.h2{font-size:44px;font-weight:800;color:${COL.teal};margin-top:6px}
.h3{font-size:36px;font-weight:800;color:${COL.teal}}
.small{font-size:27px;color:${COL.grey};line-height:1.5}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:40px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:36px}
.grid2{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,1fr);gap:30px}
.goal{padding:28px 34px}
.goalhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.num{font-size:58px;font-weight:800;color:${COL.orange}}
.txt{font-size:25px;line-height:1.6;margin-top:8px}
.headcard{background:${COL.orange};color:${COL.ink};border-radius:28px;padding:22px 50px;line-height:1.35}
.dash{border-top:7px dashed ${COL.mint};height:0}
.label{font-size:30px;font-weight:800;color:${COL.orange};margin-top:22px}
.note{font-size:30px;color:${COL.grey}}
.bul{list-style:none;margin-top:30px}
.bul li{font-size:33px;line-height:1.5;margin-bottom:26px;padding-right:44px;position:relative}
.bul li::before{content:"";position:absolute;right:0;top:20px;width:18px;height:18px;border-radius:50%;background:${COL.orange}}
.jobs .jc{justify-content:center;gap:14px}
.jt{font-size:27px;font-weight:800;padding:0 16px}
.w{display:inline-block;white-space:pre}
.wipe{position:absolute;inset:0;transform:translateX(100%);z-index:50}
</style></head>
<body><div id="stage">
${scenes.map((s, i) => `<section class="scene ${s.cls}" id="s${i + 1}">${s.html}</section>`).join("\n")}
<div class="wipe" id="wA" style="background:${COL.orange}"></div>
<div class="wipe" id="wB" style="background:${COL.teal2}"></div>
</div>
<script>
const DUR=${JSON.stringify(scenes.map((s) => s.dur))};
const EASE='cubic-bezier(.2,.8,.2,1)';
function A(el,kf,start,dur,o={}){return el.animate(kf,{delay:start*1000,duration:dur*1000,fill:o.fill||'both',easing:o.easing||EASE,iterations:o.iter||1,direction:o.dir||'normal'});}
const IN={
  fade:[{opacity:0},{opacity:1}],
  fadeUp:[{opacity:0,transform:'translateY(45px)'},{opacity:1,transform:'none'}],
  slideR:[{opacity:0,transform:'translateX(160px)'},{opacity:1,transform:'none'}],
  slideL:[{opacity:0,transform:'translateX(-160px)'},{opacity:1,transform:'none'}],
  pop:[{opacity:0,transform:'scale(.5)'},{opacity:1,transform:'scale(1.08)',offset:.7},{opacity:1,transform:'none'}],
  spin:[{opacity:0,transform:'scale(.3) rotate(-180deg)'},{opacity:1,transform:'none'}],
  zoom:[{opacity:0,transform:'scale(1.35)'},{opacity:1,transform:'none'}],
  clip:[{opacity:1,clipPath:'inset(0 0 0 100%)'},{opacity:1,clipPath:'inset(0 0 0 0)'}],
  lineX:[{transform:'scaleX(0)',transformOrigin:'right'},{transform:'scaleX(1)',transformOrigin:'right'}],
};
const DEF={fade:.9,fadeUp:.8,slideR:.85,slideL:.85,pop:.7,spin:.9,zoom:1,clip:1.1,lineX:2};
// split word-reveal blocks into spans
document.querySelectorAll('.words').forEach(b=>{
  const parts=b.textContent.trim().split(/(\\s+)/);
  b.innerHTML=parts.map(p=>/^\\s+$/.test(p)?p:'<span class="w">'+p+'</span>').join('');
});
let S=0; const starts=[];
DUR.forEach(d=>{starts.push(S);S+=d;});
window.TOTAL=S;
const scenes=[...document.querySelectorAll('.scene')];
scenes.forEach((sc,i)=>{
  const s=starts[i], e=s+DUR[i], last=i===scenes.length-1;
  // scene visibility
  if(i===0) A(sc,[{opacity:0},{opacity:1}],0,1.0); else A(sc,[{opacity:0},{opacity:1}],s,0.001,{easing:'linear'});
  // element entrances
  sc.querySelectorAll('[data-in]').forEach(el=>{
    const k=el.dataset.in, t=parseFloat(el.dataset.t||0), d=parseFloat(el.dataset.d||DEF[k]);
    A(el,IN[k],s+t,d,{easing:k==='lineX'?'cubic-bezier(.45,0,.2,1)':EASE});
  });
  sc.querySelectorAll('.words').forEach(b=>{
    const t=parseFloat(b.dataset.t), st=parseFloat(b.dataset.step);
    b.querySelectorAll('.w').forEach((w,j)=>A(w,[{opacity:0,transform:'translateY(25px)'},{opacity:1,transform:'none'}],s+t+j*st,.6));
  });
  // gentle continuous motion on decorative circles
  sc.querySelectorAll('.deco').forEach((el,j)=>A(el,{translate:['0px 0px',(j%2?'-40px 30px':'50px -35px')],scale:['1','1.08']},s,4.5,{iter:Infinity,dir:'alternate',easing:'ease-in-out'}));
  // exits: everything leaves before the wipe (last scene fades out instead)
  if(!last){
    const ex=[...sc.querySelectorAll('[data-in], .words')].reverse();
    ex.forEach((el,j)=>A(el,[{opacity:1,transform:'none'},{opacity:0,transform:'translateY(-35px) scale(.96)'}],e-1.15+j*(0.5/ex.length),.45,{fill:'forwards',easing:'ease-in'}));
    A(sc,[{opacity:1},{opacity:0}],e,0.001,{fill:'forwards',easing:'linear'});
    // wipe transition centred on the cut
    const wA=document.getElementById('wA'), wB=document.getElementById('wB');
    A(wA,[{transform:'translateX(100%)'},{transform:'translateX(0)'}],e-.6,.55,{fill:'forwards',easing:'cubic-bezier(.7,0,.3,1)'});
    A(wB,[{transform:'translateX(100%)'},{transform:'translateX(0)'}],e-.5,.5,{fill:'forwards',easing:'cubic-bezier(.7,0,.3,1)'});
    A(wB,[{transform:'translateX(0)'},{transform:'translateX(-100%)'}],e+.05,.55,{fill:'forwards',easing:'cubic-bezier(.7,0,.3,1)'});
    A(wA,[{transform:'translateX(0)'},{transform:'translateX(-100%)'}],e+.15,.55,{fill:'forwards',easing:'cubic-bezier(.7,0,.3,1)'});
  } else {
    A(sc,[{opacity:1},{opacity:0}],e-1.3,1.3,{fill:'forwards',easing:'ease-in'});
  }
});
// preview mode: plays in real time when opened in a browser; render.js pauses and seeks instead
</script></body></html>`;

fs.writeFileSync(path.join(__dirname, "animated.html"), html);
console.log("animated.html written, total", scenes.reduce((a, s) => a + s.dur, 0), "s");
