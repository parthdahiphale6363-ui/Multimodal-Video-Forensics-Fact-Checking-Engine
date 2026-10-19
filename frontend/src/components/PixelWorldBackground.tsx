'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

// ─── Attractive Pixel Cat Sprites (Width 32 x Height 22) ───────────────────
type ColorPalette = Record<string, string>;

const CAT_PALETTE: ColorPalette = {
  'O': '#231812', // Warm rich dark espresso outline
  'G': '#f59e0b', // Radiant golden ginger fur (vibrant honey orange)
  'H': '#fbbf24', // Sunny fur highlight (warm amber gold)
  'D': '#d97706', // Rich caramel shadow (belly, hind leg depth)
  'T': '#b45309', // Tabby stripes / ginger markings
  'W': '#ffffff', // Crisp snow white (cheeks, bib, white paws)
  'C': '#fef3c7', // Creamy fur accent
  'E': '#f472b6', // Sweet rose pink (inner ear)
  'N': '#fb7185', // Cute tiny pink button nose
  'P': '#18181b', // Glossy obsidian pupil
  'S': '#ffffff', // Bright eye twinkle / specular reflection
  'B': '#fda4af', // Sweet rosy cheek blush
};

const SPRITES: Record<string, string[]> = {
  // Stride A: Left front paw forward with white sock, right hind leg back
  walk1: [
    "................................",
    "................................",
    "....OO..........................",
    "...OGGO...............OO...OO...",
    "...OGGO..............OEOO.OEOO..",
    "....OGGO.............OGGO.OGGO..",
    "....OGGO...OOOOOOOO..OGGGOOGGGO.",
    ".....OGGO.OGGGTTGGGOOGGGGGGGGGGO",
    ".....OGGOOGGTTGGGGGOGGGGSPOOGGGO",
    "......OGGOGGGGGGGGGOGGGGPPOOBNBO",
    "......OGGGGGGGGTTGGGGGGGBWWWWWWO",
    ".......OGGGGGGGGGGGGGGGGGWWWWWO.",
    "......OGGGGGGGGGGGGGGGGWWWWWWO..",
    ".....OGGGGGGGGGGGDDDDDGGWWWWWO..",
    "....OGGGGGGGDDDDDDDDDDWWWWWWO...",
    "....ODDDDDDO.OOOO.ODDDDWWWWWO...",
    "...OGGGO.OGGO...OGGGO...OGGO....",
    "...OGGO..OGGO...OGGO....OGGO....",
    "...OGGO..OGGO...OGGO....OGGO....",
    "...OWWO..OWWO...OWWO....OWWO....",
    "...OOOO..OOOO...OOOO....OOOO....",
    "................................",
  ],
  // Passing A: Body bobs up 1px, paws passing
  walk2: [
    "................................",
    ".....OO.........................",
    "....OGGO........................",
    "...OGGO...............OO...OO...",
    "...OGGO..............OEOO.OEOO..",
    "....OGGO.............OGGO.OGGO..",
    "....OGGO...OOOOOOOO..OGGGOOGGGO.",
    ".....OGGO.OGGGTTGGGOOGGGGGGGGGGO",
    ".....OGGOOGGTTGGGGGOGGGGSPOOGGGO",
    "......OGGOGGGGGGGGGOGGGGPPOOBNBO",
    "......OGGGGGGGGTTGGGGGGGBWWWWWWO",
    ".......OGGGGGGGGGGGGGGGGGWWWWWO.",
    "......OGGGGGGGGGGGGGGGGWWWWWWO..",
    ".....OGGGGGGGGGGGDDDDDGGWWWWWO..",
    "....OGGGGGGGDDDDDDDDDDWWWWWWO...",
    "....ODDDDDDO.OOOO.ODDDDWWWWWO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OWWO....OWWO..OWWO..OWWO...",
    ".....OOOO....OOOO..OOOO..OOOO...",
    "................................",
  ],
  // Stride B: Right front paw forward, left hind leg back
  walk3: [
    "................................",
    "................................",
    "....OO..........................",
    "...OGGO...............OO...OO...",
    "...OGGO..............OEOO.OEOO..",
    "....OGGO.............OGGO.OGGO..",
    "....OGGO...OOOOOOOO..OGGGOOGGGO.",
    ".....OGGO.OGGGTTGGGOOGGGGGGGGGGO",
    ".....OGGOOGGTTGGGGGOGGGGSPOOGGGO",
    "......OGGOGGGGGGGGGOGGGGPPOOBNBO",
    "......OGGGGGGGGTTGGGGGGGBWWWWWWO",
    ".......OGGGGGGGGGGGGGGGGGWWWWWO.",
    "......OGGGGGGGGGGGGGGGGWWWWWWO..",
    ".....OGGGGGGGGGGGDDDDDGGWWWWWO..",
    "....OGGGGGGGDDDDDDDDDDWWWWWWO...",
    "....ODDDDDDO.OOOO.ODDDDWWWWWO...",
    "....OGGO...OGGGO....OGGO.OGGGO..",
    "....OGGO....OGGO....OGGO..OGGO..",
    "....OGGO....OGGO....OGGO..OGGO..",
    "....OWWO....OWWO....OWWO..OWWO..",
    "....OOOO....OOOO....OOOO..OOOO..",
    "................................",
  ],
  // Passing B: Legs gathering in opposite phase
  walk4: [
    "................................",
    "....OO..........................",
    "...OGGO.........................",
    "...OGGO...............OO...OO...",
    "...OGGO..............OEOO.OEOO..",
    "....OGGO.............OGGO.OGGO..",
    "....OGGO...OOOOOOOO..OGGGOOGGGO.",
    ".....OGGO.OGGGTTGGGOOGGGGGGGGGGO",
    ".....OGGOOGGTTGGGGGOGGGGSPOOGGGO",
    "......OGGOGGGGGGGGGOGGGGPPOOBNBO",
    "......OGGGGGGGGTTGGGGGGGBWWWWWWO",
    ".......OGGGGGGGGGGGGGGGGGWWWWWO.",
    "......OGGGGGGGGGGGGGGGGWWWWWWO..",
    ".....OGGGGGGGGGGGDDDDDGGWWWWWO..",
    "....OGGGGGGGDDDDDDDDDDWWWWWWO...",
    "....ODDDDDDO.OOOO.ODDDDWWWWWO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OWWO....OWWO..OWWO..OWWO...",
    ".....OOOO....OOOO..OOOO..OOOO...",
    "................................",
  ],
  // Sit: Sweet contented loaf with tail curled neatly around front paws
  sit: [
    "................................",
    "................................",
    "......................OO...OO...",
    ".....................OEOO.OEOO..",
    ".....................OGGO.OGGO..",
    "............OOOOOOOO.OGGGOOGGGO.",
    "..........OOGGGTTGGGOOGGGGGGGGGGO",
    "........OGGTTGGGGGGOGGGGSPOOGGGO",
    ".......OGGGGGGGGGGGOGGGGPPOOBNBO",
    ".......OGGGGGGGTTGGGGGGGBWWWWWWO",
    "......OGGGGGGGGGGGGGGGGGGWWWWWO.",
    ".....OGGGGGGGGGGGGGGGGWWWWWWO...",
    "....OGGGGGGGGGGGDDDDDGGWWWWWO...",
    "...OGGGGGGGDDDDDDDDDDDWWWWWWO...",
    "...OGGGGGODDDDDDDDDDDDWWWWWO....",
    "...OGGGO..ODDDDDDDDDDDWWWO......",
    "...OGGO...OGGGGGGO...OWWO.......",
    "...OGGO...OGGGGGGO...OWWO.......",
    "...OGGO...OWWWWWO....OWWO.......",
    "...OGGO...OOOOOO.....OOOO.......",
    "....OGGGOOOOOOOOOOOOOOO.........",
    ".....OOOOOOOOOOOOOOOOOO.........",
  ],
  // Jump: Graceful arched leap with stretched paws & trailing tail
  jump: [
    "................................",
    ".OO.............................",
    "..OGGO..........................",
    "...OGGO...............OO...OO...",
    "....OGGO.............OEOO.OEOO..",
    ".....OGGO............OGGO.OGGO..",
    "......OGGO..OOOOOOOO.OGGGOOGGGO.",
    ".......OGGOOGGGTTGGGOOGGGGGGGGGO",
    "......OGGGGGTTGGGGGOGGGGSPOOGGGO",
    "..OO....OGGGGGGGGGGGOGGGGPPOOBNBO",
    ".OGGGO..OGGGGGGTTGGGGGGGBWWWWWWO",
    ".OWWWO....OGGGGGGGGGGGGGGGWWWWWO.",
    "..OOOO....OGGGGGGGDDDDDDGWWWWWWO",
    ".........OGGGGGDDDDDDDDDWWWWWWO.",
    "........OGGGDDDDDDDDDDDOWWWWWO..",
    ".......ODDDDDDDDO.OOOO.ODDDDO...",
    "......OGGO..OGGO........OGGO.OO.",
    ".....OGGO..OGGO..........OGGOWWO",
    ".....OWWO..OWWO..........OWWOOOO",
    ".....OOOO..OOOO..........OOOO...",
    "................................",
    "................................",
  ],
  // Sniff: Cute curious tilt with twitching nose
  sniff: [
    "................................",
    ".....OO.........................",
    "....OGGO........................",
    "....OGGO........................",
    ".....OGGO.............OO...OO...",
    ".....OGGO............OEOO.OEOO..",
    "......OGGO.OOOOOOOO..OGGO.OGGO..",
    "......OGGOOGGGTTGGGOOGGGGOOGGGGO",
    ".......OGGOGGTTGGGGGOGGGGGGGGGGO",
    ".......OGGGGGGGGGGGGOGGGGSPOOGGO",
    "........OGGGGGGTTGGGGGGGGPPOOBNO",
    ".......OGGGGGGGGGGGGGGGGBWWWWWO.",
    "......OGGGGGGGGGGGGGGGGWWWWWWO..",
    ".....OGGGGGGGGGGGDDDDDGGWWWWWO..",
    "....OGGGGGGGDDDDDDDDDDWWWWWWO...",
    "....ODDDDDDO.OOOO.ODDDDWWWWWO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OGGO....OGGO..OGGO..OGGO...",
    ".....OWWO....OWWO..OWWO..OWWO...",
    ".....OOOO....OOOO..OOOO..OOOO...",
    "................................",
  ]
};


