import { animationData } from './crocodile-frames.ts';

export interface GridPoint {
  col: number;
  row: number;
  rank: number;
}

interface BirdSprite {
  index: number;
  text: string;
}

interface GlyphImage {
  pixels: Uint8ClampedArray;
  width: number;
}

const ramp = ' .:-=+*#%@';
const rank = new Map(Array.from(ramp, (character, index) => [character, index]));
const clearFrameIndex = Math.floor(2 * animationData.fps);
const birdReferenceIndex = Math.floor(9 * animationData.fps);
const perchedReferenceIndex = Math.floor(4.2 * animationData.fps);

function decodeFrames(): string[] {
  const buffer = Array.from(animationData.first.replace(/\n/g, ''));
  const frames: string[] = [];
  for (const delta of animationData.deltas) {
    for (const [offset, text] of delta) {
      for (let index = 0; index < text.length; index++) buffer[offset + index] = text[index];
    }
    frames.push(buffer.join(''));
  }
  return frames;
}

const frames = decodeFrames();

export function frameIndex(seconds: number): number {
  return Math.min(frames.length - 1, Math.max(0, Math.floor(seconds * animationData.fps + 1e-7)));
}

export function crocodileFrameIndex(seconds: number): number {
  if (seconds >= 2.3 && seconds < 24.8) return clearFrameIndex;
  if (seconds < 24.8) return frameIndex(seconds);
  const progress = Math.min(1, (seconds - 24.8) / 1.9);
  const eased = progress * progress * (3 - 2 * progress);
  const closingStart = Math.floor(9.3 * animationData.fps);
  const closed = Math.floor(10.7 * animationData.fps);
  return Math.round(closingStart + (closed - closingStart) * eased);
}

export function framePoints(index: number): GridPoint[] {
  const frame = frames[index];
  const points: GridPoint[] = [];
  for (let offset = 0; offset < frame.length; offset++) {
    const intensity = rank.get(frame[offset]) ?? 0;
    if (intensity === 0) continue;
    points.push({
      col: offset % animationData.cols,
      row: Math.floor(offset / animationData.cols),
      rank: intensity,
    });
  }
  return points;
}

function extractRegion(
  index: number,
  baselineIndex: number,
  top: number,
  bottom: number,
  left: number,
  right: number,
): BirdSprite {
  const source = frames[index];
  const baseline = frames[baselineIndex];
  let minRow = bottom;
  let maxRow = -1;
  let minCol = right;
  let maxCol = -1;
  for (let row = top; row <= bottom; row++) {
    for (let col = left; col <= right; col++) {
      const offset = row * animationData.cols + col;
      if (source[offset] === baseline[offset]) continue;
      minRow = Math.min(minRow, row);
      maxRow = Math.max(maxRow, row);
      minCol = Math.min(minCol, col);
      maxCol = Math.max(maxCol, col);
    }
  }
  if (maxRow < 0) return { index, text: '' };
  const lines: string[] = [];
  for (let row = minRow; row <= maxRow; row++) {
    let line = '';
    for (let col = minCol; col <= maxCol; col++) {
      const offset = row * animationData.cols + col;
      line += source[offset] === baseline[offset] ? ' ' : source[offset];
    }
    lines.push(line.trimEnd());
  }
  return { index, text: lines.join('\n').trimEnd() };
}

function perchedSprite(index: number): BirdSprite {
  return extractRegion(index, perchedReferenceIndex, 47, 54, 56, 92);
}

function flyingSprite(index: number): BirdSprite {
  return extractRegion(index, birdReferenceIndex, 0, animationData.rows - 1, 0, animationData.cols - 1);
}

function birdSprite(seconds: number): BirdSprite | null {
  if (seconds < 2.3 || seconds >= 26.3) return null;
  if (seconds >= 4.8 && seconds < 24.8) {
    const frameCount = Math.floor(1.5 * animationData.fps);
    const pose = Math.floor(4.8 * animationData.fps)
      + Math.floor((seconds - 4.8) * 10) % frameCount;
    return perchedSprite(pose);
  }
  if (seconds < 4.8) return flyingSprite(Math.min(frameIndex(seconds), perchedReferenceIndex));
  const wingFrames = [Math.floor(3.5 * animationData.fps), Math.floor(3.9 * animationData.fps)];
  return flyingSprite(wingFrames[Math.floor((seconds - 24.8) * 8) % wingFrames.length]);
}

function glyphImage(text: string): GlyphImage | null {
  const lines = text.split('\n');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context) return null;
  context.font = '16px "Courier New", Courier, monospace';
  const cellWidth = context.measureText('M').width;
  const cellHeight = 16;
  canvas.width = Math.ceil(Math.max(...lines.map((line) => line.length)) * cellWidth);
  canvas.height = lines.length * cellHeight;
  context.font = '16px "Courier New", Courier, monospace';
  context.fillStyle = '#000';
  context.textBaseline = 'top';
  lines.forEach((line, row) => context.fillText(line, 0, row * cellHeight));
  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  return { pixels: image.data, width: canvas.width };
}

function rasterizeBird(sprite: BirdSprite): GridPoint[] {
  if (!sprite.text) return [];
  const image = glyphImage(sprite.text);
  if (!image) return [];
  const lines = sprite.text.split('\n');
  const cellWidth = image.width / Math.max(...lines.map((line) => line.length));
  const points: GridPoint[] = [];
  for (let row = 0; row < lines.length; row++) {
    for (let col = 0; col < lines[row].length; col++) {
      if (lines[row][col] === ' ') continue;
      for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 3; x++) {
          const pixelX = Math.min(image.width - 1, Math.floor((col + (x + 0.5) / 3) * cellWidth));
          const pixelY = Math.floor((row + (y + 0.5) / 4) * 16);
          const alpha = image.pixels[(pixelY * image.width + pixelX) * 4 + 3];
          if (alpha > 40) points.push({ col: col + x / 3, row: row + y / 4, rank: Math.max(1, Math.round(alpha / 255 * 9)) });
        }
      }
    }
  }
  return points;
}

const birdCache = new Map<number, GridPoint[]>();

export function birdPoints(seconds: number): GridPoint[] {
  const sprite = birdSprite(seconds);
  if (!sprite) return [];
  if (!birdCache.has(sprite.index)) birdCache.set(sprite.index, rasterizeBird(sprite));
  return birdCache.get(sprite.index) ?? [];
}

export const animationGrid = {
  cols: animationData.cols,
  rows: animationData.rows,
  fps: animationData.fps,
  duration: animationData.duration,
};
