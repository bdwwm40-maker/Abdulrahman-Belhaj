# فيديو موشن جرافيك — مشروع «الشباب والمستقبل» (الوثبة الثانية)

مكتب الوكالة الوطنية للجهود التطوعية للشباب — العجيلات.
الشخصية الرسمية للوكالة تشرح المشروع والدورات الثماني بصوت رجل وباللهجة الليبية.

## الملفات النهائية

| الملف | الصوت | المدة |
|---|---|---|
| `final/youth-future-ajaylat-fusha-v2.mp4` | **النسخة الثانية (المعتمدة): شخصية متحركة + فصحى مشكولة بالكامل** | 1:51 |
| `final/youth-future-ajaylat-fusha.mp4` | صوت اصطناعي حماسي — عربية فصحى + موسيقى مبهجة | 1:41 |
| `final/youth-future-ajaylat-msa.mp4` | **بصوت عبد الرحمن (مستنسخ) — عربية فصحى** | 1:54 |
| `final/youth-future-ajaylat.mp4` | صوت ليبي اصطناعي — لهجة ليبية | 1:43 |

جميعها 1920×1080، ‏30 إطاراً/ث، صوت AAC بمستوى ‎-16 LUFS، مع ترجمة عربية مدمجة أسفل الشاشة.

### النسخة الثانية — شخصية متحركة وصوت فصيح (المعتمدة)

**ما الذي تغيّر:**
- **الصوت:** ‏`ar-SA-HamedNeural` بسرعته وطبقته الطبيعيتين (دون تسريع أو رفع للطبقة)، والنص في
  `script-fusha.json` **مشكول تشكيلاً كاملاً** مع الوقف بالسكون في آخر كل جملة.
  - **اختيار الصوت بالقياس:** قورن ستة أصوات عربية على النص نفسه، وفُرِّغ كل صوت بـ Whisper (medium) وقيست نسبة الأخطاء على مستوى الحروف.
    كانت النتائج: حامد 1.8% وحمدان 1.8% وتيم 2.1% وعمر 2.1% وفهد 2.2% وعبد الله 5.7%.
  - **الكلمات التي سُمعت خطأً:** جُرّبت بصيغ بديلة، واعتُمدت الصيغة التي يُفرَّغ فيها النطق صحيحاً:
    - «الدَّوْراتِ؟ هَيّا بِنا»
    - «بِثِقَةٍ وَهُدوءٍ»
    - «فُرْصَةٌ ذَهَبِيَّةٌ»
    - «وُورْد، وَإِكْسِل، وَبَاوَر بُوينْت»: يتعرّف عليها مفرِّغ إنجليزي على أنها Word وExcel وPowerPoint.
- **الدورات:**
  - «فن الحوار والمناظرة» بدل «فن المناظرة والخطابة».
  - «الذكاء الاصطناعي في سوق العمل» بدل «كيفية استخدام الذكاء الاصطناعي».
  - «أساسيات الحاسب الآلي» مع برامج Word وExcel وPowerPoint، وتظهر شارات البرامج على البطاقة لحظة نطق كل اسم.
- **الشخصية متحركة:**
  - **الشفاه:** تتحرك مع الكلام حرفاً بحرف.
    - تتفتح مع الفتحة والألف، وتستدير مع الضمة والواو، وتنبسط مع الكسرة والياء، وتنطبق مع الباء والميم، وتلامس الأسنان مع الفاء.
  - **العينان والحاجبان:** ترمش العينان ترميشاً طبيعياً، ويرتفع الحاجبان عند التعجب والسؤال.
  - **الجسم:** يبقى مع حركة التنفس والإطار.
  - **وجه الشخصية وتفاصيلها:** يبقى الوجه نفسه وكذلك الشنّة والزي والشعار. لا يتغير إلا الفم والعينان، وفي الإطار المحايد تبقى الصورة الأصلية بكسلاتها.

**كيف تعمل الحركة:**

