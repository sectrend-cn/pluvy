import type { Language } from '../../i18n.ts';

export interface DemoCodeLine {
  text: string;
  signal: 'none' | 'finding';
}

interface CaseCopy {
  tab: string;
  description: string;
  advice: readonly string[];
}

interface CaseBase {
  finding: string;
  file: string;
  source: readonly DemoCodeLine[];
  copy: Record<Language, CaseCopy>;
}

interface ScanSnapshot {
  date: string;
  version: string;
}

interface ResolvedCase extends CaseBase {
  kind: 'resolved';
  after: readonly DemoCodeLine[];
  commit: string;
  fixedOn: string;
}

interface OptionalFieldsCase extends CaseBase {
  kind: 'optional-fields';
  count: number;
  limit: number;
  snapshot: ScanSnapshot;
}

interface GuardedProjectionsCase extends CaseBase {
  kind: 'guarded-projections';
  count: number;
  snapshot: ScanSnapshot;
}

export type OptimizationCase = ResolvedCase | OptionalFieldsCase | GuardedProjectionsCase;

const snapshot: ScanSnapshot = { date: '2026-11-09', version: '0.0.2' };

export const optimizationCases: readonly OptimizationCase[] = [
  {
    kind: 'resolved',
    finding: 'type.broad',
    file: 'src/analysis/observation/agent-trace.ts',
    commit: 'acfa790',
    fixedOn: '2026-10-12',
    copy: {
      en: {
        tab: 'Narrowing',
        description: 'Two helpers repeat field checks. The recorded refactor replaces them with one schema.',
        advice: ['Two handwritten guards removed', 'One schema declares the shape'],
      },
      'zh-CN': {
        tab: '类型判断',
        description: '两个辅助函数重复检查字段。真实重构用一份 Schema 集中声明结构。',
        advice: ['删除两个手写判断函数', '用一份 Schema 声明结构'],
      },
    },
    source: [
      { text: 'const parsed: unknown = JSON.parse(row.toolResultsJson ?? "null");', signal: 'none' },
      { text: 'if (!Array.isArray(parsed) || parsed.length === 0) return null;', signal: 'finding' },
      { text: 'const first: unknown = parsed[0];', signal: 'none' },
      { text: 'function toolResultCallId(value: unknown): string | undefined {', signal: 'none' },
      { text: '  if (value === null || typeof value !== "object" || !("callId" in value)) return undefined;', signal: 'finding' },
      { text: '  return typeof value.callId === "string" ? value.callId : undefined;', signal: 'finding' },
      { text: '}', signal: 'none' },
      { text: 'function toolResultContent(value: unknown): string {', signal: 'none' },
      { text: '  if (value === null || typeof value !== "object" || !("content" in value)) return "";', signal: 'finding' },
      { text: '  return typeof value.content === "string" ? value.content : "";', signal: 'finding' },
      { text: '}', signal: 'none' },
    ],
    after: [
      { text: 'const traceItem = z.object({', signal: 'none' },
      { text: '  callId: z.string().nullish().catch(null),', signal: 'none' },
      { text: '  content: z.string().nullish().catch(null),', signal: 'none' },
      { text: '});', signal: 'none' },
      { text: 'const traceResultsParser = new NullableJsonParser(', signal: 'none' },
      { text: '  new ZodJsonParser(z.array(traceItem))', signal: 'none' },
      { text: ');', signal: 'none' },
      { text: 'const first = traceResultsParser', signal: 'none' },
      { text: '  .parse(row.toolResultsJson ?? "null")?.[0] ?? null;', signal: 'none' },
    ],
  },
  {
    kind: 'optional-fields',
    finding: 'type.nullable',
    file: 'src/analysis/cli/arguments.ts:17',
    count: 6,
    limit: 3,
    snapshot,
    copy: {
      en: {
        tab: 'Optional fields',
        description: 'The optional-field count exceeds this repository’s limit. Consumers may need more null checks.',
        advice: ['Keep required capabilities required', 'Split genuinely different shapes'],
      },
      'zh-CN': {
        tab: '可选字段',
        description: '可选字段数量超过仓库策略上限，可能增加调用方的判空负担。',
        advice: ['必需能力恢复为必填', '不同形态拆成具体类型'],
      },
    },
    source: [
      { text: 'export interface CliDependencies {', signal: 'none' },
      { text: '  createRuntime: (route: ModelRouteInput) => ModelRuntime;', signal: 'none' },
      { text: '  resolveProfile?: (route: ModelRouteInput) => Promise<string>;', signal: 'finding' },
      { text: '  stdout?: (line: string) => void;', signal: 'finding' },
      { text: '  stderr?: (line: string) => void;', signal: 'finding' },
      { text: '  // … 6 optional or nullable properties in total', signal: 'none' },
      { text: '}', signal: 'none' },
    ],
  },
  {
    kind: 'guarded-projections',
    finding: 'structure.guarded_projection',
    file: 'src/analysis/submission.ts:64',
    count: 7,
    snapshot,
    copy: {
      en: {
        tab: 'Projections',
        description: 'The scan records seven guarded field copies. Review their ownership and concrete field associations.',
        advice: ['Declare concrete field associations', 'Preserve omitted fields and evaluation order'],
      },
      'zh-CN': {
        tab: '守卫投影',
        description: '扫描记录了 7 次守卫式字段拷贝，需要检查映射的归属与具体字段关联。',
        advice: ['集中声明具体字段关联', '保留缺省行为与求值顺序'],
      },
    },
    source: [
      { text: 'if (node.minItems != null) schema.minItems = node.minItems;', signal: 'finding' },
      { text: 'if (node.maxItems != null) schema.maxItems = node.maxItems;', signal: 'finding' },
      { text: 'if (node.minimum != null) schema.minimum = node.minimum;', signal: 'finding' },
      { text: 'if (node.maximum != null) schema.maximum = node.maximum;', signal: 'finding' },
      { text: '// … the same guard + copy pattern repeated 3 more times', signal: 'none' },
    ],
  },
];