// ─── Flora Sprites ───────────────────────────────────────────────────────────
const FLOWER_PALETTE: ColorPalette = {
  'M': '#b85098',
  'L': '#e879f9',
  'D': '#581c87',
  'Y': '#facc15',
  'G': '#16a34a',
  'S': '#14532d',
};

const FLOWER_SPRITE = [
  "...DDD..DDD...",
  "..DMMMDDMMMD..",
  "..DMLMMDMLMD..",
  ".DMMMLLLLLMMD.",
  ".DMMMYYYYYMMD.",
  "..DMMMMMMMMD..",
  "...DDMMMMDD...",
  ".....DDDD.....",
  "......GG......",
  "......GG......",
  "..GG..GG..GG..",
  ".GGGG.GG.GGGG.",
  ".GGGG.GG.GGGG.",
  "..GG..GG..GG..",
  "......GG......",
  "......GG......",
  "......GG......",
  "......GG......",
];

const GRASS_PALETTE: ColorPalette = {
  'G': '#16a34a',
  'L': '#22c55e',
  'D': '#14532d',
};

const GRASS_SPRITE = [
  ".L....L...L.",
  ".G....G...G.",
  "DGD..DGD.DGD",
  "DGD..DGD.DGD",
  "DGDDDGDDDGDD",
  "DGGGGGGGGGGDD",
  ".DGGGGGGGGDD.",
  "..DDDDDDDD...",
];

