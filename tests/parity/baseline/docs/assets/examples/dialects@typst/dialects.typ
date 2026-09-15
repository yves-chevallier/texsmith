#set document(
title: "Language Support",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Language Support]]
#v(1.5em)

#ts-callout-style.update("fancy")

TeXSmith can render documents in multiple languages and scripts, including those with
complex typesetting requirements. Below are examples of various languages and scripts
supported by TeXSmith, showcasing its versatility in handling diverse linguistic
content.

= Japanese (#ts-script("chinese")[日本語]) – Haiku & Classical Poetry

Source (public domain): Matsuo Bashō, Oku no Hosomichi (1694)

#quote(block: true)[
#ts-script("japanese")[月日は百代の過客にして、行きかふ年も旅人なり。]

#ts-script("japanese")[舟に乗り、馬に乗りて、初秋の風に吹かれつつ、]

#ts-script("japanese")[道のべの小草を分け、山川を越えて、]

#ts-script("japanese")[心にかかる景色を求めて歩みゆく。]]

= Syriac

Source (public domain): Peshitta – Gospel of Matthew (5th century)

#quote(block: true)[
#ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܡܣܟܢ̈ܐ ܒܪܘܚܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܕܝܠܗܘܢ ܗܝ ܡܠܟܘܬܐ ܕܫܡܝ̈ܐ].
#ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܐܒܝ̈ܠܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܬܒܝܐܘܢ].
#ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܡܟܝ̈ܟܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܪܬܘܢ ܠܐܪܥܐ].
#ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܐܝܠܝܢ ܕܟܦܢܝܢ ܘܨܗܝܢ ܠܟܐܢܘܬܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܣܒܥܘܢ].]

= Greek (Ancient Greek – #ts-script("greek")[Ἑλληνικά])

Source (public domain): Homer, _Odyssey_ (8th century BC)

#quote(block: true)[
#ts-script("greek")[ἄνδρα μοι ἔννεπε], #ts-script("greek")[Μοῦσα], #ts-script("greek")[πολύτροπον], #ts-script("greek")[ὃς μάλα πολλὰ]
#ts-script("greek")[πλάγχθη], #ts-script("greek")[ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν]·
#ts-script("greek")[πολλῶν δ]' #ts-script("greek")[ἀνθρώπων ἴδεν ἄστεα καὶ νόον ἔγνω],
#ts-script("greek")[πολλὰ δ]' #ts-script("greek")[ὅ γ]' #ts-script("greek")[ἐν πόντῳ πάθεν ἄλγεα ὃν κατὰ θυμόν],
#ts-script("greek")[ἀρνύμενος ἥν τε ψυχὴν καὶ νόστον ἑταίρων].]

= Korean (#ts-script("korean")[한국어 ]– #ts-script("korean")[古典시])

Source (public domain): Jeong Mong-ju (1337–1392), _Dansimga_

#quote(block: true)[
#ts-script("korean")[이 몸이 죽고 죽어 일백 번 고쳐 죽어]
#ts-script("korean")[백골이 진토되어 넋이라도 있고 없고]
#ts-script("korean")[임 향한 일편단심이야 가실 줄이 있으랴]
#ts-script("korean")[어찌 한 마음 변치 않으리오].]

= Chinese Traditional (#ts-script("chinese")[繁體中文 ]– Classical Chinese)

Source (public domain): Tao Yuanming (365–427), _#ts-script("chinese")[歸園田居]_

#quote(block: true)[
#ts-script("chinese")[少無適俗韻，性本愛丘山。]

#ts-script("chinese")[誤落塵網中，一去三十年。]

#ts-script("chinese")[羈鳥戀舊林，池魚思故淵。]

#ts-script("chinese")[開荒南野際，守拙歸園田。]

#ts-script("chinese")[久在樊籠裡，復得返自然。]]

= Arabic

Source (public domain): Imru’ al-Qays (6th century), _Mu‘allaqāt_

#quote(block: true)[
#ts-script("arabics")[قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَنزِلِ]
#ts-script("arabics")[بِسِقطِ اللِّوَى بَيْنَ الدَّخول فَحَوْمَلِ]
#ts-script("arabics")[فَتُوضِحَ فَالمِقراةِ لَم يَعفُ رَسمُها]
#ts-script("arabics")[لِما نَسَجَتها مِن جَنُوبٍ وشَمألِ]
#ts-script("arabics")[تَرَى بَعَرَ الأرْآمِ في عَرَصاتِها]
#ts-script("arabics")[وَقِيْعانِها كَأنَّهُ حَبُّ فُلْفُلِ]]

= Devanagari (#ts-script("devanagari")[देवनागरी ]– Sanskrit)

Source (public domain): Bhagavad Gītā (2.20)

#quote(block: true)[
#ts-script("devanagari")[न जायते म्रियते वा कदाचिन्]
#ts-script("devanagari")[नायं भूत्वा भविता वा न भूयः।]
#ts-script("devanagari")[अजो नित्यः शाश्वतोऽयं पुराणो]
#ts-script("devanagari")[न हन्यते हन्यमाने शरीरे॥]]

= Urdu (#ts-script("arabics")[اُردُو ]– Classical Poetry)

Source (public domain): Mir Taqi Mir (1723–1810)

#quote(block: true)[
#ts-script("arabics")[عشق ایک مِیرُی آفت ہے]
#ts-script("arabics")[دل کو لے کر ڈوب ہی جاتی ہے]
#ts-script("arabics")[درد کی لہر اٹھتی جائے]
#ts-script("arabics")[اشک بھی ساتھ بہہ ہی جاتے ہیں]]

= Sinhala (#ts-script("sinhala")[සිංහල])

Source (public domain): Classical Sandesa-style verse

#quote(block: true)[
#ts-script("sinhala")[සඳ එළිය පුරා රැය නිල් සිලුවෙන් හැඬේලා]
#ts-script("sinhala")[සඳහනෙකු මෙන් සිත් තුළ හඬක් වී පාවෙයි]#ts-script("devanagari")[।]
#ts-script("sinhala")[සිහිනෙන් පාරවල් හරහා ලංවීය මල් සුවඳක්]
#ts-script("sinhala")[සරත් රැයේ සුවිසෙලිනි මනමේ තනුවේ රැදී].]

= Khmer (#ts-script("khmer")[ខ្មែរ])

Source (public domain): Classical Khmer poetic style (Chbab form)

#quote(block: true)[
#ts-script("khmer")[យប់ស្ថប់ត្រង់ ព្រៃស្រពន់សូរ ស្ទឹងស្ទូងតាមស្រមោលដើមឈើ]

#ts-script("khmer")[ខ្យល់អូលីល មកពីភ្នំឆ្ងាយ ប៉ះមកដល់ចិត្តអើយឆ្ងាយណា]

#ts-script("khmer")[សូរសត្វបក្សី លេបលាន់តាមសែន ក្លិនផ្កាឈូករាត្រីរំលេច។]]

= Telugu (#ts-script("telugu")[తెలుగు])

Source (public domain): Nannaya (11th century), _Andhra Mahābhāratam_

#quote(block: true)[
#ts-script("telugu")[నన్నయ భ]#ts-script("bengali")[ট্ট]#ts-script("telugu")[ుని వాక్కులు నదీవేగమువలె ప్రవహించి]
#ts-script("telugu")[పాండవ కథామృతము లోకమును నింపెను]#ts-script("devanagari")[।]
#ts-script("telugu")[ధర్మమునకు మార్గదర్శి పాండవుని గాథలతో]
#ts-script("telugu")[తెలుగు భాషకు తొలిమకుటం కీర్తి ప్రసరించెనె].]
