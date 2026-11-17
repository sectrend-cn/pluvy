import type { Language } from '../../i18n.ts';

export type DemoCodeLine =
  | { readonly text: string; readonly signal: 'none' }
  | { readonly text: string; readonly signal: 'finding'; readonly note: Record<Language, string> };

interface CaseCopy {
  readonly tab: string;
  readonly description: string;
  readonly advice: readonly [string, string];
}

interface CaseBase {
  readonly finding: string;
  readonly file: string;
  readonly source: readonly DemoCodeLine[];
  readonly copy: Record<Language, CaseCopy>;
}

export interface ResolvedCase extends CaseBase {
  readonly kind: 'resolved';
  readonly after: readonly DemoCodeLine[];
}

export interface DiagnosticCase extends CaseBase {
  readonly kind: 'test-integrity' | 'boundary-drift';
  readonly findingsCount: number;
}

export type OptimizationCase = ResolvedCase | DiagnosticCase;

export const optimizationCases: readonly OptimizationCase[] = [
  {
    kind: 'resolved',
    finding: 'type.broad · flow.swallow · type.suppression',
    file: 'src/orders.ts',
    copy: {
      en: {
        tab: 'Erased contracts',
        description: 'An agent silences a failing check with @ts-ignore, any, and a swallowed catch. Restoring the contract clears all 3 findings.',
        advice: ['Remove suppression and broad any', 'Throw or handle a specific failure'],
      },
      'zh-CN': {
        tab: '擦除契约',
        description: 'Agent 用 @ts-ignore、any 和吞异常让检查变绿；恢复具体契约即可一次消除 3 处违规。',
        advice: ['移除抑制注释与宽泛 any', '显式抛出或处理具体异常'],
      },
    },
    source: [
      { text: '// @ts-ignore -- unblock build', signal: 'finding', note: { en: '// type.suppression: foreign directive', 'zh-CN': '// type.suppression：禁止压制诊断' } },
      { text: 'export function parseOrder(raw: any): any {', signal: 'finding', note: { en: '// type.broad: erases contract with any', 'zh-CN': '// type.broad：用 any 擦除契约' } },
      { text: '  try {', signal: 'none' },
      { text: '    const [amount, currency] = raw.split(" ");', signal: 'none' },
      { text: '    return { total: Number(amount), currency };', signal: 'none' },
      { text: '  } catch (error) {', signal: 'finding', note: { en: '// flow.swallow: swallows failure', 'zh-CN': '// flow.swallow：捕获后吞掉异常' } },
      { text: '    return null;', signal: 'none' },
      { text: '  }', signal: 'none' },
      { text: '}', signal: 'none' },
    ],
    after: [
      { text: 'export interface Order {', signal: 'none' },
      { text: '  readonly total: number;', signal: 'none' },
      { text: '  readonly currency: string;', signal: 'none' },
      { text: '}', signal: 'none' },
      { text: 'export function parseOrder(raw: string): Order {', signal: 'none' },
      { text: '  const [amount, currency] = raw.trim().split(/\\s+/);', signal: 'none' },
      { text: '  if (!amount || !currency) throw new SyntaxError("Invalid order");', signal: 'none' },
      { text: '  return { total: Number(amount), currency };', signal: 'none' },
      { text: '}', signal: 'none' },
    ],
  },
  {
    kind: 'test-integrity',
    finding: 'test.vacuous · test.tautology',
    file: 'tests/orders.test.ts',
    findingsCount: 2,
    copy: {
      en: {
        tab: 'Fake tests',
        description: 'The test suite stays green, yet neither assertion can catch a wrong total or currency.',
        advice: ['Replace toBeDefined() with concrete field checks', 'Compare against an independent expected value'],
      },
      'zh-CN': {
        tab: '无效测试',
        description: '测试套件依然全绿，但这 2 条断言既验不出金额错误，也验不出币种错误。',
        advice: ['把 toBeDefined() 换成具体结果断言', '对照独立的预期值而非自身属性'],
      },
    },
    source: [
      { text: 'test("parses order total", () => {', signal: 'none' },
      { text: '  const order = parseOrder("12.50 EUR");', signal: 'none' },
      { text: '  expect(order).toBeDefined();', signal: 'finding', note: { en: '// test.vacuous: checks no behavior', 'zh-CN': '// test.vacuous：未验证具体行为' } },
      { text: '  expect(order.currency).toBe(order.currency);', signal: 'finding', note: { en: '// test.tautology: mirrors itself', 'zh-CN': '// test.tautology：自身对比恒为真' } },
      { text: '});', signal: 'none' },
    ],
  },
  {
    kind: 'boundary-drift',
    finding: 'architecture.import · type.assertion',
    file: 'src/domain/checkout.ts',
    findingsCount: 2,
    copy: {
      en: {
        tab: 'Boundary drift',
        description: 'Domain code imports a payment adapter directly and forces the currency contract with an unchecked cast.',
        advice: ['Keep adapter imports outside src/domain/*', 'Validate currency at ingress instead of casting'],
      },
      'zh-CN': {
        tab: '架构越界',
        description: '领域层直接引入支付适配器，并用未经校验的 as 断言强转币种类型。',
        advice: ['禁止 src/domain/* 直接依赖适配器层', '在输入边界校验币种而非强转类型'],
      },
    },
    source: [
      { text: 'import { chargeCard } from "../adapters/stripe";', signal: 'finding', note: { en: '// architecture.import: forbidden layer', 'zh-CN': '// architecture.import：违反依赖方向' } },
      { text: '', signal: 'none' },
      { text: 'export function settle(amount: number, unit?: string): string {', signal: 'none' },
      { text: '  const currency = unit ?? "USD";', signal: 'none' },
      { text: '  return chargeCard(amount, currency as Currency);', signal: 'finding', note: { en: '// type.assertion: unchecked cast', 'zh-CN': '// type.assertion：未经校验的强转' } },
      { text: '}', signal: 'none' },
    ],
  },
];