// ─── Cloud Sprites (White Mode / Daytime Meadow) ─────────────────────────────
const CLOUD_PALETTE: ColorPalette = {
  'W': '#ffffff', // Radiant pure snow white
  'S': '#dbeafe', // Soft sky blue-tinted underside shadow for authentic 3D pixel fluffiness
};

const CLOUD_SMALL = [
  "...........WWWWWW.......",
  "....WWWW.WWWWWWWWWW.....",
  "..WWWWWWWWWWWWWWWWWWWW..",
  ".WWWWWWWWWWWWWWWWWWWWWW.",
  "WWWWWWWWWWWWWWWWWWWWWWWW",
  "WWWWWWWWWWWWWWWWWWWWWWWW",
  ".WWWWWWWWWWWWWWWWWWWWWW.",
  "..SSSSSSSSSSSSSSSSSSSS..",
];

const CLOUD_MEDIUM = [
  "...........WWWWWWWW.............",
  ".....WWWW.WWWWWWWWWWWW...WWWW...",
  "...WWWWWWWWWWWWWWWWWWWWWWWWWWWW.",
  ".WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW.",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  ".SSSSSSSSSSSSSSSSSSSSSSSSSSSSSS.",
  "..SSSSSSSSSSSSSSSSSSSSSSSSSSSS..",
];

const CLOUD_LARGE = [
  "...............WWWWWWWW.................",
  "........WWWW..WWWWWWWWWWWW..WWWW........",
  "....WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW....",
  "..WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW..",
  ".WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW.",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
  ".SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS.",
  "..SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS..",
];

const CLOUD_SPRITES: Record<'small' | 'medium' | 'large', string[]> = {
  small: CLOUD_SMALL,
  medium: CLOUD_MEDIUM,
  large: CLOUD_LARGE,
};

const CLOUD_WIDTHS: Record<'small' | 'medium' | 'large', number> = {
  small: 24,
  medium: 32,
  large: 40,
};

// ─── Sound Synthesizer via Web Audio API ──────────────────────────────────────
class SoundSynth {
  ctx: AudioContext | null = null;
  enabled = false;

  init() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }

  meow() {
    if (!this.enabled || !this.ctx) return;
    try {
      if (this.ctx.state === 'suspended') this.ctx.resume();
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(780, now + 0.12);
      osc.frequency.exponentialRampToValueAtTime(390, now + 0.36);

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.15, now + 0.04);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.22);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.4);
    } catch {}
  }

  purr() {
    if (!this.enabled || !this.ctx) return;
    try {
      if (this.ctx.state === 'suspended') this.ctx.resume();
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const mod = this.ctx.createOscillator();
      const modGain = this.ctx.createGain();
      const gain = this.ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(75, now);
      mod.type = 'sine';
      mod.frequency.setValueAtTime(26, now);
      modGain.gain.setValueAtTime(25, now);

      mod.connect(modGain);
      modGain.connect(osc.frequency);
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.1);
      gain.gain.linearRampToValueAtTime(0.1, now + 0.5);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      mod.start(now);
      osc.start(now);
      mod.stop(now + 0.7);
      osc.stop(now + 0.7);
    } catch {}
  }

  jump() {
    if (!this.enabled || !this.ctx) return;
    try {
      if (this.ctx.state === 'suspended') this.ctx.resume();
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(280, now);
      osc.frequency.exponentialRampToValueAtTime(620, now + 0.18);

      gain.gain.setValueAtTime(0.14, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.22);
    } catch {}
  }
}

const synth = new SoundSynth();



interface Butterfly {
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  phase: number;
}

interface Star {
  x: number;
  y: number;
  size: number;
  alpha: number;
  speed: number;
  phase: number;
}

interface ShootingStar {
  x: number;
  y: number;
  vx: number;
  vy: number;
  alpha: number;
  active: boolean;
}

interface Firefly {
  x: number;
  y: number;
  baseY: number;
  vx: number;
  phase: number;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  type: 'heart' | 'sparkle' | 'dust';
  text?: string;
}

interface MovingCloud {
  x: number;
  offsetY: number;
  isLower: boolean;
  speed: number;
  scale: number;
  type: 'small' | 'medium' | 'large';
  alpha: number;
}

interface Props {
  initialTheme?: 'night' | 'day';
}

