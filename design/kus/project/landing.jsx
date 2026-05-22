// Кусь (Doggi) landing page — all 12 sections.
// Accepts {mobile} prop to render mobile or desktop layout.
// Color system in landingTheme; all sections compose into <Landing/>.

const landingTheme = {
  primary: '#055ba9',
  primaryDark: '#04467f',
  primarySoft: '#e6f0fa',
  primarySofter: '#f3f8fd',
  accent: '#f59e0b',         // warm amber CTA
  accentDeep: '#d97706',
  accentSoft: '#fef3c7',
  ink: '#0b1726',
  inkSoft: '#475569',
  inkLight: '#94a3b8',
  border: '#e2e8f0',
  borderSoft: '#eef2f7',
  bg: '#ffffff',
  bgSoft: '#f7f9fc',
  bgWarm: '#fdfbf7',
};

// Unsplash dog photos (live URLs as agreed). Keep narrow and curated.
const photos = {
  hero: 'https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=1200&q=80&auto=format&fit=crop',
  team: 'https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=900&q=80&auto=format&fit=crop',
  bowl: 'https://images.unsplash.com/photo-1568640347023-a616a30bc3bd?w=900&q=80&auto=format&fit=crop',
  finalCta: 'https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1400&q=80&auto=format&fit=crop',
  testimonial1: 'https://images.unsplash.com/photo-1551717743-49959800b1f6?w=200&q=80&auto=format&fit=crop&crop=faces',
  testimonial2: 'https://images.unsplash.com/photo-1583511655802-41f30aef99a2?w=200&q=80&auto=format&fit=crop&crop=faces',
  testimonial3: 'https://images.unsplash.com/photo-1546238232-20216dec9f72?w=200&q=80&auto=format&fit=crop&crop=faces',
};

// Logo wordmark ---------------------------------------------------------------

