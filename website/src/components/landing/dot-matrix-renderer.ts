import {
  BufferAttribute,
  BufferGeometry,
  Color,
  OrthographicCamera,
  Points,
  Scene,
  ShaderMaterial,
  WebGLRenderer,
} from 'three';

export type DotChannel = 'crocodile' | 'bird';

export interface RenderedPoint {
  x: number;
  y: number;
  size: number;
  alpha: number;
  channel: DotChannel;
}

export type DotPalette = Record<DotChannel, string>;

const vertexShader = `
  attribute float aSize;
  attribute float aAlpha;
  attribute float aBird;
  uniform float uPixelRatio;
  varying float vAlpha;
  varying float vBird;
  void main() {
    vAlpha = aAlpha;
    vBird = aBird;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uPixelRatio;
  }
`;

const fragmentShader = `
  uniform vec3 uCrocodile;
  uniform vec3 uBird;
  varying float vAlpha;
  varying float vBird;
  void main() {
    float distanceToCenter = length(gl_PointCoord - vec2(0.5));
    float coverage = 1.0 - smoothstep(0.35, 0.5, distanceToCenter);
    if (coverage <= 0.0) discard;
    gl_FragColor = vec4(mix(uCrocodile, uBird, vBird), vAlpha * coverage);
    #include <colorspace_fragment>
  }
`;

export class DotLayer {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new OrthographicCamera(0, 1, 1, 0, 0.01, 10);
  private readonly geometry = new BufferGeometry();
  private readonly material: ShaderMaterial;
  private readonly crocodile = new Color('#60655f');
  private readonly bird = new Color('#5c7c2f');

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.camera.position.z = 1;
    this.material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uCrocodile: { value: this.crocodile },
        uBird: { value: this.bird },
        uPixelRatio: { value: this.renderer.getPixelRatio() },
      },
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    const points = new Points(this.geometry, this.material);
    points.frustumCulled = false;
    this.scene.add(points);
  }

  resize(width: number, height: number): void {
    this.renderer.setSize(width, height, false);
    this.camera.right = width;
    this.camera.top = height;
    this.camera.updateProjectionMatrix();
  }

  setPalette(palette: DotPalette): void {
    this.crocodile.set(palette.crocodile);
    this.bird.set(palette.bird);
  }

  update(points: RenderedPoint[]): void {
    const positions = new Float32Array(points.length * 3);
    const sizes = new Float32Array(points.length);
    const alphas = new Float32Array(points.length);
    const birds = new Float32Array(points.length);
    points.forEach((point, index) => {
      positions[index * 3] = point.x;
      positions[index * 3 + 1] = point.y;
      sizes[index] = point.size;
      alphas[index] = point.alpha;
      birds[index] = point.channel === 'bird' ? 1 : 0;
    });
    this.geometry.setAttribute('position', new BufferAttribute(positions, 3));
    this.geometry.setAttribute('aSize', new BufferAttribute(sizes, 1));
    this.geometry.setAttribute('aAlpha', new BufferAttribute(alphas, 1));
    this.geometry.setAttribute('aBird', new BufferAttribute(birds, 1));
    this.geometry.setDrawRange(0, points.length);
    this.renderer.render(this.scene, this.camera);
  }
}
