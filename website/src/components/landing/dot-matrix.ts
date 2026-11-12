import { DotLayer, type DotPalette, type RenderedPoint } from './dot-matrix-renderer.ts';
import { animationGrid, birdField, crocodileField, crocodileFrameIndex, type DensityField } from './dot-matrix-frames.ts';

interface GridMetrics {
  cellX: number;
  cellY: number;
  originX: number;
  pitch: number;
}

interface HalftoneDot {
  dx: number;
  dy: number;
  density: number;
}

interface BirdTransform {
  x: number;
  y: number;
  mirrored: boolean;
}

interface Point2D {
  x: number;
  y: number;
}

const peckStart = 4.8;
const peckEnd = peckStart + 20;
const mouthCol = 62;
const mouthRow = 47;
const densityFloor = 0.08;
const birdPitchRatio = 0.7;

function metrics(width: number, height: number): GridMetrics {
  const scale = width <= 700 ? 0.75 : 0.65;
  const cellY = Math.min(width / (animationGrid.cols * 0.6), height / animationGrid.rows) * scale;
  const cellX = cellY * 0.6;
  return {
    cellX,
    cellY,
    originX: width - animationGrid.cols * cellX,
    pitch: Math.max(2.2, cellX * 0.7),
  };
}

function fieldValue(field: DensityField, col: number, row: number): number {
  if (col < 0 || row < 0 || col >= field.cols || row >= field.rows) return 0;
  return field.values[row * field.cols + col];
}

function sampleField(field: DensityField, col: number, row: number): number {
  const left = Math.floor(col);
  const top = Math.floor(row);
  const fx = col - left;
  const fy = row - top;
  const upper = fieldValue(field, left, top) * (1 - fx) + fieldValue(field, left + 1, top) * fx;
  const lower = fieldValue(field, left, top + 1) * (1 - fx) + fieldValue(field, left + 1, top + 1) * fx;
  const value = upper * (1 - fy) + lower * fy;
  const edge = Math.min(1, Math.max(0, (value - 0.04) / 0.9));
  return edge * edge * (3 - 2 * edge);
}

function halftone(field: DensityField, cellX: number, cellY: number, pitch: number): HalftoneDot[] {
  const dots: HalftoneDot[] = [];
  const width = field.cols * cellX;
  const height = field.rows * cellY;
  for (let dy = 0; dy < height; dy += pitch) {
    const stagger = Math.round(dy / pitch) % 2 === 0 ? 0 : pitch / 2;
    for (let dx = stagger; dx < width; dx += pitch) {
      const density = sampleField(field, dx / cellX - 0.5, dy / cellY - 0.5);
      if (density > densityFloor) dots.push({ dx, dy, density });
    }
  }
  return dots;
}

function dotSize(density: number, pitch: number): number {
  return Math.max(0.9, pitch * (0.22 + density * 0.6));
}

function crocodileDots(index: number, grid: GridMetrics): RenderedPoint[] {
  const baseline = (animationGrid.rows - 1) * grid.cellY;
  return halftone(crocodileField(index), grid.cellX, grid.cellY, grid.pitch).map((dot) => ({
    x: grid.originX + dot.dx,
    y: baseline - dot.dy,
    size: dotSize(dot.density, grid.pitch),
    alpha: 0.22 + dot.density * 0.5,
    channel: 'crocodile',
  }));
}

function flightProgress(seconds: number): number {
  if (seconds < peckStart) return Math.max(0, Math.min(1, (seconds - 2.3) / 2.5));
  if (seconds >= peckEnd) return Math.max(0, Math.min(1, (26.3 - seconds) / 1.5));
  return 1;
}

function bezier(start: Point2D, first: Point2D, second: Point2D, end: Point2D, t: number): Point2D {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return {
    x: a * start.x + b * first.x + c * second.x + d * end.x,
    y: a * start.y + b * first.y + c * second.y + d * end.y,
  };
}

