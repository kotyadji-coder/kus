// Lucide-style line icons for Кусь landing.
// All icons share stroke="currentColor", strokeWidth=1.75, no fill.
// Pass {size, color} to override.

const IconBase = ({ children, size = 24, color = 'currentColor', strokeWidth = 1.75, style }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={style}
    aria-hidden="true"
  >
    {children}
  </svg>
);

// Brand mark — a friendly bite-shape "Кусь" wordmark companion.
const IconPaw = (p) => (
  <IconBase {...p}>
    <circle cx="6" cy="9" r="1.6" />
    <circle cx="10" cy="6" r="1.6" />
    <circle cx="14" cy="6" r="1.6" />
    <circle cx="18" cy="9" r="1.6" />
    <path d="M8.5 14c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5c0 1.6 1 2.2 1 3.5 0 1.4-1.2 2-2.6 2-1 0-1.4-.5-1.9-.5s-.9.5-1.9.5C8.7 19.5 7.5 18.9 7.5 17.5c0-1.3 1-1.9 1-3.5z" />
  </IconBase>
);

// Problem cards
const IconScratch = (p) => (
  <IconBase {...p}>
    <path d="M4 17c2-1 4-2 7-2s5 1 7 2" />
    <path d="M9 7l1.5 2M14.5 7L13 9M11.5 6v2" />
    <path d="M7 14c0-3 2-5 5-5s5 2 5 5" />
    <path d="M16 18l1.5 2M8 18l-1.5 2" />
  </IconBase>
);

const IconScales = (p) => (
  <IconBase {...p}>
    <path d="M12 3v18" />
    <path d="M7 21h10" />
    <path d="M3 8h18" />
    <path d="M6 8l-3 5a3 3 0 006 0L6 8z" />
    <path d="M18 8l-3 5a3 3 0 006 0L18 8z" />
  </IconBase>
);

const IconBowl = (p) => (
  <IconBase {...p}>
    <path d="M3 11h18l-1.5 7.5a2 2 0 01-2 1.5h-11a2 2 0 01-2-1.5L3 11z" />
    <path d="M5 11c0-2.5 3-4 7-4s7 1.5 7 4" />
    <path d="M9 7.5c.5-.7 1.5-1.2 3-1.2s2.5.5 3 1.2" />
  </IconBase>
);

const IconLabel = (p) => (
  <IconBase {...p}>
    <circle cx="11" cy="11" r="6" />
    <path d="M15.5 15.5L20 20" />
    <path d="M9 11h4M11 9v4" />
  </IconBase>
);

// "Why us" cards
const IconHome = (p) => (
  <IconBase {...p}>
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v9a1 1 0 001 1h12a1 1 0 001-1v-9" />
    <path d="M10 20v-5h4v5" />
  </IconBase>
);

const IconHotel = (p) => (
  <IconBase {...p}>
    <rect x="3" y="6" width="18" height="14" rx="1.5" />
    <path d="M3 11h18" />
    <path d="M7 8.5h.01M11 8.5h.01M15 8.5h.01M19 8.5h.01" />
    <path d="M7 15h3M14 15h3" />
  </IconBase>
);

const IconStore = (p) => (
  <IconBase {...p}>
    <path d="M3 9l1-4h16l1 4" />
    <path d="M4 9v11a1 1 0 001 1h14a1 1 0 001-1V9" />
    <path d="M3 9h18" />
    <path d="M9 21v-6h6v6" />
  </IconBase>
);

// Service card visuals
const IconKibble = (p) => (
  <IconBase {...p}>
    <path d="M5 9c-1 0-2 .8-2 2.5C3 16 7 20 12 20s9-4 9-8.5c0-1.7-1-2.5-2-2.5-1 0-1.5.7-2.5.7S15 8 12 8s-3.5 1.7-4.5 1.7S6 9 5 9z" />
    <circle cx="9" cy="13" r=".8" fill="currentColor" />
    <circle cx="13" cy="14" r=".8" fill="currentColor" />
    <circle cx="16" cy="12" r=".8" fill="currentColor" />
    <path d="M8 5.5c.5 1 1.5 1.5 2.5 1.5M14 4c0 1.2.8 2 2 2.2" />
  </IconBase>
);