const Logo = ({ small, white }) => (
  <div style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: white ? '#fff' : landingTheme.primary,
    fontWeight: 800,
    fontSize: small ? 20 : 22,
    letterSpacing: '-0.02em',
  }}>
    <span style={{
      width: small ? 28 : 32,
      height: small ? 28 : 32,
      borderRadius: 10,
      background: white ? '#fff' : landingTheme.primary,
      color: white ? landingTheme.primary : '#fff',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <IconPaw size={small ? 16 : 18} strokeWidth={2.2} />
    </span>
    Кусь
  </div>
);

// Section heading helpers -----------------------------------------------------

const SectionEyebrow = ({ children }) => (
  <div style={{
    display: 'inline-block',
    fontSize: 12,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.14em',
    color: landingTheme.primary,
    background: landingTheme.primarySoft,
    padding: '6px 12px',
    borderRadius: 100,
    marginBottom: 16,
  }}>{children}</div>
);

const SectionTitle = ({ children, mobile, align = 'left', white }) => (
  <h2 style={{
    margin: 0,
    fontSize: mobile ? 30 : 48,
    fontWeight: 700,
    letterSpacing: '-0.025em',
    lineHeight: 1.1,
    color: white ? '#fff' : landingTheme.ink,
    textAlign: align,
    textWrap: 'balance',
  }}>{children}</h2>
);

const SectionSub = ({ children, mobile, align = 'left' }) => (
  <p style={{
    margin: '14px 0 0',
    fontSize: mobile ? 16 : 18,
    lineHeight: 1.55,
    color: landingTheme.inkSoft,
    textAlign: align,
    maxWidth: 640,
    textWrap: 'pretty',
  }}>{children}</p>
);

// Reusable Section wrapper — controls padding & max width
const Section = ({ children, mobile, bg, py, id }) => (
  <section id={id} style={{
    background: bg || 'transparent',
    padding: mobile
      ? `${py?.[0] || 64}px 20px`
      : `${py?.[1] || 110}px 80px`,
  }}>
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>{children}</div>
  </section>
);

const PrimaryButton = ({ children, large, accent, full, onClick }) => (
  <button
    onClick={onClick}
    style={{
      padding: large ? '18px 30px' : '14px 22px',
      fontSize: large ? 17 : 15,
      fontWeight: 700,
      fontFamily: 'inherit',
      color: '#fff',
      background: accent ? landingTheme.accent : landingTheme.primary,
      border: 'none',
      borderRadius: 12,
      cursor: 'pointer',
      letterSpacing: '-0.005em',
      boxShadow: accent
        ? '0 10px 24px -8px rgba(245, 158, 11, 0.55)'
        : '0 10px 24px -10px rgba(5, 91, 169, 0.4)',
      transition: 'transform .15s',
      width: full ? '100%' : 'auto',
    }}
  >{children}</button>
);

const GhostButton = ({ children, onClick }) => (
  <button
    onClick={onClick}
    style={{
      padding: '14px 22px',
      fontSize: 15,
      fontWeight: 600,
      fontFamily: 'inherit',
      color: landingTheme.ink,
      background: 'transparent',
      border: `1.5px solid ${landingTheme.border}`,
      borderRadius: 12,
      cursor: 'pointer',
    }}
  >{children}</button>
);

// 1. Header -------------------------------------------------------------------

const Header = ({ mobile }) => {
  const links = ['Сухой корм', 'Натуралка', 'Как мы работаем', 'Контакты'];
  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      background: 'rgba(255,255,255,0.85)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: `1px solid ${landingTheme.borderSoft}`,
    }}>
      <div style={{
        maxWidth: 1200,
        margin: '0 auto',
        padding: mobile ? '14px 20px' : '18px 80px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
      }}>
        <Logo small={mobile} />
        {!mobile && (
          <nav style={{ display: 'flex', gap: 28 }}>
            {links.map(l => (
              <a key={l} href="#" style={{
                fontSize: 15,
                color: landingTheme.inkSoft,
                textDecoration: 'none',
                fontWeight: 500,
              }}>{l}</a>
            ))}
          </nav>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            padding: mobile ? '9px 14px' : '11px 18px',
            fontSize: mobile ? 13 : 14,
            fontWeight: 600,
            fontFamily: 'inherit',
            color: '#fff',
            background: landingTheme.primary,
            border: 'none',
            borderRadius: 10,
            cursor: 'pointer',
          }}>
            <IconTelegram size={16} strokeWidth={2} />
            Чат-бот Кусь
          </button>
          {mobile && (
            <button style={{
              width: 38, height: 38, padding: 0,
              background: 'transparent',
              border: `1px solid ${landingTheme.border}`,
              borderRadius: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
              color: landingTheme.ink,
            }}>
              <IconMenu size={20} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

// 2. Hero ---------------------------------------------------------------------

const Hero = ({ mobile }) => (
  <Section mobile={mobile} py={[40, 80]}>
    <div style={{
      display: 'grid',
      gridTemplateColumns: mobile ? '1fr' : '1.1fr 1fr',
      gap: mobile ? 32 : 64,
      alignItems: 'center',
    }}>
      <div>
        <SectionEyebrow>
          <span style={{ color: landingTheme.accentDeep }}>●</span>{' '}Уже 1 200+ собак на правильном рационе
        </SectionEyebrow>
        <h1 style={{
          margin: 0,
          fontSize: mobile ? 44 : 76,
          fontWeight: 800,
          letterSpacing: '-0.035em',
          lineHeight: 0.98,
          color: landingTheme.ink,
        }}>
          Кормите собаку<br />
          <span style={{ color: landingTheme.primary }}>правильно</span>
        </h1>
        <p style={{
          margin: mobile ? '20px 0 0' : '28px 0 0',
          fontSize: mobile ? 17 : 20,
          lineHeight: 1.5,
          color: landingTheme.inkSoft,
          maxWidth: 520,
          textWrap: 'pretty',
        }}>
          Поможем подобрать идеальный рацион — сухой корм или натуралку.
          Без гугла, без калькулятора, без риска ошибиться.
        </p>
        <div style={{
          display: 'flex',
          gap: 12,
          marginTop: mobile ? 28 : 36,
          flexDirection: mobile ? 'column' : 'row',
        }}>
          <PrimaryButton large accent full={mobile}>Подобрать рацион →</PrimaryButton>
          <GhostButton>Как мы работаем</GhostButton>
        </div>
        <div style={{
          marginTop: 32,
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex' }}>
            {[photos.testimonial1, photos.testimonial2, photos.testimonial3].map((src, i) => (
              <div key={i} style={{
                width: 36, height: 36,
                borderRadius: 18,
                background: `url(${src}) center/cover`,
                border: '2px solid #fff',
                marginLeft: i > 0 ? -10 : 0,
              }} />
            ))}
          </div>
          <div>
            <div style={{ display: 'flex', gap: 2, color: landingTheme.accent }}>
              {[1, 2, 3, 4, 5].map(i => <IconStar key={i} size={14} strokeWidth={0} color={landingTheme.accent} style={{ fill: landingTheme.accent }} />)}
            </div>
            <div style={{ fontSize: 13, color: landingTheme.inkSoft, marginTop: 2 }}>
              4,9 из 5 — по 340+ отзывам
            </div>
          </div>
        </div>
      </div>

      {/* Hero image */}
      <div style={{
        position: 'relative',
        aspectRatio: mobile ? '4 / 3' : '5 / 6',
        borderRadius: 28,
        overflow: 'hidden',
        background: `linear-gradient(135deg, ${landingTheme.primarySoft}, ${landingTheme.bgWarm})`,
      }}>
        <img
          src={photos.hero}
          alt="Счастливая собака ест из миски"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
        {/* Floating credential card */}
        <div style={{
          position: 'absolute',
          left: mobile ? 16 : 24,
          bottom: mobile ? 16 : 24,
          background: 'rgba(255,255,255,0.96)',
          backdropFilter: 'blur(8px)',
          borderRadius: 16,
          padding: '14px 18px',
          boxShadow: '0 16px 40px -12px rgba(11, 23, 38, 0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          <div style={{
            width: 40, height: 40,
            borderRadius: 10,
            background: landingTheme.primarySoft,
            color: landingTheme.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <IconCheck size={22} strokeWidth={2.5} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: landingTheme.ink }}>В кинологии с 2005</div>
            <div style={{ fontSize: 12, color: landingTheme.inkSoft }}>Проверено ветеринарами и диетологами</div>
          </div>
        </div>
      </div>
    </div>
  </Section>
);

// 3. Problems -----------------------------------------------------------------

const Problems = ({ mobile }) => {
  const items = [
    { Icon: IconScratch, title: 'Аллергия и зуд', text: 'Собака чешется, шерсть тусклая, уши красные. Вы перепробовали 5 кормов — ничего не помогает. Ветеринар разводит руками: «Попробуйте ещё вот этот…»' },
    { Icon: IconScales, title: 'Страх навредить', text: 'Хотите перевести на натуралку, но боитесь. Сколько мяса? Какие кости можно? А витамины? Кажется, нужно пройти курсы диетологии, чтобы накормить собаку.' },
    { Icon: IconBowl, title: 'Отказ от еды', text: 'Купили дорогой корм по совету блогера — собака понюхала и ушла. Деньги на ветер, а питомец голодный.' },
    { Icon: IconLabel, title: 'Обман на этикетке', text: '«С ягнёнком и рисом» — а на деле кукуруза, перья и ароматизаторы. Вы не маркетолог, чтобы расшифровывать составы.' },
  ];
  return (
    <Section mobile={mobile} bg={landingTheme.bgSoft}>
      <div style={{ textAlign: mobile ? 'left' : 'center', marginBottom: mobile ? 32 : 64 }}>
        <SectionEyebrow>Знакомо?</SectionEyebrow>
        <SectionTitle mobile={mobile} align={mobile ? 'left' : 'center'}>
          Если хоть одно — это про вас,<br />мы поможем
        </SectionTitle>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? '1fr' : 'repeat(4, 1fr)',
        gap: 16,
      }}>
        {items.map(({ Icon, title, text }, i) => (
          <div key={i} style={{
            background: '#fff',
            border: `1px solid ${landingTheme.borderSoft}`,
            borderRadius: 18,
            padding: mobile ? 22 : 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}>
            <div style={{
              width: 48, height: 48,
              borderRadius: 12,
              background: landingTheme.primarySoft,
              color: landingTheme.primary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 4,
            }}>
              <Icon size={26} />
            </div>
            <div style={{ fontSize: 17, fontWeight: 700, color: landingTheme.ink }}>{title}</div>
            <div style={{ fontSize: 14.5, lineHeight: 1.55, color: landingTheme.inkSoft }}>{text}</div>
          </div>
        ))}
      </div>
    </Section>
  );
};

// 4. Who we are ---------------------------------------------------------------

const WhoWeAre = ({ mobile }) => {
  const items = [
    { Icon: IconHome, title: 'Свой центр дрессировки и питомник', text: 'Мы вырастили поколения здоровых собак. Каждый рацион проверен на практике.' },
    { Icon: IconHotel, title: 'Зоогостиница и сеть груминг-салонов', text: 'Видим сотни собак на разных типах питания и знаем, что работает.' },
    { Icon: IconStore, title: 'Опыт управления зоомагазином', text: 'Знаем рынок кормов изнутри: какие бренды честные, а какие платят за полку.' },
  ];
  return (
    <Section mobile={mobile}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? '1fr' : '1fr 1.4fr',
        gap: mobile ? 28 : 64,
        alignItems: 'start',
      }}>
        <div style={{ position: mobile ? 'static' : 'sticky', top: 120 }}>
          <SectionEyebrow>О нас</SectionEyebrow>
          <SectionTitle mobile={mobile}>
            Почему нам<br />доверяют тысячи владельцев
          </SectionTitle>
          <SectionSub mobile={mobile}>
            Мы не теоретики, начитавшиеся форумов. Мы в кинологии с 2005 года и знаем эту «кухню» изнутри.
          </SectionSub>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {items.map(({ Icon, title, text }, i) => (
            <div key={i} style={{
              padding: mobile ? 22 : 28,
              border: `1px solid ${landingTheme.borderSoft}`,
              borderRadius: 18,
              background: '#fff',
              display: 'flex',
              gap: 18,
            }}>
              <div style={{
                flex: '0 0 auto',
                width: 52, height: 52,
                borderRadius: 12,
                background: landingTheme.primarySoft,
                color: landingTheme.primary,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={28} />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: landingTheme.ink, marginBottom: 6 }}>{title}</div>
                <div style={{ fontSize: 15, lineHeight: 1.55, color: landingTheme.inkSoft }}>{text}</div>
              </div>
            </div>
          ))}
          <div style={{
            padding: mobile ? 18 : 22,
            background: landingTheme.primary,
            borderRadius: 18,
            color: '#fff',
            display: 'flex',
            gap: 14,
            alignItems: 'center',
          }}>
            <IconCheck size={28} strokeWidth={2.5} />
            <div style={{ fontSize: 15, fontWeight: 500, lineHeight: 1.5 }}>
              Все рекомендации основаны на совместной работе с ветеринарами и диетологами.
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
};

// 5. Services -----------------------------------------------------------------

const ServiceCard = ({ Icon, title, price, items, cta, mobile, highlight }) => (
  <div style={{
    flex: 1,
    background: '#fff',
    border: `1.5px solid ${highlight ? landingTheme.primary : landingTheme.borderSoft}`,
    borderRadius: 24,
    padding: mobile ? 24 : 36,
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    boxShadow: highlight ? '0 20px 50px -20px rgba(5, 91, 169, 0.25)' : 'none',
  }}>
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: 18,
    }}>
      <div style={{
        width: 64, height: 64,
        borderRadius: 16,
        background: landingTheme.primarySoft,
        color: landingTheme.primary,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={36} strokeWidth={1.6} />
      </div>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
      }}>
        <div style={{ fontSize: 12, color: landingTheme.inkLight, marginBottom: 2 }}>от</div>
        <div style={{ fontSize: mobile ? 32 : 40, fontWeight: 800, color: landingTheme.ink, letterSpacing: '-0.03em', lineHeight: 1 }}>
          {price}<span style={{ fontSize: '0.45em', color: landingTheme.inkSoft, fontWeight: 600, marginLeft: 4 }}>₽</span>
        </div>
      </div>
    </div>
    <h3 style={{
      margin: 0,
      fontSize: mobile ? 24 : 28,
      fontWeight: 700,
      letterSpacing: '-0.02em',
      color: landingTheme.ink,
      marginBottom: 22,
    }}>{title}</h3>
    <ul style={{
      listStyle: 'none',
      padding: 0,
      margin: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      marginBottom: 28,
      flex: 1,
    }}>
      {items.map((it, i) => (
        <li key={i} style={{
          display: 'flex',
          gap: 12,
          fontSize: 14.5,
          color: landingTheme.ink,
          lineHeight: 1.5,
        }}>
          <span style={{
            flex: '0 0 auto',
            width: 22, height: 22,
            marginTop: 1,
            borderRadius: 11,
            background: landingTheme.primarySoft,
            color: landingTheme.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <IconCheck size={13} strokeWidth={3} />
          </span>
          <span><strong style={{ fontWeight: 600 }}>{it.title}</strong> — <span style={{ color: landingTheme.inkSoft }}>{it.desc}</span></span>
        </li>
      ))}
    </ul>
    <PrimaryButton large accent full>{cta}</PrimaryButton>
  </div>
);

const Services = ({ mobile }) => (
  <Section id="services" mobile={mobile} bg={landingTheme.bgSoft}>
    <div style={{ textAlign: mobile ? 'left' : 'center', marginBottom: mobile ? 32 : 56 }}>
      <SectionEyebrow>Услуги</SectionEyebrow>
      <SectionTitle mobile={mobile} align={mobile ? 'left' : 'center'}>
        Выберите свой вариант
      </SectionTitle>
      <SectionSub mobile={mobile} align={mobile ? 'left' : 'center'}>
        Две одинаково проверенные программы. Одна цена, один результат — здоровая собака на правильном рационе.
      </SectionSub>
    </div>
    <div style={{
      display: 'flex',
      gap: 20,
      flexDirection: mobile ? 'column' : 'row',
    }}>
      <ServiceCard
        mobile={mobile}
        Icon={IconKibble}
        title="Подбор сухого корма"
        price="990"
        cta="Подобрать корм — 990 ₽"
        items={[
          { title: 'Анализ текущего корма', desc: 'разберём состав и покажем, за что вы реально платите' },
          { title: 'Персональный ТОП-5', desc: 'кормов под вашу собаку: породу, возраст, аллергии, бюджет' },
          { title: 'Разные ценовые категории', desc: 'от «честного бюджета» до «люкса» — выбираете сами' },
          { title: 'Прямые ссылки на покупку', desc: 'кликнули и заказали, искать ничего не нужно' },
          { title: 'Инструкция по переходу', desc: 'плавная смена корма без срывов ЖКТ' },
          { title: 'Советы по экономии', desc: 'как платить меньше за качественный корм' },
        ]}
      />
      <ServiceCard
        mobile={mobile}
        highlight
        Icon={IconMeat}
        title="Расчёт натурального рациона"
        price="1 390"
        cta="Рассчитать рацион — 1 390 ₽"
        items={[
          { title: 'Индивидуальный расчёт граммовок', desc: 'точные цифры на каждое кормление' },
          { title: 'Список продуктов', desc: 'что именно покупать, без лишнего' },
          { title: 'Учёт предпочтений', desc: 'BARF (сырое) или варка — как удобнее' },
          { title: 'Баланс Ca/P и витаминов', desc: 'уже рассчитан, не нужно думать' },
          { title: 'Витаминные добавки', desc: 'что, сколько, какой фирмы' },
          { title: 'Схема перевода с сушки', desc: 'пошагово, мягко, без срывов ЖКТ' },
          { title: 'Советы по закупкам мяса', desc: 'где выгоднее покупать' },
        ]}
      />
    </div>
    <div style={{
      textAlign: 'center',
      marginTop: 24,
      fontSize: 13.5,
      color: landingTheme.inkSoft,
    }}>
      Оплата онлайн · Результат в течение 3 рабочих дней · Поддержка 7 дней после получения
    </div>
  </Section>
);

// 6. What you get -------------------------------------------------------------

const PDFMockup = ({ mobile }) => (
  // Tablet-like frame holding a stylized PDF preview.
  <div style={{
    background: '#1f2937',
    borderRadius: 28,
    padding: 14,
    boxShadow: '0 40px 80px -30px rgba(11, 23, 38, 0.4)',
    width: '100%',
    maxWidth: 460,
    transform: mobile ? 'none' : 'rotate(-2deg)',
  }}>
    <div style={{
      background: '#fff',
      borderRadius: 16,
      padding: 22,
      aspectRatio: '3 / 4',
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* fake PDF header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <Logo small />
        <div style={{ fontSize: 10, color: landingTheme.inkLight, fontWeight: 500 }}>Рацион №А-1247</div>
      </div>
      <div style={{
        height: 1, background: landingTheme.borderSoft, marginBottom: 14,
      }} />
      <div style={{ fontSize: 11, color: landingTheme.inkSoft, marginBottom: 4 }}>Для собаки</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: landingTheme.ink, marginBottom: 14 }}>Барон, лабрадор, 4 года</div>
      <div style={{
        background: landingTheme.primarySoft,
        borderRadius: 10,
        padding: '10px 12px',
        marginBottom: 14,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div>
          <div style={{ fontSize: 10, color: landingTheme.primary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Суточная норма</div>
          <div style={{ fontSize: 20, fontWeight: 800, color: landingTheme.ink }}>620 г <span style={{ fontSize: 12, fontWeight: 500, color: landingTheme.inkSoft }}>/ день</span></div>
        </div>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: landingTheme.primary }}>
          <IconBowl size={22} />
        </div>
      </div>
      <div style={{ fontSize: 11, fontWeight: 700, color: landingTheme.ink, marginBottom: 8 }}>Раскладка на день</div>
      {[
        ['Говядина (мясо)', '210 г'],
        ['Куриные шейки', '120 г'],
        ['Рубец', '90 г'],
        ['Печень', '40 г'],
        ['Овощи, кабачок', '110 г'],
        ['Творог 5%', '50 г'],
      ].map(([k, v], i) => (
        <div key={i} style={{
          display: 'flex', justifyContent: 'space-between',
          fontSize: 11.5,
          padding: '5px 0',
          borderBottom: i < 5 ? `1px dashed ${landingTheme.borderSoft}` : 'none',
        }}>
          <span style={{ color: landingTheme.inkSoft }}>{k}</span>
          <span style={{ fontWeight: 600, color: landingTheme.ink }}>{v}</span>
        </div>
      ))}
      <div style={{
        position: 'absolute',
        bottom: 16, right: 16, left: 16,
        fontSize: 9,
        color: landingTheme.inkLight,
        textAlign: 'center',
      }}>стр. 1 из 12 · продолжение в PDF</div>
    </div>
  </div>
);

const WhatYouGet = ({ mobile }) => (
  <Section mobile={mobile}>
    <div style={{
      display: 'grid',
      gridTemplateColumns: mobile ? '1fr' : '1fr 1fr',
      gap: mobile ? 36 : 80,
      alignItems: 'center',
    }}>
      <div>
        <SectionEyebrow>Результат</SectionEyebrow>
        <SectionTitle mobile={mobile}>
          Готовый PDF-файл с рационом
        </SectionTitle>
        <SectionSub mobile={mobile}>
          Никаких теорий и общих фраз. Конкретный документ, который можно открыть, распечатать и пользоваться.
        </SectionSub>
        <div style={{
          marginTop: 28,
          display: 'grid',
          gridTemplateColumns: mobile ? '1fr' : '1fr 1fr',
          gap: 18,
        }}>
          {[
            {
              kicker: 'Для натуралки',
              items: ['Точные граммовки на каждый день', 'Список продуктов для закупки', 'Баланс нутриентов рассчитан', 'Пошаговая схема перевода', 'Принцип: «Купи — Нарежь — Положи в миску»'],
            },
            {
              kicker: 'Для сухого корма',
              items: ['ТОП-5 кормов под вашу собаку', 'Разбор составов: что внутри на самом деле', 'Прямые ссылки на покупку', 'Инструкция по смене корма'],
            },
          ].map((col, i) => (
            <div key={i} style={{
              padding: 18,
              background: landingTheme.bgSoft,
              borderRadius: 16,
              border: `1px solid ${landingTheme.borderSoft}`,
            }}>
              <div style={{
                fontSize: 12,
                fontWeight: 700,
                color: landingTheme.primary,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: 12,
              }}>{col.kicker}</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {col.items.map((it, j) => (
                  <li key={j} style={{
                    fontSize: 13.5,
                    color: landingTheme.ink,
                    display: 'flex',
                    gap: 8,
                    lineHeight: 1.4,
                  }}>
                    <IconCheck size={16} strokeWidth={2.5} color={landingTheme.primary} style={{ flex: '0 0 auto', marginTop: 1 }} />
                    {it}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <PDFMockup mobile={mobile} />
      </div>
    </div>
  </Section>
);

// 7. How we work --------------------------------------------------------------

const HowWeWork = ({ mobile }) => {
  const steps = [
    { Icon: IconClipboard, title: 'Заполняете анкету', text: 'Порода, возраст, вес, активность, аллергии, текущее питание. Займёт 3 минуты.' },
    { Icon: IconBrain, title: 'Мы анализируем', text: 'Рассчитываем рацион или подбираем корма на основе ветеринарных норм и актуального рынка.' },
    { Icon: IconFile, title: 'Получаете PDF', text: 'Готовый документ с конкретными продуктами/кормами и граммовками. Никакой воды.' },
    { Icon: IconChat, title: 'Поддержка 7 дней', text: 'Задаёте вопросы, уточняете, корректируем рацион. Мы рядом.' },
  ];
  return (
    <Section mobile={mobile} bg={landingTheme.bgSoft}>
      <div style={{ textAlign: mobile ? 'left' : 'center', marginBottom: mobile ? 32 : 56 }}>
        <SectionEyebrow>Процесс</SectionEyebrow>
        <SectionTitle mobile={mobile} align={mobile ? 'left' : 'center'}>Как это работает</SectionTitle>
      </div>
      <div style={{
        display: mobile ? 'flex' : 'grid',
        flexDirection: mobile ? 'column' : undefined,
        gridTemplateColumns: mobile ? undefined : 'repeat(4, 1fr)',
        gap: mobile ? 16 : 20,
        position: 'relative',
      }}>
        {/* connector line - desktop only */}
        {!mobile && (
          <div style={{
            position: 'absolute',
            top: 36,
            left: '12.5%',
            right: '12.5%',
            height: 2,
            background: `repeating-linear-gradient(90deg, ${landingTheme.border} 0 8px, transparent 8px 16px)`,
            zIndex: 0,
          }} />
        )}
        {steps.map(({ Icon, title, text }, i) => (
          <div key={i} style={{
            display: 'flex',
            flexDirection: mobile ? 'row' : 'column',
            gap: mobile ? 16 : 18,
            alignItems: mobile ? 'flex-start' : 'flex-start',
            position: 'relative',
            zIndex: 1,
          }}>
            <div style={{
              flex: '0 0 auto',
              width: mobile ? 56 : 72,
              height: mobile ? 56 : 72,
              borderRadius: mobile ? 16 : 20,
              background: '#fff',
              border: `2px solid ${landingTheme.primary}`,
              color: landingTheme.primary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
            }}>
              <Icon size={mobile ? 28 : 34} />
              <div style={{
                position: 'absolute',
                top: -8, right: -8,
                width: 26, height: 26,
                borderRadius: 13,
                background: landingTheme.accent,
                color: '#fff',
                fontSize: 13,
                fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '2px solid #fff',
              }}>{i + 1}</div>
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: landingTheme.ink, marginBottom: 6 }}>{title}</div>
              <div style={{ fontSize: 14.5, lineHeight: 1.55, color: landingTheme.inkSoft }}>{text}</div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
};

// 8. Testimonials -------------------------------------------------------------

const Testimonials = ({ mobile }) => {
  const items = [
    {
      photo: photos.testimonial1,
      name: 'Анна, лабрадор Барон, 4 года',
      text: 'Перевели Барона на натуралку по вашему расчёту. Через месяц ушла перхоть, шерсть блестит, на прогулке другой пёс. Деньги отбились на ветеринарных счетах за пару месяцев.',
    },
    {
      photo: photos.testimonial2,
      name: 'Дмитрий, такса Чарли, 7 лет',
      text: 'У Чарли годами был жидкий стул на любом корме. Подобрали один из ТОП-5 — впервые за всё время нормально. Спасибо, что не теории, а конкретные ссылки на покупку.',
    },
    {
      photo: photos.testimonial3,
      name: 'Мария, метис Луна, щенок',
      text: 'Боялась накормить щенка неправильно. Получила PDF с граммовками и схемой по возрасту — всё разложено по полочкам. Поддержка отвечает быстро, реально по делу.',
    },
  ];
  return (
    <Section mobile={mobile}>
      <div style={{ textAlign: mobile ? 'left' : 'center', marginBottom: mobile ? 32 : 48 }}>
        <SectionEyebrow>Отзывы</SectionEyebrow>
        <SectionTitle mobile={mobile} align={mobile ? 'left' : 'center'}>Что говорят клиенты</SectionTitle>
      </div>
      {/* Big stat strip */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? 'repeat(3, 1fr)' : 'repeat(3, 1fr)',
        gap: mobile ? 12 : 20,
        marginBottom: mobile ? 24 : 36,
        padding: mobile ? '18px' : '28px 36px',
        background: landingTheme.primary,
        borderRadius: 20,
        color: '#fff',
      }}>
        {[
          ['1 200+', 'рационов рассчитано'],
          ['4,9', 'средняя оценка'],
          ['7 дней', 'поддержка после'],
        ].map(([n, l], i) => (
          <div key={i} style={{ textAlign: mobile ? 'left' : 'center', borderLeft: !mobile && i > 0 ? `1px solid rgba(255,255,255,0.2)` : 'none', paddingLeft: !mobile && i > 0 ? 20 : 0 }}>
            <div style={{ fontSize: mobile ? 24 : 40, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1 }}>{n}</div>
            <div style={{ fontSize: mobile ? 12 : 14, opacity: 0.8, marginTop: 6 }}>{l}</div>
          </div>
        ))}
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? '1fr' : 'repeat(3, 1fr)',
        gap: 16,
      }}>
        {items.map((t, i) => (
          <div key={i} style={{
            padding: mobile ? 22 : 26,
            background: '#fff',
            border: `1px solid ${landingTheme.borderSoft}`,
            borderRadius: 18,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}>
            <div style={{ display: 'flex', gap: 2, color: landingTheme.accent }}>
              {[1, 2, 3, 4, 5].map(s => <IconStar key={s} size={14} strokeWidth={0} color={landingTheme.accent} style={{ fill: landingTheme.accent }} />)}
            </div>
            <div style={{ fontSize: 15, lineHeight: 1.55, color: landingTheme.ink, textWrap: 'pretty', flex: 1 }}>
              «{t.text}»
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <div style={{
                width: 40, height: 40,
                borderRadius: 20,
                background: `url(${t.photo}) center/cover`,
                flex: '0 0 auto',
              }} />
              <div style={{ fontSize: 13.5, fontWeight: 600, color: landingTheme.ink }}>{t.name}</div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
};

// 9. FAQ ----------------------------------------------------------------------

const FAQ = ({ mobile }) => {
  const items = [
    { q: 'Это подходит для щенков?', a: 'Да. Для щенков особенно важно правильное питание — они растут, и рацион нужно пересчитывать. Мы учитываем возраст и породу.' },
    { q: 'А если у собаки аллергия?', a: 'Это как раз наша специализация. В анкете указываете известные аллергены — мы подберём рацион, исключающий их.' },
    { q: 'Как быстро я получу результат?', a: 'В течение 3 рабочих дней. Обычно быстрее.' },
    { q: 'Можно ли задать вопросы после?', a: 'Да, у вас 7 дней поддержки после получения PDF. Пишите в Telegram — ответим.' },
    { q: 'Чем это лучше бесплатных таблиц из интернета?', a: 'Бесплатные таблицы — общие. Мы делаем расчёт под конкретную собаку: её вес, возраст, активность, аллергии, ваш бюджет. Плюс поддержка, если что-то пойдёт не так.' },
    { q: 'А если корм/рацион не подойдёт?', a: 'У вас 7 дней поддержки — скорректируем. Такое бывает редко, потому что мы учитываем все параметры заранее.' },
  ];
  const [open, setOpen] = useState(0);
  return (
    <Section mobile={mobile} bg={landingTheme.bgSoft}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? '1fr' : '1fr 1.6fr',
        gap: mobile ? 28 : 64,
        alignItems: 'start',
      }}>
        <div style={{ position: mobile ? 'static' : 'sticky', top: 120 }}>
          <SectionEyebrow>FAQ</SectionEyebrow>
          <SectionTitle mobile={mobile}>Частые<br />вопросы</SectionTitle>
          <SectionSub mobile={mobile}>
            Не нашли ответ? Напишите в Telegram-бот — ответим за 15 минут в рабочее время.
          </SectionSub>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((it, i) => {
            const isOpen = open === i;
            return (
              <div key={i} style={{
                background: '#fff',
                border: `1px solid ${isOpen ? landingTheme.primary : landingTheme.borderSoft}`,
                borderRadius: 14,
                overflow: 'hidden',
                transition: 'border-color .15s',
              }}>
                <button
                  onClick={() => setOpen(isOpen ? -1 : i)}
                  style={{
                    width: '100%',
                    padding: mobile ? '18px 20px' : '20px 24px',
                    background: 'transparent',
                    border: 'none',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    fontSize: mobile ? 16 : 17,
                    fontWeight: 600,
                    color: landingTheme.ink,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 16,
                  }}
                >
                  {it.q}
                  <IconChevron
                    size={20}
                    strokeWidth={2.2}
                    color={isOpen ? landingTheme.primary : landingTheme.inkSoft}
                    style={{
                      transform: isOpen ? 'rotate(180deg)' : 'rotate(0)',
                      transition: 'transform .2s',
                      flex: '0 0 auto',
                    }}
                  />
                </button>
                {isOpen && (
                  <div style={{
                    padding: mobile ? '0 20px 20px' : '0 24px 22px',
                    fontSize: 15,
                    lineHeight: 1.6,
                    color: landingTheme.inkSoft,
                  }}>{it.a}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Section>
  );
};

// 10. Wizard section ----------------------------------------------------------

const WizardSection = ({ mobile }) => (
  <Section mobile={mobile}>
    <div style={{ textAlign: 'center', marginBottom: mobile ? 32 : 48 }}>
      <SectionEyebrow>Анкета</SectionEyebrow>
      <SectionTitle mobile={mobile} align="center">Расскажите о собаке</SectionTitle>
      <SectionSub mobile={mobile} align="center">
        5 коротких шагов — ничего лишнего. Сохраняем ответы, можно вернуться позже.
      </SectionSub>
    </div>
    <WizardForm mobile={mobile} />
  </Section>
);

// 11. Final CTA --------------------------------------------------------------

const FinalCTA = ({ mobile }) => (
  <Section mobile={mobile}>
    <div style={{
      position: 'relative',
      borderRadius: 28,
      overflow: 'hidden',
      padding: mobile ? '36px 24px' : '80px 64px',
      background: `linear-gradient(135deg, ${landingTheme.primary}, ${landingTheme.primaryDark})`,
      color: '#fff',
    }}>
      {/* faded photo overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: `url(${photos.finalCta}) center/cover`,
        opacity: 0.18,
        mixBlendMode: 'overlay',
      }} />
      <div style={{ position: 'relative', maxWidth: 720 }}>
        <SectionTitle mobile={mobile} white>
          Хватит гадать —<br />дайте собаке лучшее
        </SectionTitle>
        <p style={{
          margin: mobile ? '16px 0 0' : '20px 0 0',
          fontSize: mobile ? 16 : 19,
          lineHeight: 1.5,
          color: 'rgba(255,255,255,0.85)',
          maxWidth: 580,
        }}>
          Стоимость подбора — дешевле одного визита к ветеринару. А результат — на всю жизнь.
        </p>
        <div style={{
          display: 'flex',
          gap: 12,
          marginTop: 32,
          flexDirection: mobile ? 'column' : 'row',
        }}>
          <button style={{
            padding: mobile ? '16px 22px' : '18px 26px',
            fontSize: 16,
            fontWeight: 700,
            fontFamily: 'inherit',
            color: landingTheme.primary,
            background: '#fff',
            border: 'none',
            borderRadius: 12,
            cursor: 'pointer',
          }}>Подбор сухого корма — 990 ₽</button>
          <button style={{
            padding: mobile ? '16px 22px' : '18px 26px',
            fontSize: 16,
            fontWeight: 700,
            fontFamily: 'inherit',
            color: '#fff',
            background: landingTheme.accent,
            border: 'none',
            borderRadius: 12,
            cursor: 'pointer',
            boxShadow: '0 10px 24px -8px rgba(245, 158, 11, 0.5)',
          }}>Расчёт натуралки — 1 390 ₽</button>
        </div>
      </div>
    </div>
  </Section>
);

// 12. Footer ------------------------------------------------------------------

const Footer = ({ mobile }) => (
  <footer style={{
    background: landingTheme.ink,
    color: '#fff',
    padding: mobile ? '40px 20px 28px' : '64px 80px 40px',
  }}>
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: mobile ? '1fr' : '1.4fr 1fr 1fr 1fr',
        gap: mobile ? 32 : 48,
        paddingBottom: 36,
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}>
        <div>
          <Logo white />
          <p style={{
            margin: '16px 0 0',
            fontSize: 14.5,
            lineHeight: 1.6,
            color: 'rgba(255,255,255,0.7)',
            maxWidth: 320,
          }}>
            Подбор рациона для собак от практиков с 20+ лет в кинологии. На основе совместной работы с ветеринарами и диетологами.
          </p>
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            {[IconTelegram, IconPhone].map((Ic, i) => (
              <a key={i} href="#" style={{
                width: 38, height: 38,
                borderRadius: 10,
                background: 'rgba(255,255,255,0.08)',
                color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                textDecoration: 'none',
              }}>
                <Ic size={18} />
              </a>
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.5)', marginBottom: 14 }}>Контакты</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 14, color: 'rgba(255,255,255,0.85)' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <IconPin size={16} style={{ flex: '0 0 auto', marginTop: 2, opacity: 0.6 }} />
              площадь Ленина, 3<br />Архангельск
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <IconClock size={16} style={{ flex: '0 0 auto', opacity: 0.6 }} />
              ежедневно 10:00–20:00
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <IconPhone size={16} style={{ flex: '0 0 auto', opacity: 0.6 }} />
              +7 958 111 42 00
            </div>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.5)', marginBottom: 14 }}>Услуги Doggi</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14 }}>
            {['Подбор рациона', 'Дрессировка', 'Зоогостиница', 'Груминг Pet Spa'].map(l => (
              <a key={l} href="#" style={{ color: 'rgba(255,255,255,0.85)', textDecoration: 'none' }}>{l}</a>
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.5)', marginBottom: 14 }}>Правовое</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14 }}>
            <a href="#" style={{ color: 'rgba(255,255,255,0.85)', textDecoration: 'none' }}>Пользовательское соглашение</a>
            <a href="#" style={{ color: 'rgba(255,255,255,0.85)', textDecoration: 'none' }}>Политика обработки данных</a>
          </div>
        </div>
      </div>
      <div style={{
        paddingTop: 24,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexDirection: mobile ? 'column' : 'row',
        gap: 12,
        fontSize: 13,
        color: 'rgba(255,255,255,0.5)',
      }}>
        <div>© 2025 Doggi · ИП Кусь</div>
        <div>doggi.ru/food</div>
      </div>
    </div>
  </footer>
);

// Main Landing ----------------------------------------------------------------

const Landing = ({ mobile }) => (
  <div style={{
    background: '#fff',
    color: landingTheme.ink,
    fontFamily: '"Golos Text", system-ui, sans-serif',
    fontSize: 16,
    overflow: 'hidden',
    width: '100%',
  }}>
    <Header mobile={mobile} />
    <Hero mobile={mobile} />
    <Problems mobile={mobile} />
    <WhoWeAre mobile={mobile} />
    <Services mobile={mobile} />
    <WhatYouGet mobile={mobile} />
    <HowWeWork mobile={mobile} />
    <Testimonials mobile={mobile} />
    <FAQ mobile={mobile} />
    <WizardSection mobile={mobile} />
    <FinalCTA mobile={mobile} />
    <Footer mobile={mobile} />
  </div>
);

window.Landing = Landing;
window.landingTheme = landingTheme;
