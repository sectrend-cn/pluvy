const scanDuration = 3.2;

export class ScanPlayback {
  private frame = 0;

  constructor(
    private readonly panel: HTMLElement,
    private readonly comparison: HTMLElement,
    private readonly range: HTMLInputElement,
    private readonly reducedMotion: MediaQueryList,
  ) {
    range.addEventListener('pointerdown', () => this.stop());
    range.addEventListener('keydown', () => this.stop());
    range.addEventListener('input', () => {
      this.stop();
      this.setPosition(range.valueAsNumber);
    });
    range.addEventListener('change', () => this.complete());
    reducedMotion.addEventListener('change', () => {
      if (reducedMotion.matches && !panel.hidden) {
        this.setPosition(0);
        this.complete();
      }
    });
  }

  play(): void {
    this.stop();
    if (this.reducedMotion.matches) {
      this.setPosition(0);
      this.complete();
      return;
    }
    this.panel.dataset.scanState = 'scanning';
    this.setPosition(100);
    const start = performance.now();
    const advance = (now: number): void => {
      const seconds = (now - start) / 1000;
      const progress = Math.min(seconds / scanDuration, 1);
      const easedProgress = progress * progress * (3 - 2 * progress);
      this.setPosition(100 * (1 - easedProgress));
      if (progress < 1) {
        this.frame = requestAnimationFrame(advance);
      } else {
        this.setPosition(0);
        this.complete();
      }
    };
    this.frame = requestAnimationFrame(advance);
  }

  stop(): void {
    cancelAnimationFrame(this.frame);
    this.panel.dataset.scanState = 'manual';
  }

  private complete(): void {
    cancelAnimationFrame(this.frame);
    this.panel.dataset.scanState = 'complete';
  }

  private setPosition(position: number): void {
    this.range.value = String(position);
    this.comparison.style.setProperty('--code-position', `${position}%`);
  }
}
