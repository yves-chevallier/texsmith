#set document(
title: "Foreign Script Support",
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
#set page(columns: 2)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[Foreign Script Support]
#linebreak()
#text(size: 1.2em)[Demo on fonts fallback support]]
#v(1.5em)

#block(width: 100%, inset: (x: 2em))[
#align(center)[#text(weight: "bold")[Abstract]]
#v(0.5em)
TeXSmith can render documents in multiple languages and scripts, including those with complex typesetting requirements. Below are examples of various
languages and scripts supported by TeXSmith, showcasing its versatility in
handling diverse linguistic content.]
#v(1em)

= Japanese (#ts-script("chinese")[日本語])

Japanese is the national language of Japan and is spoken by over 125 million people, primarily within the country.

#ts-script("japanese")[月日は百代の過客にして、行きかふ年も旅人なり。]

#ts-script("japanese")[舟に乗り、馬に乗りて、初秋の風に吹かれつつ、]

#ts-script("japanese")[道のべの小草を分け、山川を越えて。]

= Korean (#ts-script("korean")[한국어])

Korean is spoken by about 80 million people worldwide and is the official language of both South Korea and North Korea.

#ts-script("korean")[이 몸이 죽고 죽어 일백 번 고쳐 죽어]

#ts-script("korean")[백골이 진토되어 넋이라도 있고 없고]

#ts-script("korean")[임 향한 일편단심이야 가실 줄이 있으랴]

= Syriac (#ts-script("syriacfull")[ܠܫܢܐ ܣܘܪܝܝܐ])

Syriac is an ancient Aramaic language historically used in the Middle East, especially in Christian liturgical and literary traditions.

#ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܡܣܟܢ̈ܐ ܒܪܘܚܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܕܝܠܗܘܢ ܗܝ ܡܠܟܘܬܐ ܕܫܡܝ̈ܐ]. #ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܐܒܝ̈ܠܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܬܒܝܐܘܢ]. #ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܡܟܝ̈ܟܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܪܬܘܢ ܠܐܪܥܐ]. #ts-script("syriacfull")[ܛܘܒܝܗܘܢ ܠܐܝܠܝܢ ܕܟܦܢܝܢ ܘܨܗܝܢ ܠܟܐܢܘܬܐ]#ts-script("arabics")[، ]#ts-script("syriacfull")[ܕܗܢܘܢ ܢܣܒܥܘܢ].

= Greek (#ts-script("greek")[ελληνικά])

Greek is the official language of Greece and Cyprus and is spoken by roughly 13 million people, with a literary tradition dating back more than three millennia.

#ts-script("greek")[Άντρα], #ts-script("greek")[Μούσα], #ts-script("greek")[πες μου τον πολυμήχανο], #ts-script("greek")[που πάρα πολλά]
#ts-script("greek")[ταλαιπωρήθηκε], #ts-script("greek")[αφού κατέστρεψε την ιερή πολιτεία της Τροίας]·

#ts-script("greek")[και είδε τις πόλεις πολλών ανθρώπων και γνώρισε τον τρόπο τους],
#ts-script("greek")[και πολλές λύπες έπαθε στη θάλασσα μέσα στην καρδιά του],

#ts-script("greek")[προσπαθώντας να σώσει και τη δική του ζωή]
#ts-script("greek")[και την επιστροφή των συντρόφων του].

= Chinese Trad. (#ts-script("chinese")[繁體中文])

Traditional Chinese characters are used mainly in Taiwan, Hong Kong, and Macau by tens of millions of speakers of Mandarin, Cantonese, and other Sinitic languages.

#ts-script("chinese")[少无适俗韵，性本爱丘山。]
#ts-script("chinese")[误落尘网中，一去三十年。]
#ts-script("chinese")[羁鸟恋旧林，池鱼思故渊。]
#ts-script("chinese")[开荒南野际，守拙归园田。]
#ts-script("chinese")[久在樊笼里，复得返自然。]

= Arabic

Arabic is spoken by over 400 million people across the Middle East and North Africa and serves as the liturgical language of Islam.

#ts-script("arabics")[قِفا نَبْكِ مِنْ ذِكرَى حبيبٍ ومَنزِلِ]

#ts-script("arabics")[بِسِقطِ اللِّوَى بَيْنَ الدَّخول فَحَوْمَلِ]

#ts-script("arabics")[فَتُوضِحَ فَالمِقراةِ لَم يَعفُ رَسمُها]

#ts-script("arabics")[لِما نَسَجَتها مِن جَنُوبٍ وشَمألِ]

#ts-script("arabics")[تَرَى بَعَرَ الأرْآمِ في عَرَصاتِها]

#ts-script("arabics")[وَقِيْعانِها كَأنَّهُ حَبُّ فُلْفُلِ]

= Devanagari (#ts-script("devanagari")[देवनागरी])

The Devanagari script is used for several major South Asian languages, including Hindi, Marathi, and Sanskrit, representing over 600 million speakers combined.

#ts-script("devanagari")[न जायते म्रियते वा कदाचिन्]

#ts-script("devanagari")[नायं भूत्वा भविता वा न भूयः।]

#ts-script("devanagari")[अजो नित्यः शाश्वतोऽयं पुराणो]

#ts-script("devanagari")[न हन्यते हन्यमाने शरीरे॥]

= Urdu (#ts-script("arabics")[اردو])

Urdu is spoken by more than 170 million people, mainly in Pakistan and India, and serves as Pakistan's national language.

#ts-script("arabics")[عشق ایک مِیرُی آفت ہے]

#ts-script("arabics")[دل کو لے کر ڈوب ہی جاتی ہے]

#ts-script("arabics")[درد کی لہر اٹھتی جائے]

#ts-script("arabics")[اشک بھی ساتھ بہہ ہی جاتے ہیں]

= Sinhala (#ts-script("sinhala")[සිංහල])

Sinhala is the primary language of Sri Lanka and is spoken by about 17 million native speakers.

#ts-script("sinhala")[සඳ එළිය පුරා රැය නිල් සිලුවෙන් හැඬේලා]

#ts-script("sinhala")[සඳහනෙකු මෙන් සිත් තුළ හඬක් වී පාවෙයි]#ts-script("devanagari")[।]

#ts-script("sinhala")[සිහිනෙන් පාරවල් හරහා ලංවීය මල් සුවඳක්]

#ts-script("sinhala")[සරත් රැයේ සුවිසෙලිනි මනමේ තනුවේ රැදී].

= Khmer (#ts-script("khmer")[ខ្មែរ])

Khmer is the official language of Cambodia and is spoken by more than 16 million people.

#ts-script("khmer")[យប់ស្ថប់ត្រង់ ព្រៃស្រពន់សូរ ស្ទឹងស្ទូងតាមស្រមោលដើមឈើ]
#ts-script("khmer")[ខ្យល់អូលីល មកពីភ្នំឆ្ងាយ ប៉ះមកដល់ចិត្តអើយឆ្ងាយណា]
#ts-script("khmer")[សូរសត្វបក្សី លេបលាន់តាមសែន ក្លិនផ្កាឈូករាត្រីរំលេច។]

= Telugu (#ts-script("telugu")[తెలుగు])

Telugu is a major Dravidian language of India, spoken by over 80 million people, primarily in the states of Andhra Pradesh and Telangana.

#ts-script("telugu")[నన్నయ భట్టుని వాక్కులు నదీవేగమువలె ప్రవహించి]

#ts-script("telugu")[పాండవ కథామృతము లోకమును నింపెను]#ts-script("devanagari")[।]

#ts-script("telugu")[ధర్మమునకు మార్గదర్శి పాండవుని గాథలతో]

#ts-script("telugu")[తెలుగు భాషకు తొలిమకుటం కీర్తి ప్రసరించెనె].

= Georgian (#ts-script("georgianfull")[ქართული])

Georgian is the official language of Georgia, with around 4-5 million speakers, and is the largest member of the Kartvelian language family.

#ts-script("georgianfull")[ქართული ენა კავკასიონის მთებს შორის დაბადებული ძველი ხმავია].
#ts-script("georgianfull")[ქრონიკებში], #ts-script("georgianfull")[ხელნაწერებში და ხალხურ სიმღერებში ეს ენა ხალხის ისტორიას მოჰყვება].
#ts-script("georgianfull")[თბილისის ქუჩის საუბრიდან სოფლის სუფრის ტოსტებამდე],
#ts-script("georgianfull")[ქართული სიტყვები მეგობრობისა და სტუმართმოყვარეობის სულს ატარებს].

= Armenian (#ts-script("armenian")[Հայերեն])

Armenian is the official language of Armenia and a key language of the global Armenian diaspora, spoken by roughly 6–7 million people.

#ts-script("armenian")[Հայերենը միայն պետական լեզու չէ՝ այլ նաեւ հոգեւոր հիշողության տանող ուղի է։]

#ts-script("armenian")[Դարերի ընթացքում գրված տարեգրությունները՝ սաղմոսները եւ ժողովրդական երգերը՝]

#ts-script("armenian")[այս լեզվով են պահպանել ժողովրդի ուրախությունն ու ցավը։]

= Russian (#ts-script("cyrillics")[русский])

Russian is an East Slavic language spoken by about 258 million people worldwide and is an official language in Russia, Belarus, Kazakhstan, and Kyrgyzstan.

#ts-script("cyrillics")[Мой дядя самых честных правил],

#ts-script("cyrillics")[когда не в шутку занемог],

#ts-script("cyrillics")[он уважать себя заставил]

#ts-script("cyrillics")[и лучше выдумать не мог].

= Hebrew (#ts-script("hebrew")[עברית])

Hebrew is a Semitic language spoken by over 9 million people worldwide and is the official language of Israel.

#ts-script("hebrew")[הַלֵּילָה אֲנִי חוֹלֵם עַל שָׂפוֹת הָעֵת בָּאוּ בַּחוֹף]
#ts-script("hebrew")[קוֹל הַגַּלִּים מְשַׁחֵק עִם הָרֶגַע]
#ts-script("hebrew")[וְהַלֵּב כּוֹסֵף לְבֵית כָּל שִׁירַי].

= Thai (#ts-script("thai")[ไทย])

Thai is the national language of Thailand and is spoken by more than 60 million people.

#ts-script("thai")[สายลมพัดผ่านทุ่งข้าวเขียวขจี]

#ts-script("thai")[กลิ่นดอกไม้โชยมากับเสียงระฆังวัด]

#ts-script("thai")[หัวใจคิดถึงรอยยิ้มและคำทักทายอบอุ่นของผู้คน].

= Bengali (#ts-script("bengali")[বাংলা])

Bengali is spoken by over 250 million people, mainly in Bangladesh and the Indian state of West Bengal.

#ts-script("bengali")[এই নদী মাঠ আর গাছের ছায়া]

#ts-script("bengali")[মানুষের হাসি আর শোকের গান]

#ts-script("bengali")[সব মিলিয়ে বাংলা ভাষা হৃদয়ে রাখে প্রাণের গল্প]#ts-script("devanagari")[।]

= Tibetan

#ts-script("tibetan")[བོད་ཡིག་གི་ཚིག་སྨོན་རྒྱལ་ཁབ་གི་སྙིང་ནས་བྱུང་]

#ts-script("tibetan")[རླུང་དང་སྣུམ་གྱི་སྒྲ་དང་མཉམ་དུ་སྐད་ཆ་སྣང་བ་བསྐུར།]

#ts-script("tibetan")[ལམ་སེང་གི་སྒྲོན་མ་བཞུགས་སྒོམ་དང་མཉམ་བཞག་པའི་ཡིད་ཀྱི་གདུང་འདུག།]

= Tamil (#ts-script("tamil")[தமிழ்])

#ts-script("tamil")[காற்றின் மணம் நனைந்து வரும்]
#ts-script("tamil")[பாட்டின் சொல் மனதில் நிற்கும்]
#ts-script("tamil")[தமிழ் மண்ணின் நெஞ்சில் வாழும் மரபின் இனிமை].

= Amharic (#ts-script("ethiopicfull")[አማርኛ])

Amharic is a Semitic language spoken mainly in Ethiopia.

#ts-script("ethiopicfull")[አማርኛ በኢትዮጵያ የመንግሥት ቋንቋ እና የብዙ ብሔሮች መገናኛ መንገድ ናት።]

#ts-script("ethiopicfull")[መዝሙሮች፣ ታሪካዊ ዘገባዎች እና የዕለት ተዕለት ተወላጅ ቃላት ውስጥ ይህች ቋንቋ የሕይወትን ድምጽ ታትማለች።]

= Burmese (#ts-script("myanmarfull")[မြန်မာ])

Burmese is the official language of Myanmar.

and over 40 million total speakers use it.

#ts-script("myanmarfull")[မြန်မာဘာသာကို ရှေးအခေတ်ကပင် ဗိမာန်၊]

#ts-script("myanmarfull")[ရာဇဝင်စာအုပ်တွေထဲက ဗျာဒိတ်စာနဲ့အတူ]

#ts-script("myanmarfull")[ဆက်ခံလာကြတယ်။]
