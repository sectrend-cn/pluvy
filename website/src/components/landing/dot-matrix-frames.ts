import { animationData } from './crocodile-frames.ts';

export interface DensityField {
  cols: number;
  rows: number;
  values: Float32Array;
}

interface BirdPose {
  kind: 'flying' | 'perched';
  index: number;
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

function intensity(character: string): number {
  return (rank.get(character) ?? 0) / (ramp.length - 1);
}

export function crocodileField(index: number): DensityField {
  const frame = frames[index];
  const values = new Float32Array(frame.length);
  for (let offset = 0; offset < frame.length; offset++) values[offset] = intensity(frame[offset]);
  return { cols: animationData.cols, rows: animationData.rows, values };
}

function extractRegion(
  index: number,
  baselineIndex: number,
  top: number,
  bottom: number,
  left: number,
  right: number,
): DensityField {
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
  if (maxRow < 0) return { cols: 0, rows: 0, values: new Float32Array(0) };
  const cols = maxCol - minCol + 1;
  const rows = maxRow - minRow + 1;
  const values = new Float32Array(cols * rows);
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const offset = (minRow + row) * animationData.cols + minCol + col;
      if (source[offset] !== baseline[offset]) values[row * cols + col] = intensity(source[offset]);
    }
  }
  return { cols, rows, values };
}

function birdPose(seconds: number): BirdPose | null {
  if (seconds < 2.3 || seconds >= 26.3) return null;
  if (seconds >= 4.8 && seconds < 24.8) {
    const frameCount = Math.floor(1.5 * animationData.fps);
    const index = Math.floor(4.8 * animationData.fps) + Math.floor((seconds - 4.8) * 10) % frameCount;
    return { kind: 'perched', index };
  }
  if (seconds < 4.8) return { kind: 'flying', index: Math.min(frameIndex(seconds), perchedReferenceIndex) };
  const wingFrames = [Math.floor(3.5 * animationData.fps), Math.floor(3.9 * animationData.fps)];
  return { kind: 'flying', index: wingFrames[Math.floor((seconds - 24.8) * 8) % wingFrames.length] };
}

function poseField(pose: BirdPose): DensityField {
  return pose.kind === 'perched'
    ? extractRegion(pose.index, perchedReferenceIndex, 47, 54, 56, 92)
    : extractRegion(pose.index, birdReferenceIndex, 0, animationData.rows - 1, 0, animationData.cols - 1);
}

const birdFields = new Map<string, DensityField>();

export function birdField(seconds: number): DensityField | null {
  const pose = birdPose(seconds);
  if (!pose) return null;
  const key = `${pose.kind}:${pose.index}`;
  const cached = birdFields.get(key);
  if (cached) return cached;
  const field = poseField(pose);
  birdFields.set(key, field);
  return field;
}

export const animationGrid = {
  cols: animationData.cols,
  rows: animationData.rows,
  fps: animationData.fps,
  duration: animationData.duration,
};