1. **مكتبة تعابير:** يُولَّد الوجه بنموذج [LivePortrait](https://huggingface.co/spaces/KwaiVGI/LivePortrait) (KwaiVGI، ترخيص MIT) محلياً على المعالج، في 73 حالة:
   - شبكة للفم: 11 درجة فتح × 5 أشكال، من مستدير إلى منبسط.
   - 3 درجات انطباق للشفاه.
   - شبكة للعينين: 5 درجات ترميش × 3 درجات للحاجب.

   يستخدم ذلك أداة `tools/face_rig.py`.
2. **توقيت الحروف:** تحوِّل `tools/lipsync.py` النص المشكول إلى أصوات:
   - تعالج المدّ والشدّة والتنوين واللام الشمسية وهمزة الوصل والوقف.
   - ثم تحاذيها مع التسجيل بنموذج المحاذاة MMS (‏torchaudio)، فيُعرف وقت كل حرف بدقة 20 ملّي ثانية.
3. **تركيب الإطارات:** تركّب `tools/face_frames.py` وجه كل إطار من المكتبة بالاستيفاء، وتلصقه فوق الشخصية الأصلية.
   - النتيجة 1300 رقعة فريدة لـ 3328 إطاراً.
   - تعرضها المنصة في `stage/` فوق الصورة الثابتة، فتتحرك مع الإطار والتنفس.

```bash
# مرة واحدة: كود LivePortrait وأوزانه من مساحة Hugging Face (src/ + pretrained_weights/)
python3 -c "from huggingface_hub import snapshot_download as d; d('KwaiVGI/LivePortrait', repo_type='space', local_dir='LP', allow_patterns=['src/**','pretrained_weights/**'])"
pip install onnx onnxruntime rich scikit-image
python3 tools/face_rig.py LP                                   # مكتبة التعابير ← build/face-lib.npz (~15 دقيقة)

SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 tools/voice.py --script script-fusha.json \
  --voice ar-SA-HamedNeural --out audio-fusha --rate=+0% --pitch=+0Hz
python3 tools/lipsync.py --script script-fusha.json --audio audio-fusha      # توقيت الحروف
python3 tools/build_timeline.py --script script-fusha.json --audio audio-fusha --music upbeat
python3 tools/face_frames.py --lib build/face-lib.npz --audio audio-fusha    # وجه كل إطار
NODE_PATH=$(npm root -g) node tools/render.mjs
tools/mix.sh 0.14 final/youth-future-ajaylat-fusha-v2.mp4
```

> `build_timeline.py` يحذف `build/face.js` القديم، فالنسخ الأخرى (بلا `face_frames.py`) تُبنى بالشخصية الثابتة كما كانت.

### النسخة الفصحى بصوت اصطناعي (الأولى)

- الصوت: ‏`ar-SA-HamedNeural` (صوت فصيح، الأوضح والأكثر تلويناً بين الأصوات العربية المجرَّبة)
  بسرعة ‎+6% وطبقة ‎+6Hz لنبرة أكثر حيوية.
- الموسيقى: مولَّدة برمجياً — سلّم دو الكبير (C-G-Am-F)، ‏112 نبضة/دقيقة، أربيجيو وإيقاع خفيف،
  وتنخفض تلقائياً عند الكلام (`build_timeline.py --music upbeat`).

```bash
SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 tools/voice.py --script script-msa.json \
  --voice ar-SA-HamedNeural --out audio-msa-ai --rate=+6% --pitch=+6Hz
python3 tools/build_timeline.py --script script-msa.json --audio audio-msa-ai --music upbeat
NODE_PATH=$(npm root -g) node tools/render.mjs
tools/mix.sh 0.14 final/youth-future-ajaylat-fusha.mp4
```

### النسخة بصوتك (الفصحى)

- النص: `script-msa.json` (مع تشكيل في الكلمات التي كان النموذج يخطئ فيها).
- الصوت: استنساخ محلي بنموذج **XTTS v2** من عيّنة صوتك (17 ثانية)، دون إرسالها لأي خدمة خارجية.
  لكل مشهد عدة نسخ (3–6)، تُفرَّغ كل نسخة بـ Whisper ويُختار الأوضح نطقاً.
  التقرير في `audio-msa-xtts/takes.json`.
- القياس: تشابه مع صوتك ≈ 0.90 (نصفا تسجيلك نفسه ≈ 0.92)، وأخطاء النطق أقل من محاولة OpenVoice (25%).
- ترخيص أوزان XTTS v2 هو Coqui Public Model License: **للاستخدام غير التجاري**.
  فيديو توعوي لوكالة تطوعية غير ربحي، أما الإعلانات التجارية المدفوعة فتحتاج أداة أخرى أو تسجيلاً بصوتك الحقيقي.

```bash
COQUI_TOS_AGREED=1 python3 tools/xtts_voice.py REF.wav --takes 3          # صوتك لكل مشهد
python3 tools/xtts_voice.py REF.wav --takes 6 --only c2 c3                  # إعادة مشاهد بعينها
python3 tools/build_timeline.py --script script-msa.json --audio audio-msa-xtts
NODE_PATH=$(npm root -g) node tools/render.mjs
tools/mix.sh 0.10 final/youth-future-ajaylat-msa.mp4
```

## المشاهد (توقيت النسخة الثانية)

| الوقت | المشهد |
|---|---|
| 0:00 | افتتاحية: شعار الوكالة + «مشروع الشباب والمستقبل — الوثبة الثانية» |
| 0:03 | التحية لشباب العجيلات |
| 0:13 | المشروع ومكتب العجيلات والوثبة الثانية |
| 0:23 | دورات تدريبية ومهنية لشباب المدينة |
| 0:36 | عدّاد «8 دورات» |
| 0:41 | بطاقة لكل دورة (01–08) مع شريط تقدّم |
| 1:28 | دعوة للتسجيل والمتابعة |
| 1:39 | الختام: الشعار + «إيثار وعطاء» |

## الصوت

- الصوت: ‏`ar-LY-OmarNeural` (صوت رجل ليبي عصبي من Microsoft) عبر `edge-tts`، أبطأ قليلاً (‎-3%)
  مع تقصير الوقفات الطويلة.
- النص في `script.json` (كُتب بثلاث صيغ ثم دُمج الأفضل منها، باللهجة الليبية الغربية).
- موسيقى خلفية هادئة مولَّدة برمجياً (بلا حقوق)، تنخفض تلقائياً عند الكلام.

> في النسخ الثلاث الأولى الشخصية صورة ثابتة تتحرك بالإطار (تقريب، تنفّس، اهتزاز مع الصوت، مؤشر كلام).
> النسخة الثانية (`-fusha-v2`) فيها مزامنة شفاه حقيقية وترميش — انظر أعلاه.

## إعادة البناء

```bash
SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 tools/voice.py --rate=-3%   # الصوت لكل مشهد
python3 tools/build_timeline.py                                            # التوقيت + الترجمة + الموسيقى
NODE_PATH=$(npm root -g) node tools/render.mjs                             # الإطارات (Playwright)
tools/mix.sh 0.10                                                          # الدمج النهائي
```

لتعديل نص أو دورة: عدِّل `script.json` ثم أعد الخطوات الأربع. التصميم في `stage/` (HTML/CSS/JS).