const IconMeat = (p) => (
  <IconBase {...p}>
    <path d="M6.5 17.5c-2.5-2.5-2.5-7 .5-10s7.5-3 10-.5c2 2 1.5 5-.5 7s-5 2.5-7 .5z" />
    <circle cx="9" cy="14" r="1.2" />
    <path d="M5.5 18.5l-2 2" />
    <path d="M16 7c-1 1-1 3 0 4" />
  </IconBase>
);

// Process steps
const IconClipboard = (p) => (
  <IconBase {...p}>
    <rect x="6" y="4" width="12" height="17" rx="1.5" />
    <rect x="9" y="2" width="6" height="4" rx="1" />
    <path d="M9 11h6M9 14h6M9 17h4" />
  </IconBase>
);

const IconBrain = (p) => (
  <IconBase {...p}>
    <path d="M12 5c-1.5-1.5-4-1.5-5 .5S5 9 6 10c-1 1.5-.5 3.5 1 4 0 1.5 1.5 3 3.5 2.5.5 1.5 2.5 1.5 3 0" />
    <path d="M12 5c1.5-1.5 4-1.5 5 .5s2 3.5 1 4.5c1 1.5.5 3.5-1 4 0 1.5-1.5 3-3.5 2.5" />
    <path d="M12 5v13" />
  </IconBase>
);

const IconFile = (p) => (
  <IconBase {...p}>
    <path d="M14 3H7a1 1 0 00-1 1v16a1 1 0 001 1h10a1 1 0 001-1V7l-4-4z" />
    <path d="M14 3v4h4" />
    <path d="M9 13h6M9 16h6M9 10h3" />
  </IconBase>
);

const IconChat = (p) => (
  <IconBase {...p}>
    <path d="M21 12c0 4-4 7-9 7-1.2 0-2.3-.2-3.4-.5L3 20l1.5-4.5C3.5 14.5 3 13.3 3 12c0-4 4-7 9-7s9 3 9 7z" />
    <circle cx="9" cy="12" r=".8" fill="currentColor" />
    <circle cx="12" cy="12" r=".8" fill="currentColor" />
    <circle cx="15" cy="12" r=".8" fill="currentColor" />
  </IconBase>
);

// FAQ
const IconChevron = (p) => (
  <IconBase {...p}>
    <path d="M6 9l6 6 6-6" />
  </IconBase>
);

const IconArrow = (p) => (
  <IconBase {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </IconBase>
);

const IconCheck = (p) => (
  <IconBase {...p}>
    <path d="M5 12l5 5L20 7" />
  </IconBase>
);

const IconMenu = (p) => (
  <IconBase {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </IconBase>
);

const IconTelegram = (p) => (
  <IconBase {...p}>
    <path d="M3 11l18-7-3 16-7-3-3 4v-5l10-9-12 7-3-2z" />
  </IconBase>
);

const IconStar = (p) => (
  <IconBase {...p}>
    <path d="M12 3l2.5 6 6.5.5-5 4.5 1.5 6.5L12 17l-5.5 3.5L8 14l-5-4.5L9.5 9 12 3z" />
  </IconBase>
);

const IconPhone = (p) => (
  <IconBase {...p}>
    <path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a1 1 0 01-1 1A16 16 0 014 5a1 1 0 011-1z" />
  </IconBase>
);

const IconPin = (p) => (
  <IconBase {...p}>
    <path d="M12 21s7-6.5 7-12a7 7 0 10-14 0c0 5.5 7 12 7 12z" />
    <circle cx="12" cy="9" r="2.5" />
  </IconBase>
);

const IconClock = (p) => (
  <IconBase {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </IconBase>
);

// PDF mock visual
const IconPDF = (p) => (
  <IconBase {...p}>
    <path d="M7 3h8l4 4v14a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z" />
    <path d="M15 3v4h4" />
  </IconBase>
);

const IconUser = (p) => (
  <IconBase {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 4-7 8-7s8 3 8 7" />
  </IconBase>
);

const IconHeart = (p) => (
  <IconBase {...p}>
    <path d="M12 20s-7-4.5-7-10a4 4 0 017-2.5A4 4 0 0119 10c0 5.5-7 10-7 10z" />
  </IconBase>
);

Object.assign(window, {
  IconBase, IconPaw, IconScratch, IconScales, IconBowl, IconLabel,
  IconHome, IconHotel, IconStore, IconKibble, IconMeat,
  IconClipboard, IconBrain, IconFile, IconChat,
  IconChevron, IconArrow, IconCheck, IconMenu, IconTelegram,
  IconStar, IconPhone, IconPin, IconClock, IconPDF, IconUser, IconHeart,
});
