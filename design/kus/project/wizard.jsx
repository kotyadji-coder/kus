// Кусь — 5-шаговая анкета подбора рациона
// Fully functional: navigation, state, progress bar, card selection.

const { useState } = React;

const wizPalette = {
  primary: '#055ba9',
  primaryDark: '#04467f',
  primarySoft: '#e6f0fa',
  accent: '#f59e0b',
  ink: '#0b1726',
  inkSoft: '#475569',
  border: '#e2e8f0',
  bg: '#ffffff',
  bgSoft: '#f7f9fc',
};

// Reusable bits ---------------------------------------------------------------

const wizFieldLabel = (label, required) => (
  <div style={{
    fontSize: 13,
    fontWeight: 500,
    color: wizPalette.inkSoft,
    marginBottom: 6,
    letterSpacing: '0.01em',
  }}>
    {label}{required && <span style={{ color: wizPalette.accent, marginLeft: 4 }}>*</span>}
  </div>
);

const WizInput = ({ value, onChange, placeholder, type = 'text' }) => (
  <input
    type={type}
    value={value || ''}
    onChange={(e) => onChange && onChange(e.target.value)}
    placeholder={placeholder}
    style={{
      width: '100%',
      padding: '14px 16px',
      fontSize: 16,
      fontFamily: 'inherit',
      color: wizPalette.ink,
      background: wizPalette.bg,
      border: `1.5px solid ${wizPalette.border}`,
      borderRadius: 10,
      outline: 'none',
      transition: 'border-color .15s',
    }}
    onFocus={(e) => e.target.style.borderColor = wizPalette.primary}
    onBlur={(e) => e.target.style.borderColor = wizPalette.border}
  />
);

const WizSegmented = ({ options, value, onChange }) => (
  <div style={{
    display: 'flex',
    background: wizPalette.bgSoft,
    border: `1.5px solid ${wizPalette.border}`,
    borderRadius: 10,
    padding: 4,
    gap: 4,
  }}>
    {options.map(opt => (
      <button
        key={opt.value}
        onClick={() => onChange(opt.value)}
        style={{
          flex: 1,
          padding: '10px 12px',
          fontSize: 15,
          fontWeight: 500,
          fontFamily: 'inherit',
          color: value === opt.value ? '#fff' : wizPalette.inkSoft,
          background: value === opt.value ? wizPalette.primary : 'transparent',
          border: 'none',
          borderRadius: 7,
          cursor: 'pointer',
          transition: 'all .15s',
        }}
      >
        {opt.label}
      </button>
    ))}
  </div>
);