export default function PixelWorldBackground({ initialTheme = 'night' }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Theme state: 'night' or 'day'
  const [theme, setTheme] = useState<'night' | 'day'>('night');
  const [speedMode, setSpeedMode] = useState<'walk' | 'trot' | 'zoomies'>('walk');
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [activeToy, setActiveToy] = useState<'none' | 'yarn' | 'fish'>('none');
  const [catSpeech, setCatSpeech] = useState<string | null>(null);
  const [speechTimer, setSpeechTimer] = useState<number>(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Initialize theme from localStorage or preferred scheme
  useEffect(() => {
    const savedTheme = localStorage.getItem('pixel_theme') as 'night' | 'day' | null;
    const active = savedTheme || initialTheme;
    setTheme(active);
    document.documentElement.setAttribute('data-theme', active === 'night' ? 'dark' : 'light');

    const onExternalTheme = (e: Event) => {
      const customEvent = e as CustomEvent<'night' | 'day'>;
      if (customEvent.detail && customEvent.detail !== theme) {
        setTheme(customEvent.detail);
      }
    };
    const onExternalSpeed = (e: Event) => {
      const customEvent = e as CustomEvent<'walk' | 'trot' | 'zoomies'>;
      if (customEvent.detail) {
        setSpeedMode(customEvent.detail);
      }
    };
    const onExternalSound = (e: Event) => {
      const customEvent = e as CustomEvent<boolean>;
      if (typeof customEvent.detail === 'boolean') {
        synth.init();
        synth.enabled = customEvent.detail;
        setSoundEnabled(customEvent.detail);
      }
    };

    window.addEventListener('pixel-theme-change', onExternalTheme);
    window.addEventListener('pixel-speed-change', onExternalSpeed);
    window.addEventListener('pixel-sound-change', onExternalSound);

    return () => {
      window.removeEventListener('pixel-theme-change', onExternalTheme);
      window.removeEventListener('pixel-speed-change', onExternalSpeed);
      window.removeEventListener('pixel-sound-change', onExternalSound);
    };
  }, [initialTheme, theme]);

  const toggleTheme = (newTheme?: 'night' | 'day') => {
    const next = newTheme || (theme === 'night' ? 'day' : 'night');
    setTheme(next);
    localStorage.setItem('pixel_theme', next);
    document.documentElement.setAttribute('data-theme', next === 'night' ? 'dark' : 'light');
    window.dispatchEvent(new CustomEvent('pixel-theme-change', { detail: next }));
    synth.jump();
  };

  const toggleSound = () => {
    synth.init();
    synth.enabled = !soundEnabled;
    setSoundEnabled(!soundEnabled);
    if (!soundEnabled) synth.meow();
  };

  const showSpeech = useCallback((text: string) => {
    setCatSpeech(text);
    setSpeechTimer(Date.now() + 3000);
    synth.meow();
  }, []);

  // ─── Canvas Render Engine ─────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = document.documentElement.clientWidth || window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = document.documentElement.clientWidth || window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    const PIXEL_SCALE = 3;
    const GROUND_HEIGHT = 64; // Grass + Dirt thickness at the bottom
    const GROUND_Y = height - GROUND_HEIGHT;

    // Stars (for Night Mode)
    const stars: Star[] = Array.from({ length: 85 }, () => ({
      x: Math.random() * width,
      y: Math.random() * (GROUND_Y - 40),
      size: Math.random() > 0.85 ? 3 : Math.random() > 0.45 ? 2 : 1,
      alpha: 0.3 + Math.random() * 0.7,
      speed: 0.02 + Math.random() * 0.05,
      phase: Math.random() * Math.PI * 2,
    }));

    // Shooting Stars
    const shootingStars: ShootingStar[] = [];
    let nextShootingStar = Date.now() + 4000;

    // Fireflies (Night Mode)
    const fireflies: Firefly[] = Array.from({ length: 8 }, () => ({
      x: Math.random() * width,
      y: GROUND_Y - 35 - Math.random() * 45,
      baseY: GROUND_Y - 35 - Math.random() * 45,
      vx: (Math.random() - 0.5) * 0.6,
      phase: Math.random() * Math.PI * 2,
    }));



    // Butterflies (Day Mode)
    const butterflies: Butterfly[] = [
      { x: width * 0.25, y: GROUND_Y - 50, vx: 0.8, vy: 0.3, color: '#facc15', phase: 0 },
      { x: width * 0.65, y: GROUND_Y - 40, vx: -0.7, vy: -0.2, color: '#ec4899', phase: 2 },
      { x: width * 0.85, y: GROUND_Y - 60, vx: 0.6, vy: 0.4, color: '#38bdf8', phase: 4 },
    ];

    // White Moving Clouds (Day / White Mode)
    const clouds: MovingCloud[] = [
      // High altitude clouds drifting across the upper sky
      { x: width * 0.05, offsetY: 18, isLower: false, speed: 0.28, scale: 2, type: 'small', alpha: 0.95 },
      { x: width * 0.38, offsetY: 30, isLower: false, speed: 0.20, scale: 3, type: 'large', alpha: 0.92 },
      { x: width * 0.72, offsetY: 22, isLower: false, speed: 0.24, scale: 2, type: 'medium', alpha: 0.96 },
      // Mid-lower sky clouds floating peacefully above the distant green hills
      { x: width * 0.16, offsetY: 165, isLower: true, speed: 0.38, scale: 2, type: 'medium', alpha: 0.92 },
      { x: width * 0.54, offsetY: 125, isLower: true, speed: 0.30, scale: 3, type: 'large', alpha: 0.90 },
      { x: width * 0.88, offsetY: 145, isLower: true, speed: 0.44, scale: 2, type: 'small', alpha: 0.94 },
    ];

    // Flowers & Grass
    const flowers = [
      { x: Math.floor(width * 0.12), sway: 0, type: 'purple' },
      { x: Math.floor(width * 0.32), sway: 1.2, type: 'pink' },
      { x: Math.floor(width * 0.58), sway: 2.5, type: 'purple' }, // Like Mistral screenshot
      { x: Math.floor(width * 0.78), sway: 0.8, type: 'yellow' },
      { x: Math.floor(width * 0.92), sway: 1.7, type: 'purple' },
    ];

    const grassTufts = [
      { x: Math.floor(width * 0.05), offset: 0 },
      { x: Math.floor(width * 0.22), offset: 1 },
      { x: Math.floor(width * 0.48), offset: 2 },
      { x: Math.floor(width * 0.7), offset: 0.5 },
      { x: Math.floor(width * 0.88), offset: 1.8 },
    ];

    // Particles
    const particles: Particle[] = [];

    // Cat Object
    const cat = {
      x: width * 0.3,
      y: GROUND_Y - 20 * PIXEL_SCALE + 4,
      vx: 1.4,
      vy: 0,
      facing: 1, // 1 right, -1 left
      state: 'walk' as 'walk' | 'run' | 'jump' | 'sit' | 'sniff',
      walkFrame: 0,
      animTick: 0,
      stateTimer: 0,
      isGrounded: true,
      targetX: null as number | null,
    };

    // Helper: Draw pixel sprite onto canvas with exact integer coordinates to prevent moire & seams
    const drawSprite = (
      sprite: string[],
      palette: ColorPalette,
      dx: number,
      dy: number,
      flipH = false,
      scale = PIXEL_SCALE
    ) => {
      ctx.save();
      const intX = Math.round(dx);
      const intY = Math.round(dy);
      if (flipH) {
        ctx.translate(intX + sprite[0].length * scale, intY);
        ctx.scale(-1, 1);
        for (let r = 0; r < sprite.length; r++) {
          const row = sprite[r];
          const py = r * scale;
          for (let c = 0; c < row.length; c++) {
            const char = row[c];
            if (char !== '.' && palette[char]) {
              ctx.fillStyle = palette[char];
              ctx.fillRect(c * scale, py, scale, scale);
            }
          }
        }
      } else {
        for (let r = 0; r < sprite.length; r++) {
          const row = sprite[r];
          const py = intY + r * scale;
          for (let c = 0; c < row.length; c++) {
            const char = row[c];
            if (char !== '.' && palette[char]) {
              ctx.fillStyle = palette[char];
              ctx.fillRect(intX + c * scale, py, scale, scale);
            }
          }
        }
      }
      ctx.restore();
    };



    // Click handler for cat & meadow
    const onCanvasClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        target.closest(
          'button, input, a, select, textarea, [role="button"], [role="toolbar"], .glass, .demo-card, .module-card, .url-command-bar, .pixel-floating-dock, .modal-backdrop, .error-box'
        )
      ) {
        return; // Never intercept clicks on dashboard UI controls
      }

      const rect = canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      // Pet cat check
      const catW = 32 * PIXEL_SCALE;
      const catH = 20 * PIXEL_SCALE;
      if (
        clickX >= cat.x &&
        clickX <= cat.x + catW &&
        clickY >= cat.y - 20 &&
        clickY <= cat.y + catH + 10
      ) {
        cat.state = 'jump';
        cat.vy = -6.2;
        cat.isGrounded = false;
        synth.jump();
        synth.meow();

        for (let i = 0; i < 6; i++) {
          particles.push({
            x: cat.x + catW / 2 + (Math.random() - 0.5) * 20,
            y: cat.y,
            vx: (Math.random() - 0.5) * 2.5,
            vy: -2 - Math.random() * 2.5,
            life: 0,
            maxLife: 60,
            type: 'heart',
            text: '❤️',
          });
        }
        showSpeech(theme === 'day' ? "Lovely day! 🐾☀️" : "Meow in the stars! 🐾🌙");
        return;
      }

      // If clicked on meadow, plant flower!
      if (clickY >= GROUND_Y - 20) {
        flowers.push({
          x: clickX,
          sway: Math.random() * Math.PI,
          type: Math.random() > 0.5 ? 'purple' : 'pink',
        });
        cat.targetX = clickX;
        for (let i = 0; i < 6; i++) {
          particles.push({
            x: clickX,
            y: GROUND_Y - 10,
            vx: (Math.random() - 0.5) * 3,
            vy: -1.5 - Math.random() * 2,
            life: 0,
            maxLife: 45,
            type: 'sparkle',
          });
        }
        showSpeech("New flower planted! 🌸");
      }
    };

    window.addEventListener('click', onCanvasClick);

    // ─── Main Animation Loop ─────────────────────────────────────────────────
    const loop = (time: number) => {
      // ── 1. Clear & Sky Gradient ──
      ctx.clearRect(0, 0, width, height);

      const skyGrad = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
      if (theme === 'night') {
        skyGrad.addColorStop(0, '#040612');
        skyGrad.addColorStop(0.55, '#070b20');
        skyGrad.addColorStop(1, '#0e1438');
      } else {
        skyGrad.addColorStop(0, '#1d4ed8'); // Deep vibrant blue
        skyGrad.addColorStop(0.4, '#38bdf8'); // Clear azure
        skyGrad.addColorStop(0.85, '#7dd3fc');
        skyGrad.addColorStop(1, '#bae6fd'); // Soft horizon mist
      }
      ctx.fillStyle = skyGrad;
      ctx.fillRect(0, 0, width, GROUND_Y);

      // ── 2. Sky Elements (Night: Stars & Moon; Day: Sun & Clouds) ──
      if (theme === 'night') {
        // Starfield
        stars.forEach(st => {
          st.phase += st.speed;
          const alpha = 0.25 + 0.75 * Math.abs(Math.sin(st.phase));
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
          ctx.fillRect(st.x, st.y, st.size, st.size);
        });

        // Shooting Stars
        if (Date.now() > nextShootingStar) {
          shootingStars.push({
            x: Math.random() * width * 0.75,
            y: Math.random() * (GROUND_Y * 0.35),
            vx: 8 + Math.random() * 5,
            vy: 3 + Math.random() * 3,
            alpha: 1,
            active: true,
          });
          nextShootingStar = Date.now() + 6000 + Math.random() * 8000;
        }

        for (let i = shootingStars.length - 1; i >= 0; i--) {
          const ss = shootingStars[i];
          ss.x += ss.vx;
          ss.y += ss.vy;
          ss.alpha -= 0.025;

          ctx.strokeStyle = `rgba(255, 255, 255, ${ss.alpha})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(ss.x, ss.y);
          ctx.lineTo(ss.x - ss.vx * 3.5, ss.y - ss.vy * 3.5);
          ctx.stroke();

          if (ss.alpha <= 0) shootingStars.splice(i, 1);
        }

        // 8-bit Crescent Moon (Top-Left Sky)
        const moonX = 44;
        const moonY = 28;
        ctx.fillStyle = 'rgba(254, 240, 138, 0.18)';
        ctx.beginPath();
        ctx.arc(moonX + 14, moonY + 14, 26, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        const moonBlocks = [
          "..####..",
          ".######.",
          "###..###",
          "##......",
          "##......",
          "###..###",
          ".######.",
          "..####..",
        ];
        moonBlocks.forEach((row, r) => {
          for (let c = 0; c < row.length; c++) {
            if (row[c] === '#') {
              ctx.fillRect(moonX + c * 3.5, moonY + r * 3.5, 3.5, 3.5);
            }
          }
        });

        // Fireflies
        fireflies.forEach(ff => {
          ff.x += ff.vx;
          ff.phase += 0.03;
          ff.y = ff.baseY + Math.sin(ff.phase) * 8;
          if (ff.x < 0) ff.x = width;
          if (ff.x > width) ff.x = 0;

          const pulse = 0.4 + 0.6 * Math.abs(Math.sin(ff.phase * 1.5));
          ctx.fillStyle = `rgba(217, 249, 157, ${pulse * 0.3})`;
          ctx.beginPath();
          ctx.arc(ff.x, ff.y, 6, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = `rgba(250, 204, 21, ${pulse})`;
          ctx.fillRect(ff.x - 1, ff.y - 1, 3, 3);
        });
      } else {
        // DAY MODE: Radiant 8-Bit Golden Sun with Rays (Top-Left Sky)
        const sunX = 44;
        const sunY = 28;
        const sunPulse = 1 + Math.sin(time * 0.003) * 0.06;

        // Radiant warm ambient sun glow
        ctx.fillStyle = 'rgba(253, 224, 71, 0.22)';
        ctx.beginPath();
        ctx.arc(sunX + 22, sunY + 22, 48 * sunPulse, 0, Math.PI * 2);
        ctx.fill();

        // Charming 8-bit Sun sprite (with transparent background)
        const sunBlocks = [
          "..R...R...R..",
          "....#####....",
          ".R.#######.R.",
          "..#########..",
          ".###########.",
          "R##E#####E##R",
          ".###########.",
          "..##MMMMM##..",
          ".R.#######.R.",
          "....#####....",
          "..R...R...R..",
        ];
        const sunScale = 3.2;
        sunBlocks.forEach((row, r) => {
          for (let c = 0; c < row.length; c++) {
            const ch = row[c];
            if (ch === '#') {
              ctx.fillStyle = '#facc15';
              ctx.fillRect(sunX + c * sunScale, sunY + r * sunScale, sunScale, sunScale);
            } else if (ch === 'R') {
              ctx.fillStyle = '#fbbf24';
              ctx.fillRect(sunX + c * sunScale, sunY + r * sunScale, sunScale, sunScale);
            } else if (ch === 'E') {
              ctx.fillStyle = '#78350f';
              ctx.fillRect(sunX + c * sunScale, sunY + r * sunScale, sunScale, sunScale);
            } else if (ch === 'M') {
              ctx.fillStyle = '#92400e';
              ctx.fillRect(sunX + c * sunScale, sunY + r * sunScale, sunScale, sunScale);
            }
          }
        });

        // 8-Bit Fluffy White Moving Clouds (Day Mode)
        clouds.forEach(cl => {
          cl.x += cl.speed;
          const sprite = CLOUD_SPRITES[cl.type];
          const cWidth = CLOUD_WIDTHS[cl.type] * cl.scale;
          if (cl.x > width + 50) {
            cl.x = -cWidth - 50;
          }
          const drawY = cl.isLower ? Math.max(140, GROUND_Y - cl.offsetY) : cl.offsetY;
          ctx.save();
          ctx.globalAlpha = cl.alpha;
          drawSprite(sprite, CLOUD_PALETTE, cl.x, drawY, false, cl.scale);
          ctx.restore();
        });

        // Fluttering Butterflies
        butterflies.forEach(bf => {
          bf.x += bf.vx;
          bf.phase += 0.1;
          bf.y += Math.sin(bf.phase) * 0.8 + bf.vy * 0.2;
          if (bf.x < -20) bf.x = width + 10;
          if (bf.x > width + 20) bf.x = -10;

          // 2-frame wing flap
          const flap = Math.sin(bf.phase * 3) > 0;
          ctx.fillStyle = bf.color;
          ctx.fillRect(bf.x, bf.y, 4, flap ? 4 : 2);
          ctx.fillRect(bf.x + (bf.vx > 0 ? 4 : -4), bf.y - (flap ? 2 : 0), 3, 3);
        });
      }

      // ── 3. Distant Pixel Hills Layer ──
      ctx.fillStyle = theme === 'night' ? 'rgba(16, 24, 52, 0.7)' : 'rgba(74, 222, 128, 0.45)';
      ctx.beginPath();
      ctx.moveTo(0, GROUND_Y);
      for (let hx = 0; hx <= width; hx += 80) {
        const hy = GROUND_Y - 22 - Math.sin((hx + time * 0.02) * 0.008) * 16;
        ctx.lineTo(hx, hy);
      }
      ctx.lineTo(width, GROUND_Y);
      ctx.closePath();
      ctx.fill();

      // ── 4. Ground: Grass & Checkered Earth Dirt Blocks ──
      const grassH = 14;
      ctx.fillStyle = '#16a34a'; // Grass base
      ctx.fillRect(0, GROUND_Y, width, grassH);

      // Jagged 8-bit grass tooth highlights
      ctx.fillStyle = '#22c55e';
      for (let x = 0; x < width; x += 8) {
        ctx.fillRect(x, GROUND_Y - 3, 4, 3);
        ctx.fillRect(x + 2, GROUND_Y - 5, 2, 2);
        ctx.fillRect(x + 4, GROUND_Y - 2, 4, 2);
      }

      // Dirt Blocks Section (16x16 Checkered Platformer Grid)
      const dirtY = GROUND_Y + grassH;
      const dirtH = height - dirtY;
      ctx.fillStyle = '#3a2016';
      ctx.fillRect(0, dirtY, width, dirtH);

      const tileSize = 16;
      for (let tx = 0; tx < width; tx += tileSize) {
        for (let ty = dirtY; ty < height; ty += tileSize) {
          const isEven = (tx / tileSize + Math.floor((ty - dirtY) / tileSize)) % 2 === 0;
          ctx.fillStyle = isEven ? '#4a2c1b' : '#331c12';
          ctx.fillRect(tx, ty, tileSize, tileSize);

          ctx.fillStyle = isEven ? '#5d3823' : '#29150b';
          ctx.fillRect(tx + 3, ty + 4, 3, 3);
          ctx.fillRect(tx + 9, ty + 10, 4, 3);

          ctx.strokeStyle = '#221108';
          ctx.lineWidth = 1;
          ctx.strokeRect(tx, ty, tileSize, tileSize);
        }
      }

      // ── 5. Flora: Swaying Flowers & Grass Tufts ──
      const swayTime = time * 0.003;
      grassTufts.forEach(gt => {
        const sway = Math.sin(swayTime + gt.offset) * 1.5;
        drawSprite(GRASS_SPRITE, GRASS_PALETTE, gt.x + sway, GROUND_Y - 14, false, 2);
      });

      flowers.forEach(fl => {
        const sway = Math.sin(swayTime + fl.sway) * 2;
        let pal = { ...FLOWER_PALETTE };
        if (fl.type === 'pink') {
          pal.M = '#ec4899';
          pal.L = '#fbcfe8';
          pal.D = '#831843';
        } else if (fl.type === 'yellow') {
          pal.M = '#eab308';
          pal.L = '#fef08a';
          pal.D = '#713f12';
        }
        drawSprite(FLOWER_SPRITE, pal, fl.x + sway, GROUND_Y - 32, false, 2);
      });

      // ── 6. Cat AI, Physics & Animation ──
      const catBaseSpeed = speedMode === 'zoomies' ? 4.2 : speedMode === 'trot' ? 2.4 : 1.3;
      const targetY = GROUND_Y - 20 * PIXEL_SCALE + 4;

      if (!cat.isGrounded) {
        cat.vy += 0.35; // gravity
        cat.y += cat.vy;
        if (cat.y >= targetY) {
          cat.y = targetY;
          cat.vy = 0;
          cat.isGrounded = true;
          cat.state = 'walk';
        }
      }

      if (cat.stateTimer > 0) {
        cat.stateTimer--;
        if (cat.stateTimer === 0 && cat.isGrounded) cat.state = 'walk';
      }

      if (cat.isGrounded) {
        if (cat.state === 'walk' || cat.state === 'run') {
          if (cat.targetX !== null) {
            const dx = cat.targetX - (cat.x + 40);
            if (Math.abs(dx) > 15) {
              cat.facing = dx > 0 ? 1 : -1;
              cat.vx = cat.facing * (cat.state === 'run' ? catBaseSpeed * 1.4 : catBaseSpeed);
              cat.x += cat.vx;
            } else {
              cat.targetX = null;
              cat.state = 'sniff';
              cat.stateTimer = 50;
            }
          } else {
            cat.vx = cat.facing * catBaseSpeed;
            cat.x += cat.vx;

            const rightLimit = width - 36 * PIXEL_SCALE;
            const leftLimit = 10;
            if (cat.x > rightLimit) {
              cat.x = rightLimit;
              cat.facing = -1;
              if (Math.random() > 0.4) {
                cat.state = 'sit';
                cat.stateTimer = 45;
              }
            } else if (cat.x < leftLimit) {
              cat.x = leftLimit;
              cat.facing = 1;
              if (Math.random() > 0.4) {
                cat.state = 'sit';
                cat.stateTimer = 45;
              }
            }

            // Hop over flowers
            flowers.forEach(fl => {
              const distFl = fl.x - (cat.x + 30);
              if (Math.abs(distFl) < 8 && Math.random() > 0.5) {
                cat.state = 'jump';
                cat.vy = -4.8;
                cat.isGrounded = false;
                synth.jump();
              }
            });

            if (Math.random() < 0.003) {
              cat.state = 'sniff';
              cat.stateTimer = 60;
            } else if (Math.random() < 0.001) {
              cat.state = 'sit';
              cat.stateTimer = 90;
              synth.purr();
            }
          }

          cat.animTick++;
          const frameInterval = speedMode === 'zoomies' ? 4 : speedMode === 'trot' ? 7 : 11;
          if (cat.animTick % frameInterval === 0) {
            cat.walkFrame = (cat.walkFrame + 1) % 4;
            if (speedMode === 'zoomies' && Math.random() > 0.5) {
              particles.push({
                x: cat.facing > 0 ? cat.x : cat.x + 32 * PIXEL_SCALE,
                y: cat.y + 18 * PIXEL_SCALE,
                vx: -cat.facing * 0.8,
                vy: -0.4,
                life: 0,
                maxLife: 20,
                type: 'dust',
              });
            }
          }
        }
      }

      // ── 7. Draw Cat Sprite ──
      let currentSprite: string[];
      if (cat.state === 'jump') currentSprite = SPRITES.jump;
      else if (cat.state === 'sit') currentSprite = SPRITES.sit;
      else if (cat.state === 'sniff') currentSprite = SPRITES.sniff;
      else {
        const walkFrames = [SPRITES.walk1, SPRITES.walk2, SPRITES.walk3, SPRITES.walk4];
        currentSprite = walkFrames[cat.walkFrame];
      }

      drawSprite(currentSprite, CAT_PALETTE, cat.x, cat.y, cat.facing < 0, PIXEL_SCALE);

      // ── 8. Speech Bubble ──
      if (catSpeech && Date.now() < speechTimer) {
        const bubbleX = Math.max(15, Math.min(width - 160, cat.x + (cat.facing > 0 ? 30 : -50)));
        const bubbleY = cat.y - 36;

        ctx.font = 'bold 12px "Outfit", sans-serif';
        const txtWidth = ctx.measureText(catSpeech).width;
        const padX = 10;
        const bW = txtWidth + padX * 2;
        const bH = 26;

        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#18181c';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(bubbleX, bubbleY, bW, bH, 6);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.moveTo(bubbleX + 16, bubbleY + bH);
        ctx.lineTo(bubbleX + 22, bubbleY + bH + 6);
        ctx.lineTo(bubbleX + 28, bubbleY + bH);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#0f172a';
        ctx.fillText(catSpeech, bubbleX + padX, bubbleY + 17);
      }

      // ── 9. Particle Physics ──
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life++;

        const pAlpha = 1 - p.life / p.maxLife;
        if (p.type === 'heart') {
          ctx.font = '14px sans-serif';
          ctx.fillStyle = `rgba(244, 63, 94, ${pAlpha})`;
          ctx.fillText(p.text || '❤️', p.x, p.y);
        } else if (p.type === 'sparkle') {
          ctx.fillStyle = `rgba(250, 204, 21, ${pAlpha})`;
          ctx.fillRect(p.x, p.y, 3, 3);
          ctx.fillRect(p.x - 2, p.y + 1, 7, 1);
        } else if (p.type === 'dust') {
          ctx.fillStyle = `rgba(180, 160, 140, ${pAlpha * 0.5})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
          ctx.fill();
        }

        if (p.life >= p.maxLife) particles.splice(i, 1);
      }

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('click', onCanvasClick);
    };
  }, [theme, speedMode, showSpeech, catSpeech, speechTimer]);

  return (
    <div className="pixel-bg-layer" aria-hidden="true">
      <canvas ref={canvasRef} className="pixel-bg-canvas" />
    </div>
  );
}