function birdTransform(grid: GridMetrics, field: DensityField, seconds: number, height: number): BirdTransform {
  const progress = flightProgress(seconds);
  const eased = progress * progress * (3 - 2 * progress);
  const birdWidth = field.cols * grid.cellX;
  const birdHeight = field.rows * grid.cellY;
  const mouth = { x: grid.originX + mouthCol * grid.cellX, y: (animationGrid.rows - mouthRow) * grid.cellY };
  const start = { x: -birdWidth - 48, y: height + birdHeight + 48 };
  const first = { x: mouth.x * 0.3, y: height * 0.8 };
  const second = { x: mouth.x * 0.85, y: mouth.y + height * 0.3 };
  return { ...bezier(start, first, second, mouth, eased), mirrored: seconds >= peckEnd };
}

function placeBird(dots: HalftoneDot[], field: DensityField, grid: GridMetrics, transform: BirdTransform): RenderedPoint[] {
  const width = field.cols * grid.cellX;
  return dots.map((dot) => ({
    x: transform.x + (transform.mirrored ? width - dot.dx : dot.dx),
    y: transform.y - dot.dy,
    size: dotSize(dot.density, grid.pitch * birdPitchRatio),
    alpha: 0.8 + dot.density * 0.2,
    channel: 'bird',
  }));
}

function palette(): DotPalette {
  const style = getComputedStyle(document.documentElement);
  return {
    crocodile: style.getPropertyValue('--muted').trim(),
    bird: style.getPropertyValue('--accent').trim(),
  };
}

interface DotLayers {
  crocodile: DotLayer;
  bird: DotLayer;
}

function createScene(layers: DotLayers, container: HTMLElement): { render(seconds: number): void; resize(): void } {
  let grid = metrics(1, 1);
  let lastIndex = -1;
  let crocodile: RenderedPoint[] = [];
  const birdCache = new Map<DensityField, HalftoneDot[]>();

  function render(seconds: number): void {
    const index = crocodileFrameIndex(seconds);
    if (index !== lastIndex) {
      crocodile = crocodileDots(index, grid);
      lastIndex = index;
      layers.crocodile.update(crocodile);
    }
    const field = birdField(seconds);
    if (!field || field.cols === 0) {
      layers.bird.update([]);
      return;
    }
    const dots = birdCache.get(field) ?? halftone(field, grid.cellX, grid.cellY, grid.pitch * birdPitchRatio);
    birdCache.set(field, dots);
    const transform = birdTransform(grid, field, seconds, container.clientHeight);
    layers.bird.update(placeBird(dots, field, grid, transform));
  }

  function resize(): void {
    grid = metrics(container.clientWidth, container.clientHeight);
    layers.crocodile.resize(container.clientWidth, container.clientHeight);
    layers.bird.resize(container.clientWidth, container.clientHeight);
    lastIndex = -1;
    birdCache.clear();
  }

  return { render, resize };
}

function applyPalette(layers: DotLayers): void {
  const colors = palette();
  layers.crocodile.setPalette(colors);
  layers.bird.setPalette(colors);
}

export function startDotMatrix(background: HTMLElement, flight: HTMLElement): void {
  const crocodileCanvas = background.querySelector<HTMLCanvasElement>('[data-layer="crocodile"]');
  const birdCanvas = flight.querySelector<HTMLCanvasElement>('[data-layer="bird"]');
  if (!crocodileCanvas || !birdCanvas) return;
  try {
    const layers = { crocodile: new DotLayer(crocodileCanvas), bird: new DotLayer(birdCanvas) };
    const scene = createScene(layers, background);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let time = 0;
    let previousStamp = performance.now();
    const themeObserver = new MutationObserver(() => {
      applyPalette(layers);
      scene.resize();
      scene.render(time);
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    applyPalette(layers);
    window.addEventListener('resize', () => {
      scene.resize();
      scene.render(time);
    });
    window.setInterval(() => {
      const now = performance.now();
      const elapsed = (now - previousStamp) / 1000;
      previousStamp = now;
      if (document.hidden || reducedMotion) return;
      time = (time + elapsed) % animationGrid.duration;
      scene.render(time);
    }, 1000 / 30);
    scene.resize();
    scene.render(time);
  } catch {
    background.dataset.unavailable = 'true';
    flight.dataset.unavailable = 'true';
  }
}