// Big selectable card — used for diet, BCS, activity, type, budget.
const WizCard = ({ selected, onClick, title, desc, illust, compact }) => (
  <button
    onClick={onClick}
    style={{
      width: '100%',
      textAlign: 'left',
      padding: compact ? 16 : 18,
      background: selected ? wizPalette.primarySoft : wizPalette.bg,
      border: `2px solid ${selected ? wizPalette.primary : wizPalette.border}`,
      borderRadius: 14,
      cursor: 'pointer',
      fontFamily: 'inherit',
      display: 'flex',
      alignItems: 'flex-start',
      gap: 14,
      transition: 'all .15s',
      position: 'relative',
    }}
  >
    {illust && (
      <div style={{
        flex: '0 0 auto',
        width: compact ? 44 : 56,
        height: compact ? 44 : 56,
        borderRadius: 10,
        background: selected ? '#fff' : wizPalette.bgSoft,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: wizPalette.primary,
      }}>
        {illust}
      </div>
    )}
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{
        fontSize: compact ? 15 : 16,
        fontWeight: 600,
        color: wizPalette.ink,
        marginBottom: desc ? 4 : 0,
      }}>{title}</div>
      {desc && (
        <div style={{
          fontSize: 13.5,
          color: wizPalette.inkSoft,
          lineHeight: 1.45,
        }}>{desc}</div>
      )}
    </div>
    {selected && (
      <div style={{
        flex: '0 0 auto',
        width: 22,
        height: 22,
        borderRadius: 11,
        background: wizPalette.primary,
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <IconCheck size={14} strokeWidth={3} />
      </div>
    )}
  </button>
);

// BCS silhouettes — simple SVGs (top/side rough shapes).
const BCSSilhouette = ({ variant, color = '#055ba9' }) => {
  // variants: skinny, athletic, donut, ball
  const widths = { skinny: 28, athletic: 36, donut: 48, ball: 58 };
  const w = widths[variant];
  return (
    <svg width="60" height="40" viewBox="0 0 60 40" fill="none">
      {/* side view dog */}
      <ellipse cx="30" cy="22" rx={w / 2} ry="10" fill={color} opacity="0.18" />
      <ellipse cx="30" cy="22" rx={w / 2} ry="10" stroke={color} strokeWidth="1.5" />
      <circle cx={30 + w / 2 - 4} cy="16" r="5" fill={color} opacity="0.18" />
      <circle cx={30 + w / 2 - 4} cy="16" r="5" stroke={color} strokeWidth="1.5" />
      <path d={`M${30 - w / 2 + 1} 22 L${30 - w / 2 - 4} 18`} stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      <path d={`M${30 - w / 2 + 4} 32 L${30 - w / 2 + 4} 36 M${30 + w / 2 - 6} 32 L${30 + w / 2 - 6} 36`} stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
};

// Steps -----------------------------------------------------------------------

const Step1 = ({ data, set }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
    <div>
      {wizFieldLabel('Кличка собаки', true)}
      <WizInput value={data.name} onChange={v => set('name', v)} placeholder="Например, Барон" />
    </div>
    <div>
      {wizFieldLabel('Порода', true)}
      <WizInput value={data.breed} onChange={v => set('breed', v)} placeholder="Начните вводить: лабрадор, метис..." />
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div>
        {wizFieldLabel('Возраст', true)}
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="number"
            value={data.ageNum || ''}
            onChange={e => set('ageNum', e.target.value)}
            placeholder="3"
            style={{
              width: 80,
              padding: '14px 16px',
              fontSize: 16,
              fontFamily: 'inherit',
              border: `1.5px solid ${wizPalette.border}`,
              borderRadius: 10,
              outline: 'none',
            }}
          />
          <div style={{ flex: 1 }}>
            <WizSegmented
              options={[{ value: 'mo', label: 'мес' }, { value: 'yr', label: 'лет' }]}
              value={data.ageUnit || 'yr'}
              onChange={v => set('ageUnit', v)}
            />
          </div>
        </div>
      </div>
      <div>
        {wizFieldLabel('Текущий вес, кг', true)}
        <WizInput value={data.weight} onChange={v => set('weight', v)} placeholder="12.5" />
      </div>
    </div>
    <div>
      {wizFieldLabel('Пол', true)}
      <WizSegmented
        options={[{ value: 'm', label: 'Мальчик' }, { value: 'f', label: 'Девочка' }]}
        value={data.sex}
        onChange={v => set('sex', v)}
      />
    </div>
    <div>
      {wizFieldLabel('Кастрация / стерилизация', true)}
      <WizSegmented
        options={[{ value: 'yes', label: 'Да' }, { value: 'no', label: 'Нет' }]}
        value={data.neutered}
        onChange={v => set('neutered', v)}
      />
    </div>
  </div>
);

const Step2 = ({ data, set }) => {
  const diets = [
    { id: 'dry', title: 'Сухой корм' },
    { id: 'porridge', title: 'Каши с мясом' },
    { id: 'raw', title: 'Натуралка' },
    { id: 'table', title: 'Еда со стола' },
    { id: 'mixed', title: 'Смешанное' },
    { id: 'other', title: 'Свой вариант' },
  ];
  const bcs = [
    { id: 'skinny', title: 'Худышка', desc: 'Рёбра и позвоночник сильно торчат — нужно набрать.' },
    { id: 'athletic', title: 'Атлет', desc: 'Рёбра прощупываются, талия видна — вес идеальный.' },
    { id: 'donut', title: 'Пончик', desc: 'Рёбра найти сложно, талии почти нет — пора худеть.' },
    { id: 'ball', title: 'Колобок', desc: 'Ожирение, собаке тяжело двигаться.' },
  ];
  const activities = [
    { id: 'lazy', title: 'Ленивая', desc: 'Гуляем мало, в основном спит на диване.' },
    { id: 'medium', title: 'Средняя', desc: '2–3 прогулки, игры с мячом, побегушки с друзьями.' },
    { id: 'high', title: 'Высокая', desc: 'Спорт, охота, длительные походы, рабочая собака.' },
    { id: 'growing', title: 'Растущий организм', desc: 'Активный щенок.' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        {wizFieldLabel('Что ест сейчас?', true)}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {diets.map(d => (
            <WizCard key={d.id} compact selected={data.diet === d.id} onClick={() => set('diet', d.id)} title={d.title} />
          ))}
        </div>
      </div>
      <div>
        {wizFieldLabel('Кондиция — оцените упитанность', true)}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {bcs.map(b => (
            <WizCard
              key={b.id}
              selected={data.bcs === b.id}
              onClick={() => set('bcs', b.id)}
              title={b.title}
              desc={b.desc}
              illust={<BCSSilhouette variant={b.id} />}
            />
          ))}
        </div>
      </div>
      <div>
        {wizFieldLabel('Активность (честно!)', true)}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {activities.map(a => (
            <WizCard key={a.id} selected={data.activity === a.id} onClick={() => set('activity', a.id)} title={a.title} desc={a.desc} />
          ))}
        </div>
      </div>
    </div>
  );
};

const Step3 = ({ data, set }) => {
  const stools = [
    { id: 'good', label: 'Отличный' },
    { id: 'liquid', label: 'Часто жидкий' },
    { id: 'constipation', label: 'Бывают запоры' },
    { id: 'large', label: 'Много выхода' },
    { id: 'other', label: 'Свой вариант' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        {wizFieldLabel('Есть ли подтверждённые диагнозы?')}
        <textarea
          value={data.diagnoses || ''}
          onChange={e => set('diagnoses', e.target.value)}
          placeholder="Гастрит, панкреатит, МКБ, проблемы с печенью. Если нет — оставьте пустым."
          rows={3}
          style={{
            width: '100%',
            padding: '14px 16px',
            fontSize: 15,
            fontFamily: 'inherit',
            color: wizPalette.ink,
            background: wizPalette.bg,
            border: `1.5px solid ${wizPalette.border}`,
            borderRadius: 10,
            resize: 'vertical',
            outline: 'none',
          }}
        />
      </div>
      <div>
        {wizFieldLabel('Как дела со стулом?', true)}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {stools.map(s => (
            <WizCard key={s.id} compact selected={data.stool === s.id} onClick={() => set('stool', s.id)} title={s.label} />
          ))}
        </div>
      </div>
    </div>
  );
};

const Step4 = ({ data, set }) => {
  const types = [
    { id: 'barf', title: 'Сырое (BARF)', desc: 'Готов давать сырое мясо, субпродукты и сырые мясные кости.' },
    { id: 'cooked', title: 'Термически обработанное', desc: 'Хочу варить или припускать мясо.' },
    { id: 'dry', title: 'Сухой корм', desc: 'Перейти к подбору сухого корма.' },
  ];
  const budgets = [
    { id: 'supermarket', title: 'Супермаркет', desc: 'Могу покупать курицу, индейку, говядину в обычном магазине.' },
    { id: 'market', title: 'Рынок / магазины для собак', desc: 'Есть доступ к рубцу, лёгким, печени, разному мясу.' },
    { id: 'unlimited', title: 'Не ограничено', desc: 'Готов покупать кролика, утку, лосося и т.д.' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <div style={{
          fontSize: 13,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: wizPalette.primary,
          marginBottom: 8,
        }}>Самый важный пункт</div>
        {wizFieldLabel('Тип питания', true)}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {types.map(t => (
            <WizCard key={t.id} selected={data.type === t.id} onClick={() => set('type', t.id)} title={t.title} desc={t.desc} />
          ))}
        </div>
      </div>
      <div>
        {wizFieldLabel('Бюджет и доступность продуктов', true)}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {budgets.map(b => (
            <WizCard key={b.id} selected={data.budget === b.id} onClick={() => set('budget', b.id)} title={b.title} desc={b.desc} />
          ))}
        </div>
      </div>
      <div>
        {wizFieldLabel('Стоп-продукты')}
        <textarea
          value={data.stopFoods || ''}
          onChange={e => set('stopFoods', e.target.value)}
          placeholder="Аллергия, непереносимость, собака отказывается есть."
          rows={2}
          style={{
            width: '100%',
            padding: '14px 16px',
            fontSize: 15,
            fontFamily: 'inherit',
            border: `1.5px solid ${wizPalette.border}`,
            borderRadius: 10,
            resize: 'vertical',
            outline: 'none',
          }}
        />
      </div>
    </div>
  );
};

const Step5 = ({ data, set }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
    <div>
      {wizFieldLabel('Ваше имя', true)}
      <WizInput value={data.userName} onChange={v => set('userName', v)} placeholder="Анастасия" />
    </div>
    <div>
      {wizFieldLabel('Телефон или Telegram', true)}
      <WizInput value={data.contact} onChange={v => set('contact', v)} placeholder="+7 958 111 42 00  или  @username" />
    </div>
    <div>
      {wizFieldLabel('Email для отправки PDF', true)}
      <WizInput type="email" value={data.email} onChange={v => set('email', v)} placeholder="you@example.com" />
    </div>
    <label style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      cursor: 'pointer',
      padding: '8px 0',
      fontSize: 13,
      color: wizPalette.inkSoft,
      lineHeight: 1.5,
    }}>
      <input
        type="checkbox"
        checked={data.consent || false}
        onChange={e => set('consent', e.target.checked)}
        style={{ marginTop: 2, accentColor: wizPalette.primary, width: 18, height: 18 }}
      />
      <span>Нажимая кнопку, вы даёте согласие на обработку персональных данных и соглашаетесь c <a href="#" style={{ color: wizPalette.primary }}>политикой конфиденциальности</a>.</span>
    </label>
  </div>
);

// Main wizard ----------------------------------------------------------------

const WizardForm = ({ mobile }) => {
  const [step, setStep] = useState(1);
  const [data, setData] = useState({ sex: 'm', neutered: 'no', ageUnit: 'yr' });
  const set = (k, v) => setData(d => ({ ...d, [k]: v }));

  const totalSteps = 5;
  const titles = [
    'О собаке',
    'Рацион и активность сейчас',
    'Здоровье и ЖКТ',
    'Предпочтения',
    'Контакты',
  ];

  return (
    <div style={{
      background: wizPalette.bg,
      borderRadius: mobile ? 20 : 24,
      border: `1px solid ${wizPalette.border}`,
      boxShadow: '0 20px 60px -20px rgba(5, 91, 169, 0.15)',
      overflow: 'hidden',
      maxWidth: mobile ? '100%' : 720,
      margin: '0 auto',
    }}>
      {/* Header with progress */}
      <div style={{
        padding: mobile ? '20px 20px 0' : '28px 32px 0',
        background: '#fff',
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 14,
        }}>
          <div style={{
            fontSize: 12,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: wizPalette.primary,
          }}>Шаг {step} из {totalSteps}</div>
          <div style={{ fontSize: 12, color: wizPalette.inkSoft }}>3 минуты</div>
        </div>
        {/* progress bar - 5 dots/segments */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 22 }}>
          {[1, 2, 3, 4, 5].map(i => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 6,
                borderRadius: 3,
                background: i <= step ? wizPalette.primary : wizPalette.border,
                transition: 'background .2s',
              }}
            />
          ))}
        </div>
        <h3 style={{
          margin: 0,
          fontSize: mobile ? 22 : 28,
          fontWeight: 700,
          color: wizPalette.ink,
          letterSpacing: '-0.02em',
        }}>{titles[step - 1]}</h3>
      </div>

      {/* Body */}
      <div style={{ padding: mobile ? '22px 20px' : '28px 32px' }}>
        {step === 1 && <Step1 data={data} set={set} />}
        {step === 2 && <Step2 data={data} set={set} />}
        {step === 3 && <Step3 data={data} set={set} />}
        {step === 4 && <Step4 data={data} set={set} />}
        {step === 5 && <Step5 data={data} set={set} />}
      </div>

      {/* Footer */}
      <div style={{
        padding: mobile ? '16px 20px 20px' : '20px 32px 28px',
        borderTop: `1px solid ${wizPalette.border}`,
        background: wizPalette.bgSoft,
        display: 'flex',
        gap: 10,
        flexDirection: mobile ? 'column-reverse' : 'row',
        justifyContent: 'space-between',
      }}>
        {step > 1 ? (
          <button
            onClick={() => setStep(s => s - 1)}
            style={{
              padding: '14px 22px',
              fontSize: 15,
              fontWeight: 600,
              fontFamily: 'inherit',
              color: wizPalette.inkSoft,
              background: 'transparent',
              border: `1.5px solid ${wizPalette.border}`,
              borderRadius: 10,
              cursor: 'pointer',
            }}
          >← Назад</button>
        ) : <div />}
        {step < totalSteps ? (
          <button
            onClick={() => setStep(s => s + 1)}
            style={{
              padding: '14px 22px',
              fontSize: 15,
              fontWeight: 600,
              fontFamily: 'inherit',
              color: '#fff',
              background: wizPalette.primary,
              border: 'none',
              borderRadius: 10,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              justifyContent: 'center',
            }}
          >Дальше <IconArrow size={16} strokeWidth={2.5} /></button>
        ) : (
          <button
            style={{
              padding: '14px 22px',
              fontSize: 15,
              fontWeight: 700,
              fontFamily: 'inherit',
              color: '#fff',
              background: wizPalette.accent,
              border: 'none',
              borderRadius: 10,
              cursor: 'pointer',
              boxShadow: '0 8px 20px -6px rgba(245, 158, 11, 0.5)',
            }}
          >Оплатить и получить рацион →</button>
        )}
      </div>
    </div>
  );
};

window.WizardForm = WizardForm;
