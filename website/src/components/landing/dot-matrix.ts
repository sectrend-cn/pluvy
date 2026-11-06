import { DotLayer, type RenderedPoint } from './dot-matrix-renderer.ts';
import { animationGrid, birdPoints, crocodileFrameIndex, framePoints, type GridPoint } from './dot-matrix-frames.ts';

interface GridMetrics {
  cellX: number;
  cellY: number;
  originX: number;
}

interface BirdTransform {
  cellX: number;
  cellY: number;
  x: number;
  y: number;
}

const peckStart = 4.8;
const peckEnd = peckStart + 20;
const mouthCol = 62;
const mouthRow = 47;

function metrics(width: number, height: number): GridMetrics {
  const scale = width <= 700 ? 0.75 : 0.65;
  const cellY = Math.min(width / (animationGrid.cols * 0.6), height / animationGrid.rows) * scale;
  return {
    cellX: cellY * 0.6,
    cellY,
    originX: width - animationGrid.cols * cellY * 0.6,
  };
}

function crocodilePoint(point: GridPoint, grid: GridMetrics, seconds: number): RenderedPoint {
  const insideMouth = seconds >= peckStart && seconds < peckEnd;
  return {
    x: grid.originX + point.col * grid.cellX,
    y: (animationGrid.rows - point.row - 1) * grid.cellY,
    size: insideMouth
      ? Math.max(1.4, grid.cellY * (0.2 + point.rank / 9 * 0.22))
      : Math.max(1.3, grid.cellY * (0.2 + point.rank / 9 * 0.18)),
    alpha: insideMouth
      ? Math.min(1, 0.45 + point.rank / 9 * 0.55)
      : 0.6 + point.rank / 9 * 0.4,
  };
}

function flightProgress(seconds: number): number {
  if (seconds < peckStart) return Math.max(0, Math.min(1, (seconds - 2.8) / 2));
  if (seconds >= peckEnd) return Math.max(0, Math.min(1, (26.3 - seconds) / 1.5));
  return 1;
}

function birdTransform(grid: GridMetrics, seconds: number, width: number, height: number): BirdTransform | null {
  if (seconds < 2.3 || seconds >= 26.3) return null;
  const progress = flightProgress(seconds);
  const eased = progress * progress * (3 - 2 * progress);
  const cellY = Math.max(3.2, grid.cellY);
  return {
    cellX: cellY * 0.6,
    cellY,
    x: width * 0.02 + (grid.originX + mouthCol * grid.cellX - width * 0.02) * eased,
    y: height * 0.89 + ((animationGrid.rows - mouthRow) * grid.cellY - height * 0.89) * eased,
  };
}

function birdPoint(point: GridPoint, transform: BirdTransform): RenderedPoint {
  return {
    x: transform.x + point.col * transform.cellX,
    y: transform.y - point.row * transform.cellY,
    size: Math.max(1.1, transform.cellY * 0.23),
    alpha: 1,
  };
}

export function startDotMatrix(container: HTMLElement): void {
  const canvas = container.querySelector<HTMLCanvasElement>('[data-layer="animation"]');
  if (!canvas) return;
  try {
    const layer = new DotLayer(canvas);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let grid = metrics(1, 1);
    let lastIndex = -1;
    let crocodile: RenderedPoint[] = [];
    let time = 0;
    let previousStamp = performance.now();

    function render(seconds: number): void {
      const index = crocodileFrameIndex(seconds);
      if (index !== lastIndex) {
        crocodile = framePoints(index).map((point) => crocodilePoint(point, grid, seconds));
        lastIndex = index;
      }
      const sprite = birdPoints(seconds);
      const transform = birdTransform(grid, seconds, container.clientWidth, container.clientHeight);
      const bird = sprite.length && transform ? sprite.map((point) => birdPoint(point, transform)) : [];
      layer.update([...crocodile, ...bird]);
    }

    function resize(): void {
      grid = metrics(container.clientWidth, container.clientHeight);
      layer.resize(container.clientWidth, container.clientHeight);
      lastIndex = -1;
      render(time);
    }

    const themeObserver = new MutationObserver(() => {
      layer.setColor(getComputedStyle(document.documentElement).getPropertyValue('--ink'));
      render(time);
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    layer.setColor(getComputedStyle(document.documentElement).getPropertyValue('--ink'));
    window.addEventListener('resize', resize);
    window.setInterval(() => {
      const now = performance.now();
      const elapsed = (now - previousStamp) / 1000;
      previousStamp = now;
      if (document.hidden || reducedMotion) return;
      time = (time + elapsed) % animationGrid.duration;
      render(time);
    }, 1000 / 30);
    resize();
  } catch {
    container.dataset.unavailable = 'true';
  }
}
