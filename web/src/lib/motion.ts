// One place for motion physics so every surface feels like the same instrument.
// Tight springs, crisp ease-out. Nothing bouncy, nothing sluggish.

import type { Transition, Variants } from 'motion/react';

export const SPRING: Transition = { type: 'spring', stiffness: 400, damping: 32 };
export const SPRING_SOFT: Transition = { type: 'spring', stiffness: 320, damping: 34 };
export const EASE_CRISP = [0.16, 1, 0.3, 1] as const;
export const EXIT: Transition = { duration: 0.14, ease: EASE_CRISP };

/** 40ms stagger, 6px rise. Used for the choreographed dashboard mount. */
export const zoneContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } },
};

export const zoneItem: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.32, ease: EASE_CRISP } },
};

export const drawerVariants: Variants = {
  hidden: { x: '100%' },
  show: { x: 0, transition: SPRING },
  exit: { x: '100%', transition: EXIT },
};

export const pressable = { whileTap: { scale: 0.98 }, transition: SPRING };

/** Shared-element pill used by the rail, tabs and the timeframe control. */
export const pillTransition = SPRING;
