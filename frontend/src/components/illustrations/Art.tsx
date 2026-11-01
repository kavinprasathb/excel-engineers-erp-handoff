import { useId } from "react";
import type { ReactNode } from "react";

/**
 * Hand-drawn illustrations in one soft, semi-3D style: a light-to-deep blue
 * body, a white highlight on top, a darker face for depth and a faint ground
 * shadow. Drawn on a 120 x 120 grid. Gradient ids are made unique per
 * instance so two copies on one page never share (and break) a gradient.
 */

export type ArtName =
  | "pump"
  | "motor"
  | "baseframe"
  | "shaft"
  | "seal"
  | "valve"
  | "quote"
  | "negotiation"
  | "order"
  | "truck"
  | "clipboard"
  | "shelf"
  | "factory"
  | "building"
  | "chart"
  | "bell"
  | "check"
  | "tray"
  | "lock"
  | "warning"
  | "people";

interface Ids {
  blue: string;
  deep: string;
  paper: string;
  metal: string;
  green: string;
  amber: string;
  red: string;
  glow: string;
}

function Defs({ id }: { id: Ids }) {
  return (
    <defs>
      <linearGradient id={id.blue} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#9cc0ff" />
        <stop offset="1" stopColor="#3c6fe0" />
      </linearGradient>
      <linearGradient id={id.deep} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#3d6fe0" />
        <stop offset="1" stopColor="#2448a8" />
      </linearGradient>
      <linearGradient id={id.paper} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#ffffff" />
        <stop offset="1" stopColor="#e3ebfa" />
      </linearGradient>
      <linearGradient id={id.metal} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#f3f5f9" />
        <stop offset="1" stopColor="#a4adbd" />
      </linearGradient>
      <linearGradient id={id.green} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#6fe3a8" />
        <stop offset="1" stopColor="#16a063" />
      </linearGradient>
      <linearGradient id={id.amber} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#ffd37a" />
        <stop offset="1" stopColor="#e58a00" />
      </linearGradient>
      <linearGradient id={id.red} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#ff9a9a" />
        <stop offset="1" stopColor="#d93636" />
      </linearGradient>
      <radialGradient id={id.glow} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#3c6fe0" stopOpacity="0.18" />
        <stop offset="1" stopColor="#3c6fe0" stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

const u = (id: string) => `url(#${id})`;

function Ground({ id, w = 40 }: { id: Ids; w?: number }) {
  return (
    <>
      <circle cx="60" cy="58" r="54" fill={u(id.glow)} />
      <ellipse cx="60" cy="104" rx={w} ry="6" fill="#1e3a8a" opacity="0.1" />
    </>
  );
}

const DRAW: Record<ArtName, (id: Ids) => ReactNode> = {
  pump: (id) => (
    <>
      <Ground id={id} w={34} />
      <rect x="42" y="92" width="36" height="8" rx="2" fill={u(id.deep)} />
      <rect x="54" y="14" width="16" height="22" rx="3" fill={u(id.metal)} />
      <rect x="50" y="12" width="24" height="7" rx="2.5" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      <circle cx="60" cy="60" r="34" fill={u(id.blue)} />
      <path d="M32 50a30 30 0 0 1 48-18" stroke="#fff" strokeOpacity="0.55" strokeWidth="4" strokeLinecap="round" fill="none" />
      <circle cx="60" cy="62" r="17" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="1" />
      <circle cx="60" cy="62" r="10" fill={u(id.deep)} />
      {[0, 60, 120, 180, 240, 300].map((a) => (
        <circle key={a} cx={60 + 13.5 * Math.cos((a * Math.PI) / 180)} cy={62 + 13.5 * Math.sin((a * Math.PI) / 180)} r="1.6" fill="#6b7587" />
      ))}
    </>
  ),
  motor: (id) => (
    <>
      <Ground id={id} w={42} />
      <rect x="24" y="92" width="64" height="7" rx="2" fill={u(id.deep)} />
      <rect x="18" y="40" width="72" height="52" rx="14" fill={u(id.blue)} />
      {[48, 56, 64, 72, 80].map((y) => (
        <rect key={y} x="26" y={y} width="56" height="2.4" rx="1.2" fill="#2448a8" opacity="0.35" />
      ))}
      <rect x="44" y="28" width="22" height="14" rx="3" fill={u(id.deep)} />
      <path d="M24 46h58" stroke="#fff" strokeOpacity="0.5" strokeWidth="3" strokeLinecap="round" />
      <rect x="88" y="60" width="18" height="10" rx="3" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      <circle cx="18" cy="66" r="3" fill="#2448a8" opacity="0.5" />
    </>
  ),
  baseframe: (id) => (
    <>
      <Ground id={id} w={50} />
      <path d="M10 88l10-8h84l-10 8z" fill={u(id.metal)} />
      <rect x="10" y="88" width="84" height="10" rx="1.5" fill="#7b8698" />
      <circle cx="36" cy="64" r="20" fill={u(id.blue)} />
      <circle cx="36" cy="65" r="9" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      <rect x="30" y="36" width="12" height="10" rx="2" fill={u(id.metal)} />
      <rect x="56" y="62" width="8" height="6" rx="1.5" fill="#8d97a8" />
      <rect x="62" y="50" width="38" height="30" rx="9" fill={u(id.deep)} />
      {[56, 62, 68, 74].map((y) => (
        <rect key={y} x="67" y={y} width="28" height="1.8" rx="0.9" fill="#fff" opacity="0.25" />
      ))}
      <rect x="74" y="42" width="12" height="9" rx="2" fill={u(id.blue)} />
      <path d="M22 54a18 18 0 0 1 22-8" stroke="#fff" strokeOpacity="0.55" strokeWidth="3" strokeLinecap="round" fill="none" />
    </>
  ),
  shaft: (id) => (
    <>
      <Ground id={id} w={46} />
      <rect x="10" y="56" width="100" height="12" rx="6" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      <rect x="12" y="58" width="96" height="3" rx="1.5" fill="#fff" opacity="0.7" />
      <rect x="46" y="40" width="12" height="44" rx="4" fill={u(id.blue)} />
      <rect x="62" y="40" width="12" height="44" rx="4" fill={u(id.deep)} />
      <rect x="57" y="48" width="6" height="28" rx="2" fill="#1e3a8a" opacity="0.6" />
      <rect x="18" y="54" width="6" height="16" rx="1.5" fill="#8d97a8" />
    </>
  ),
  seal: (id) => (
    <>
      <Ground id={id} w={30} />
      <circle cx="60" cy="58" r="36" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="1" />
      <circle cx="60" cy="58" r="26" fill={u(id.blue)} />
      <circle cx="60" cy="58" r="15" fill="#fff" />
      <circle cx="60" cy="58" r="15" fill="none" stroke="#2448a8" strokeOpacity="0.3" strokeWidth="2" />
      <path d="M34 42a32 32 0 0 1 40-14" stroke="#fff" strokeWidth="4" strokeLinecap="round" fill="none" opacity="0.8" />
    </>
  ),
  valve: (id) => (
    <>
      <Ground id={id} w={46} />
      <rect x="10" y="62" width="100" height="18" rx="3" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      <rect x="10" y="58" width="8" height="26" rx="2" fill="#8d97a8" />
      <rect x="102" y="58" width="8" height="26" rx="2" fill="#8d97a8" />
      <path d="M40 84V58c0-8 6-12 20-12s20 4 20 12v26z" fill={u(id.blue)} />
      <rect x="57" y="26" width="6" height="22" fill="#6b7587" />
      <ellipse cx="60" cy="26" rx="22" ry="6" fill="none" stroke={u(id.red)} strokeWidth="5" />
      <path d="M44 62c4-8 18-10 28-4" stroke="#fff" strokeOpacity="0.55" strokeWidth="3" strokeLinecap="round" fill="none" />
    </>
  ),
  quote: (id) => (
    <>
      <Ground id={id} w={32} />
      <rect x="36" y="18" width="52" height="70" rx="6" fill={u(id.blue)} opacity="0.5" transform="rotate(8 62 53)" />
      <rect x="30" y="16" width="52" height="72" rx="6" fill={u(id.paper)} stroke="#c9d6f0" />
      <rect x="38" y="28" width="26" height="4" rx="2" fill="#3c6fe0" />
      {[40, 48, 56].map((y) => (
        <rect key={y} x="38" y={y} width="36" height="3" rx="1.5" fill="#b9c7e4" />
      ))}
      <rect x="38" y="66" width="20" height="3" rx="1.5" fill="#b9c7e4" />
      <circle cx="84" cy="78" r="15" fill={u(id.green)} />
      <text x="84" y="84" textAnchor="middle" fontSize="16" fontWeight="700" fill="#fff" fontFamily="Inter, sans-serif">₹</text>
    </>
  ),
  negotiation: (id) => (
    <>
      <Ground id={id} w={36} />
      <path d="M22 40l30-16h26v26L48 82z" fill={u(id.paper)} stroke="#c9d6f0" transform="rotate(-6 50 50)" />
      <path d="M40 56l30-16h26v26L66 98z" fill={u(id.blue)} />
      <circle cx="86" cy="50" r="4" fill="#fff" />
      <text x="68" y="76" textAnchor="middle" fontSize="15" fontWeight="700" fill="#fff" fontFamily="Inter, sans-serif">₹</text>
      <path d="M28 20v14m0 0l-5-5m5 5l5-5" stroke="#16a063" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </>
  ),
  order: (id) => (
    <>
      <Ground id={id} w={38} />
      <path d="M60 30l34 14v36L60 96 26 80V44z" fill={u(id.deep)} />
      <path d="M60 30l34 14-34 16-34-16z" fill={u(id.blue)} />
      <path d="M60 60v36L26 80V44z" fill="#6f98f0" />
      <path d="M43 37l34 15" stroke="#fff" strokeOpacity="0.6" strokeWidth="5" />
      <circle cx="90" cy="30" r="14" fill={u(id.green)} />
      <path d="M83 30l5 5 9-10" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </>
  ),
  truck: (id) => (
    <>
      <Ground id={id} w={48} />
      <rect x="10" y="38" width="62" height="44" rx="6" fill={u(id.blue)} />
      <path d="M16 46h50" stroke="#fff" strokeOpacity="0.5" strokeWidth="3" strokeLinecap="round" />
      <path d="M72 52h20l14 16v14H72z" fill={u(id.deep)} />
      <path d="M78 56h12l9 11H78z" fill="#dbe7ff" />
      <circle cx="30" cy="86" r="10" fill="#2b3444" />
      <circle cx="30" cy="86" r="4" fill={u(id.metal)} />
      <circle cx="88" cy="86" r="10" fill="#2b3444" />
      <circle cx="88" cy="86" r="4" fill={u(id.metal)} />
    </>
  ),
  clipboard: (id) => (
    <>
      <Ground id={id} w={32} />
      <rect x="28" y="20" width="60" height="76" rx="8" fill={u(id.deep)} />
      <rect x="34" y="28" width="48" height="62" rx="4" fill={u(id.paper)} />
      <rect x="46" y="14" width="24" height="14" rx="4" fill={u(id.metal)} stroke="#8d97a8" strokeWidth="0.8" />
      {[42, 54, 66].map((y) => (
        <g key={y}>
          <rect x="40" y={y - 3} width="7" height="7" rx="2" fill={u(id.green)} />
          <rect x="51" y={y - 1} width="25" height="3" rx="1.5" fill="#b9c7e4" />
        </g>
      ))}
      <rect x="40" y="76" width="18" height="3" rx="1.5" fill="#b9c7e4" />
    </>
  ),
  shelf: (id) => (
    <>
      <Ground id={id} w={46} />
      <rect x="14" y="20" width="6" height="80" rx="2" fill="#7b8698" />
      <rect x="100" y="20" width="6" height="80" rx="2" fill="#7b8698" />
      <rect x="14" y="54" width="92" height="5" rx="2" fill={u(id.metal)} />
      <rect x="14" y="90" width="92" height="5" rx="2" fill={u(id.metal)} />
      <rect x="26" y="30" width="26" height="24" rx="3" fill={u(id.blue)} />
      <rect x="56" y="36" width="20" height="18" rx="3" fill={u(id.amber)} />
      <rect x="80" y="28" width="16" height="26" rx="3" fill={u(id.deep)} />
      <rect x="26" y="68" width="18" height="22" rx="3" fill={u(id.deep)} />
      <rect x="48" y="64" width="30" height="26" rx="3" fill={u(id.blue)} />
      <rect x="82" y="72" width="14" height="18" rx="3" fill={u(id.green)} />
      <rect x="34" y="30" width="10" height="5" rx="1" fill="#fff" opacity="0.6" />
      <rect x="56" y="64" width="14" height="5" rx="1" fill="#fff" opacity="0.6" />
    </>
  ),
  factory: (id) => (
    <>
      <Ground id={id} w={48} />
      <rect x="80" y="18" width="12" height="40" rx="2" fill="#7b8698" />
      <circle cx="92" cy="12" r="6" fill="#d6dde9" />
      <path d="M14 52l22-14v14l22-14v14l22-14v58H14z" fill={u(id.blue)} />
      <rect x="14" y="70" width="88" height="26" fill={u(id.deep)} />
      {[22, 40, 58, 76].map((x) => (
        <rect key={x} x={x} y="76" width="12" height="10" rx="1.5" fill="#dbe7ff" />
      ))}
      <rect x="92" y="78" width="8" height="18" rx="1" fill={u(id.amber)} />
    </>
  ),
  building: (id) => (
    <>
      <Ground id={id} w={40} />
      <rect x="28" y="20" width="44" height="78" rx="4" fill={u(id.blue)} />
      <rect x="72" y="46" width="24" height="52" rx="3" fill={u(id.deep)} />
      {[30, 44, 58, 72].map((y) =>
        [36, 52].map((x) => <rect key={`${x}-${y}`} x={x} y={y} width="10" height="8" rx="1.5" fill="#e8f0ff" opacity="0.9" />),
      )}
      {[56, 68, 80].map((y) => (
        <rect key={y} x="78" y={y} width="12" height="6" rx="1" fill="#9cc0ff" />
      ))}
      <rect x="44" y="86" width="12" height="12" rx="1.5" fill={u(id.amber)} />
    </>
  ),
  chart: (id) => (
    <>
      <Ground id={id} w={42} />
      <rect x="16" y="20" width="88" height="76" rx="10" fill={u(id.paper)} stroke="#c9d6f0" />
      <rect x="28" y="62" width="12" height="24" rx="3" fill={u(id.blue)} />
      <rect x="46" y="50" width="12" height="36" rx="3" fill={u(id.deep)} />
      <rect x="64" y="56" width="12" height="30" rx="3" fill={u(id.blue)} />
      <rect x="82" y="38" width="12" height="48" rx="3" fill={u(id.green)} />
      <path d="M30 50l18-14 18 8 22-16" stroke="#16a063" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle cx="88" cy="28" r="4" fill="#16a063" />
    </>
  ),
  bell: (id) => (
    <>
      <Ground id={id} w={30} />
      <path d="M60 18c-16 0-26 12-26 28v20l-8 12h68l-8-12V46c0-16-10-28-26-28z" fill={u(id.blue)} />
      <path d="M42 44c0-10 6-17 14-19" stroke="#fff" strokeOpacity="0.6" strokeWidth="4" strokeLinecap="round" fill="none" />
      <rect x="24" y="76" width="72" height="8" rx="4" fill={u(id.deep)} />
      <circle cx="60" cy="92" r="7" fill={u(id.amber)} />
      <circle cx="86" cy="26" r="10" fill={u(id.red)} />
    </>
  ),
  check: (id) => (
    <>
      <Ground id={id} w={30} />
      <circle cx="60" cy="56" r="36" fill={u(id.green)} />
      <path d="M36 42a30 30 0 0 1 30-14" stroke="#fff" strokeOpacity="0.55" strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M44 57l11 11 22-24" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M98 22l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#ffc55c" />
      <path d="M20 80l1.5 3.5 3.5 1.5-3.5 1.5-1.5 3.5-1.5-3.5-3.5-1.5 3.5-1.5z" fill="#9cc0ff" />
    </>
  ),
  tray: (id) => (
    <>
      <Ground id={id} w={42} />
      <rect x="40" y="18" width="40" height="46" rx="4" fill={u(id.paper)} stroke="#c9d6f0" transform="rotate(-8 60 41)" />
      <path d="M18 62l12-20h60l12 20v26a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6z" fill={u(id.blue)} />
      <path d="M18 62h28a14 10 0 0 0 28 0h28v26a6 6 0 0 1-6 6H24a6 6 0 0 1-6-6z" fill={u(id.deep)} />
    </>
  ),
  lock: (id) => (
    <>
      <Ground id={id} w={30} />
      <path d="M40 50V38a20 20 0 0 1 40 0v12" stroke={u(id.metal)} strokeWidth="9" fill="none" />
      <rect x="28" y="48" width="64" height="48" rx="10" fill={u(id.blue)} />
      <path d="M34 56h52" stroke="#fff" strokeOpacity="0.5" strokeWidth="3" strokeLinecap="round" />
      <circle cx="60" cy="70" r="7" fill="#1e3a8a" />
      <rect x="57" y="72" width="6" height="12" rx="2" fill="#1e3a8a" />
    </>
  ),
  warning: (id) => (
    <>
      <Ground id={id} w={36} />
      <path d="M60 16l44 76a6 6 0 0 1-5 9H21a6 6 0 0 1-5-9z" fill={u(id.amber)} />
      <path d="M52 34l-18 32" stroke="#fff" strokeOpacity="0.5" strokeWidth="4" strokeLinecap="round" />
      <rect x="56" y="44" width="8" height="30" rx="4" fill="#fff" />
      <circle cx="60" cy="84" r="5" fill="#fff" />
    </>
  ),
  people: (id) => (
    <>
      <Ground id={id} w={40} />
      <circle cx="44" cy="40" r="14" fill={u(id.blue)} />
      <path d="M18 92c0-18 12-30 26-30s26 12 26 30z" fill={u(id.blue)} />
      <circle cx="78" cy="46" r="12" fill={u(id.deep)} />
      <path d="M56 94c0-16 10-26 22-26s22 10 22 26z" fill={u(id.deep)} />
    </>
  ),
};

export function Art({ name, size = 96, className = "" }: { name: ArtName; size?: number; className?: string }) {
  const base = useId().replace(/:/g, "");
  const id: Ids = {
    blue: `${base}b`,
    deep: `${base}d`,
    paper: `${base}p`,
    metal: `${base}m`,
    green: `${base}g`,
    amber: `${base}a`,
    red: `${base}r`,
    glow: `${base}w`,
  };
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} className={className} aria-hidden focusable="false">
      <Defs id={id} />
      {DRAW[name](id)}
    </svg>
  );
}
