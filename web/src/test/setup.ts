import { vi } from 'vitest';

// jsdom lacks a canvas implementation. The ultrasound tool only needs a recording stub
// for unit tests; pixel output is verified manually in a real browser.
class ContextStub {
  fillStyle = '';
  strokeStyle = '';
  lineWidth = 1;
  font = '';
  clearRect() {}
  fillRect() {}
  beginPath() {}
  ellipse() {}
  fill() {}
  stroke() {}
  moveTo() {}
  lineTo() {}
  setLineDash() {}
  fillText() {}
  arc() {}
  drawImage() {}
}

if (typeof HTMLCanvasElement !== 'undefined') {
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    value: () => new ContextStub(),
    configurable: true,
  });
}

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(globalThis, 'ResizeObserver', { value: ResizeObserverStub, configurable: true });

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'scrollTo', { value: () => {}, configurable: true });
}

if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false, media: query, onchange: null,
      addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
    })),
    configurable: true,
  });
}
