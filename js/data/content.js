// محتوى التصنيفات.
// type:
//   flag   → صورة علم من assets/flags
//   logo   → شعار (SVG من simple-icons) بلونه
//   capital→ علم ودولة، والجواب عاصمتها
//   wiki   → صورة تنجاب من ويكيبيديا وقت اللعب. كل عنصر [الجواب، عنوان المقالة بالإنكليزي]
//            (ويكيبيديا ترجع بس الصور الحرة، والعنصر اللي ما إله صورة ينشال تلقائياً)
(function () {
  const C = window.COUNTRIES;

  const wiki = list => list.map(([a, t]) => ({ a, t }));

  window.CATEGORIES = [
    {
      id: 'flags', short: 'أعلام', name: 'أعلام الدول', icon: '🏳️', type: 'flag', prompt: 'علم يا دولة؟',
      items: C.flags.map(f => ({ a: f.a, c: f.c })),
    },
    {
      id: 'apps', short: 'شعارات', name: 'شعارات تطبيقات وماركات', icon: '📱', type: 'logo', prompt: 'شنو هذا الشعار؟',
      items: window.LOGOS.apps,
    },
    {
      id: 'cars', short: 'سيارات', name: 'شعارات سيارات', icon: '🚗', type: 'logo', prompt: 'شعار يا سيارة؟',
      items: window.LOGOS.cars,
    },
    {
      id: 'capitals', short: 'عواصم', name: 'عواصم الدول', icon: '🏙️', type: 'capital', prompt: 'شنو عاصمة هاي الدولة؟',
      items: [
        ['iq', 'العراق', 'بغداد'], ['sa', 'السعودية', 'الرياض'], ['eg', 'مصر', 'القاهرة'], ['jo', 'الأردن', 'عمّان'],
        ['sy', 'سوريا', 'دمشق'], ['lb', 'لبنان', 'بيروت'], ['ae', 'الإمارات', 'أبوظبي'], ['qa', 'قطر', 'الدوحة'],
        ['bh', 'البحرين', 'المنامة'], ['om', 'عُمان', 'مسقط'], ['ye', 'اليمن', 'صنعاء'], ['ma', 'المغرب', 'الرباط'],
        ['ly', 'ليبيا', 'طرابلس'], ['sd', 'السودان', 'الخرطوم'], ['ps', 'فلسطين', 'القدس'], ['tr', 'تركيا', 'أنقرة'],
        ['ir', 'إيران', 'طهران'], ['pk', 'باكستان', 'إسلام آباد'], ['af', 'أفغانستان', 'كابل'], ['in', 'الهند', 'نيودلهي'],
        ['cn', 'الصين', 'بكين'], ['jp', 'اليابان', 'طوكيو'], ['kr', 'كوريا الجنوبية', 'سيول'], ['ru', 'روسيا', 'موسكو'],
        ['us', 'أمريكا', 'واشنطن'], ['ca', 'كندا', 'أوتاوا'], ['mx', 'المكسيك', 'مكسيكو سيتي'], ['br', 'البرازيل', 'برازيليا'],
        ['ar', 'الأرجنتين', 'بوينس آيرس'], ['gb', 'بريطانيا', 'لندن'], ['fr', 'فرنسا', 'باريس'], ['de', 'ألمانيا', 'برلين'],
        ['it', 'إيطاليا', 'روما'], ['es', 'إسبانيا', 'مدريد'], ['pt', 'البرتغال', 'لشبونة'], ['nl', 'هولندا', 'أمستردام'],
        ['be', 'بلجيكا', 'بروكسل'], ['ch', 'سويسرا', 'برن'], ['at', 'النمسا', 'فيينا'], ['gr', 'اليونان', 'أثينا'],
        ['se', 'السويد', 'ستوكهولم'], ['no', 'النرويج', 'أوسلو'], ['dk', 'الدنمارك', 'كوبنهاغن'], ['ua', 'أوكرانيا', 'كييف'],
        ['pl', 'بولندا', 'وارسو'], ['au', 'أستراليا', 'كانبرا'], ['id', 'إندونيسيا', 'جاكرتا'], ['my', 'ماليزيا', 'كوالالمبور'],
        ['th', 'تايلاند', 'بانكوك'], ['ng', 'نيجيريا', 'أبوجا'], ['ke', 'كينيا', 'نيروبي'], ['et', 'إثيوبيا', 'أديس أبابا'],
        ['so', 'الصومال', 'مقديشو'], ['mr', 'موريتانيا', 'نواكشوط'], ['cu', 'كوبا', 'هافانا'], ['ie', 'أيرلندا', 'دبلن'],
      ].map(([c, q, a]) => ({ c, q, a })),
    },
    {
      id: 'players', short: 'لاعبين', name: 'لاعبين كورة', icon: '⚽', type: 'wiki', prompt: 'منو هذا اللاعب؟',
      items: wiki([
        ['ميسي', 'Lionel Messi'], ['كريستيانو رونالدو', 'Cristiano Ronaldo'], ['نيمار', 'Neymar'],
        ['مبابي', 'Kylian Mbappé'], ['محمد صلاح', 'Mohamed Salah'], ['هالاند', 'Erling Haaland'],
        ['بنزيمة', 'Karim Benzema'], ['مودريتش', 'Luka Modrić'], ['زين الدين زيدان', 'Zinedine Zidane'],
        ['رونالدينيو', 'Ronaldinho'], ['رونالدو البرازيلي', 'Ronaldo (Brazilian footballer)'],
        ['بيكهام', 'David Beckham'], ['إبراهيموفيتش', 'Zlatan Ibrahimović'], ['ليفاندوفسكي', 'Robert Lewandowski'],
        ['دي بروين', 'Kevin De Bruyne'], ['فينيسيوس', 'Vinícius Júnior'], ['بيلينغهام', 'Jude Bellingham'],
        ['لامين يامال', 'Lamine Yamal'], ['رياض محرز', 'Riyad Mahrez'], ['أشرف حكيمي', 'Achraf Hakimi'],
        ['ساديو ماني', 'Sadio Mané'], ['واين روني', 'Wayne Rooney'], ['تيري هنري', 'Thierry Henry'],
        ['إنييستا', 'Andrés Iniesta'], ['تشافي', 'Xavi'], ['سيرخيو راموس', 'Sergio Ramos'],
        ['بوفون', 'Gianluigi Buffon'], ['مالديني', 'Paolo Maldini'], ['مارادونا', 'Diego Maradona'],
        ['بيليه', 'Pelé'], ['كاكا', 'Kaká'], ['غاريث بيل', 'Gareth Bale'], ['هاري كين', 'Harry Kane'],
        ['غريزمان', 'Antoine Griezmann'], ['نوير', 'Manuel Neuer'], ['كاسياس', 'Iker Casillas'],
        ['بيرلو', 'Andrea Pirlo'], ['توتي', 'Francesco Totti'], ['جيرارد', 'Steven Gerrard'],
        ['لامبارد', 'Frank Lampard'], ['دروغبا', 'Didier Drogba'], ['صامويل إيتو', "Samuel Eto'o"],
        ['سواريز', 'Luis Suárez'], ['أغويرو', 'Sergio Agüero'], ['يونس محمود', 'Younis Mahmoud'],
        ['حكيم زياش', 'Hakim Ziyech'], ['سون هيونغ مين', 'Son Heung-min'], ['مسعود أوزيل', 'Mesut Özil'],
        ['توني كروس', 'Toni Kroos'], ['علي دائي', 'Ali Daei'], ['سالم الدوسري', 'Salem Al-Dawsari'],
        ['ياسين بونو', 'Yassine Bounou'], ['بيكيه', 'Gerard Piqué'],
        ['أيمن حسين', 'Aymen Hussein'], ['نشأت أكرم', 'Nashat Akram'], ['كيليان مبابي', 'Kylian Mbappé'],
      ]).filter((v, i, arr) => arr.findIndex(x => x.t === v.t) === i),
    },
    {
      id: 'actors', short: 'ممثلين', name: 'ممثلين', icon: '🎬', type: 'wiki', prompt: 'منو هذا الممثل؟',
      items: wiki([
        ['توم كروز', 'Tom Cruise'], ['ليوناردو دي كابريو', 'Leonardo DiCaprio'], ['براد بيت', 'Brad Pitt'],
        ['ويل سميث', 'Will Smith'], ['جوني ديب', 'Johnny Depp'], ['ذا روك', 'Dwayne Johnson'],
        ['جاكي شان', 'Jackie Chan'], ['أنجلينا جولي', 'Angelina Jolie'], ['مورغان فريمان', 'Morgan Freeman'],
        ['كيانو ريفز', 'Keanu Reeves'], ['توم هانكس', 'Tom Hanks'], ['روبرت داوني جونيور', 'Robert Downey Jr.'],
        ['سكارليت جوهانسون', 'Scarlett Johansson'], ['جيم كاري', 'Jim Carrey'], ['دينزل واشنطن', 'Denzel Washington'],
        ['آل باتشينو', 'Al Pacino'], ['روبرت دي نيرو', 'Robert De Niro'], ['جيسون ستاثام', 'Jason Statham'],
        ['فين ديزل', 'Vin Diesel'], ['مستر بين', 'Rowan Atkinson'], ['شارلي شابلن', 'Charlie Chaplin'],
        ['أرنولد شوارزنيغر', 'Arnold Schwarzenegger'], ['سيلفستر ستالون', 'Sylvester Stallone'],
        ['إيما واتسون', 'Emma Watson'], ['دانيال رادكليف', 'Daniel Radcliffe'], ['كريس هيمسورث', 'Chris Hemsworth'],
        ['رايان رينولدز', 'Ryan Reynolds'], ['هيو جاكمان', 'Hugh Jackman'], ['نيكولاس كيج', 'Nicolas Cage'],
        ['شاروخان', 'Shah Rukh Khan'], ['أميتاب باتشان', 'Amitabh Bachchan'], ['عامر خان', 'Aamir Khan'],
        ['سلمان خان', 'Salman Khan'], ['عادل إمام', 'Adel Emam'], ['عمر الشريف', 'Omar Sharif'],
        ['أحمد حلمي', 'Ahmed Helmy'], ['محمد هنيدي', 'Mohamed Henedi'], ['دريد لحام', 'Duraid Lahham'],
        ['يسرا', 'Yousra'], ['أحمد زكي', 'Ahmed Zaki (actor)'], ['جوني ديب', 'Johnny Depp'],
        ['مارلون براندو', 'Marlon Brando'], ['أودري هيبورن', 'Audrey Hepburn'], ['كيت وينسلت', 'Kate Winslet'],
        ['زندايا', 'Zendaya'], ['توم هولاند', 'Tom Holland'], ['مارغو روبي', 'Margot Robbie'],
      ]).filter((v, i, arr) => arr.findIndex(x => x.t === v.t) === i),
    },
    {
      id: 'singers', short: 'مغنيين', name: 'مغنيين', icon: '🎤', type: 'wiki', prompt: 'منو هذا المطرب؟',
      items: wiki([
        ['كاظم الساهر', 'Kadim Al Sahir'], ['أم كلثوم', 'Umm Kulthum'], ['فيروز', 'Fairuz'],
        ['عمرو دياب', 'Amr Diab'], ['نانسي عجرم', 'Nancy Ajram'], ['محمد عبده', 'Mohammed Abdu'],
        ['عبد الحليم حافظ', 'Abdel Halim Hafez'], ['إليسا', 'Elissa (singer)'], ['تامر حسني', 'Tamer Hosny'],
        ['هيفاء وهبي', 'Haifa Wehbe'], ['راشد الماجد', 'Rashed Al-Majed'], ['صابر الرباعي', 'Saber Rebaï'],
        ['حسين الجسمي', 'Hussain Al Jassmi'], ['راغب علامة', 'Ragheb Alama'], ['وائل كفوري', 'Wael Kfoury'],
        ['أصالة', 'Assala Nasri'], ['إلهام المدفعي', 'Ilham al-Madfai'], ['ماجد المهندس', 'Majid Al Mohandis'],
        ['محمد منير', 'Mohamed Mounir'], ['وردة الجزائرية', 'Warda Al-Jazairia'], ['صباح فخري', 'Sabah Fakhri'],
        ['مايكل جاكسون', 'Michael Jackson'], ['شاكيرا', 'Shakira'], ['إد شيران', 'Ed Sheeran'],
        ['تايلور سويفت', 'Taylor Swift'], ['جاستن بيبر', 'Justin Bieber'], ['ريهانا', 'Rihanna'],
        ['أديل', 'Adele'], ['إيمنيم', 'Eminem'], ['إلفيس بريسلي', 'Elvis Presley'],
        ['فريدي ميركوري', 'Freddie Mercury'], ['بوب مارلي', 'Bob Marley'], ['سيلين ديون', 'Celine Dion'],
        ['ليدي غاغا', 'Lady Gaga'], ['برونو مارس', 'Bruno Mars'], ['ذا ويكند', 'The Weeknd'],
        ['بيونسيه', 'Beyoncé'], ['دريك', 'Drake (musician)'], ['بيلي آيليش', 'Billie Eilish'],
      ]),
    },
    {
      id: 'places', short: 'معالم', name: 'أماكن ومعالم', icon: '🏛️', type: 'wiki', prompt: 'وين هذا المكان؟',
      items: wiki([
        ['برج إيفل', 'Eiffel Tower'], ['الأهرامات', 'Great Pyramid of Giza'], ['تاج محل', 'Taj Mahal'],
        ['تمثال الحرية', 'Statue of Liberty'], ['الكولوسيوم', 'Colosseum'], ['سور الصين العظيم', 'Great Wall of China'],
        ['برج خليفة', 'Burj Khalifa'], ['بيغ بن', 'Big Ben'], ['برج بيزا المائل', 'Leaning Tower of Pisa'],
        ['البتراء', 'Petra'], ['تمثال المسيح الفادي', 'Christ the Redeemer (statue)'], ['ماتشو بيتشو', 'Machu Picchu'],
        ['دار أوبرا سيدني', 'Sydney Opera House'], ['ملوية سامراء', 'Great Mosque of Samarra'],
        ['زقورة أور', 'Ziggurat of Ur'], ['طاق كسرى', 'Taq Kasra'], ['نصب الشهيد', 'Al-Shaheed Monument'],
        ['بوابة عشتار', 'Ishtar Gate'], ['المسجد الحرام', 'Great Mosque of Mecca'], ['المسجد النبوي', "Prophet's Mosque"],
        ['قبة الصخرة', 'Dome of the Rock'], ['ساغرادا فاميليا', 'Sagrada Família'], ['جسر البوابة الذهبية', 'Golden Gate Bridge'],
        ['جسر البرج', 'Tower Bridge'], ['بوابة براندنبورغ', 'Brandenburg Gate'], ['الأكروبوليس', 'Acropolis of Athens'],
        ['ستونهنج', 'Stonehenge'], ['جبل فوجي', 'Mount Fuji'], ['شلالات نياغرا', 'Niagara Falls'],
        ['أنغكور وات', 'Angkor Wat'], ['كاتدرائية القديس باسيل', "Saint Basil's Cathedral"],
        ['جامع الشيخ زايد', 'Sheikh Zayed Grand Mosque'], ['آيا صوفيا', 'Hagia Sophia'],
        ['الجامع الأزرق', 'Sultan Ahmed Mosque'], ['برج العرب', 'Burj Al Arab'], ['أبراج الكويت', 'Kuwait Towers'],
        ['برجا بتروناس', 'Petronas Towers'], ['جبل إيفرست', 'Mount Everest'], ['قوس النصر', 'Arc de Triomphe'],
        ['قصر الحمراء', 'Alhambra'], ['أبو الهول', 'Great Sphinx of Giza'], ['تمثال الحرية', 'Statue of Liberty'],
      ]).filter((v, i, arr) => arr.findIndex(x => x.t === v.t) === i),
    },
    {
      id: 'animals', short: 'حيوانات', name: 'حيوانات', icon: '🦁', type: 'wiki', prompt: 'شنو هذا الحيوان؟',
      items: wiki([
        ['أسد', 'Lion'], ['نمر', 'Tiger'], ['فيل', 'African bush elephant'], ['زرافة', 'Giraffe'],
        ['حمار وحشي', 'Plains zebra'], ['كنغر', 'Red kangaroo'], ['كوالا', 'Koala'], ['باندا', 'Giant panda'],
        ['بطريق', 'Emperor penguin'], ['جمل', 'Dromedary'], ['دب قطبي', 'Polar bear'], ['فهد', 'Cheetah'],
        ['فرس النهر', 'Hippopotamus'], ['وحيد القرن', 'White rhinoceros'], ['غوريلا', 'Western gorilla'],
        ['تمساح', 'Nile crocodile'], ['فلامنغو', 'American flamingo'], ['طاووس', 'Indian peafowl'],
        ['بومة', 'Barn owl'], ['أخطبوط', 'Common octopus'], ['دولفين', 'Common bottlenose dolphin'],
        ['قرش أبيض', 'Great white shark'], ['كسلان', 'Brown-throated sloth'], ['خلد الماء (بلاتيبوس)', 'Platypus'],
        ['ثعلب', 'Red fox'], ['قنفذ', 'European hedgehog'], ['ذيب', 'Wolf'], ['نعامة', 'Common ostrich'],
        ['حرباية', 'Panther chameleon'], ['نسر أصلع', 'Bald eagle'], ['أكسولوتل', 'Axolotl'], ['ميركات', 'Meerkat'],
        ['راكون', 'Raccoon'], ['أوكابي', 'Okapi'], ['ضبع', 'Spotted hyena'], ['حصان البحر', 'Seahorse'],
        ['ببغاء المكاو', 'Scarlet macaw'], ['لاما', 'Llama'], ['سنجاب', 'Red squirrel'], ['غزال', 'Dorcas gazelle'],
      ]),
    },
    {
      id: 'food', short: 'أكلات', name: 'أكلات', icon: '🍕', type: 'wiki', prompt: 'شنو هاي الأكلة؟',
      items: wiki([
        ['بيتزا', 'Pizza'], ['سوشي', 'Sushi'], ['همبرگر', 'Hamburger'], ['فلافل', 'Falafel'], ['حمص', 'Hummus'],
        ['شاورما', 'Shawarma'], ['كباب', 'Kebab'], ['دولمة', 'Dolma'], ['برياني', 'Biryani'], ['كنافة', 'Knafeh'],
        ['بقلاوة', 'Baklava'], ['تبولة', 'Tabbouleh'], ['مسگوف', 'Masgouf'], ['كليچة', 'Kleicha'], ['باييا', 'Paella'],
        ['كرواسون', 'Croissant'], ['تاكو', 'Taco'], ['رامن', 'Ramen'], ['پانكيك', 'Pancake'], ['وافل', 'Waffle'],
        ['دونات', 'Doughnut'], ['سباگيتي', 'Spaghetti'], ['منسف', 'Mansaf'], ['كبسة', 'Kabsa'], ['كشري', 'Koshary'],
        ['شكشوكة', 'Shakshouka'], ['فتوش', 'Fattoush'], ['لازانيا', 'Lasagna'], ['تشوروس', 'Churro'],
        ['مندي', 'Mandi (food)'], ['پاپكورن', 'Popcorn'], ['آيس كريم', 'Ice cream'], ['كبة', 'Kibbeh'],
        ['تشيز كيك', 'Cheesecake'], ['هوت دوگ', 'Hot dog'], ['بابا غنوج', 'Baba ghanoush'], ['محشي', 'Mahshi'],
      ]),
    },
  ];
})();