export function PixelAnimationControls() {
  const [theme, setTheme] = useState<'night' | 'day'>('night');
  const [speedMode, setSpeedMode] = useState<'walk' | 'trot' | 'zoomies'>('walk');
  const [soundEnabled, setSoundEnabled] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('pixel_theme') as 'night' | 'day' | null;
    if (savedTheme) setTheme(savedTheme);

    const savedSpeed = localStorage.getItem('pixel_speed') as 'walk' | 'trot' | 'zoomies' | null;
    if (savedSpeed) setSpeedMode(savedSpeed);

    const savedSound = localStorage.getItem('pixel_sound');
    if (savedSound !== null) setSoundEnabled(savedSound === 'true');

    const onThemeChange = (e: Event) => {
      const customEvent = e as CustomEvent<'night' | 'day'>;
      if (customEvent.detail) setTheme(customEvent.detail);
    };
    const onSpeedChange = (e: Event) => {
      const customEvent = e as CustomEvent<'walk' | 'trot' | 'zoomies'>;
      if (customEvent.detail) setSpeedMode(customEvent.detail);
    };
    const onSoundChange = (e: Event) => {
      const customEvent = e as CustomEvent<boolean>;
      if (typeof customEvent.detail === 'boolean') setSoundEnabled(customEvent.detail);
    };

    window.addEventListener('pixel-theme-change', onThemeChange);
    window.addEventListener('pixel-speed-change', onSpeedChange);
    window.addEventListener('pixel-sound-change', onSoundChange);

    return () => {
      window.removeEventListener('pixel-theme-change', onThemeChange);
      window.removeEventListener('pixel-speed-change', onSpeedChange);
      window.removeEventListener('pixel-sound-change', onSoundChange);
    };
  }, []);

  const toggleTheme = (newTheme?: 'night' | 'day') => {
    const next = newTheme || (theme === 'night' ? 'day' : 'night');
    setTheme(next);
    localStorage.setItem('pixel_theme', next);
    document.documentElement.setAttribute('data-theme', next === 'night' ? 'dark' : 'light');
    window.dispatchEvent(new CustomEvent('pixel-theme-change', { detail: next }));
    synth.jump();
  };

  const setSpeed = (mode: 'walk' | 'trot' | 'zoomies') => {
    setSpeedMode(mode);
    localStorage.setItem('pixel_speed', mode);
    window.dispatchEvent(new CustomEvent('pixel-speed-change', { detail: mode }));
    synth.jump();
  };

  const toggleSound = () => {
    const next = !soundEnabled;
    synth.init();
    synth.enabled = next;
    setSoundEnabled(next);
    localStorage.setItem('pixel_sound', String(next));
    window.dispatchEvent(new CustomEvent('pixel-sound-change', { detail: next }));
    if (next) synth.meow();
  };

  return (
    <div className="pixel-floating-dock" role="toolbar" aria-label="Background Animation Controls">
      {/* Day / Night Pill Switch */}
      <div className="dock-theme-switch">
        <button
          type="button"
          className={`dock-btn ${theme === 'day' ? 'active' : ''}`}
          onClick={() => toggleTheme('day')}
          title="Switch to Daytime Meadow mode"
        >
          ☀️ Day
        </button>
        <button
          type="button"
          className={`dock-btn ${theme === 'night' ? 'active' : ''}`}
          onClick={() => toggleTheme('night')}
          title="Switch to Starry Midnight mode"
        >
          🌙 Night
        </button>
      </div>

      <div className="dock-divider" />

      {/* Speed presets */}
      <div className="dock-group">
        <button
          type="button"
          className={`dock-pill ${speedMode === 'walk' ? 'active' : ''}`}
          onClick={() => setSpeed('walk')}
          title="Gentle walk"
        >
          🐾 Walk
        </button>
        <button
          type="button"
          className={`dock-pill ${speedMode === 'trot' ? 'active' : ''}`}
          onClick={() => setSpeed('trot')}
          title="Trot pace"
        >
          🏃 Trot
        </button>
        <button
          type="button"
          className={`dock-pill ${speedMode === 'zoomies' ? 'active' : ''}`}
          onClick={() => setSpeed('zoomies')}
          title="Sprint zoomies!"
        >
          ⚡ Zoomies
        </button>
      </div>

      <div className="dock-divider" />

      {/* Sound Toggle */}
      <button
        type="button"
        className={`dock-pill sound-pill ${soundEnabled ? 'active' : ''}`}
        onClick={toggleSound}
        title={soundEnabled ? 'Mute 8-bit sound' : 'Enable 8-bit sound effects'}
      >
        {soundEnabled ? '🔊 Sound On' : '🔇 Muted'}
      </button>
    </div>
  );
}
