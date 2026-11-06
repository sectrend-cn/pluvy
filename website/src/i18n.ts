export type Language = 'en' | 'zh-CN';

const englishLanding = {
  hero: {
    lead: 'Agent-written code,',
    emphasis: 'checked by a gate.',
    description: 'Agents can make a task look done by loosening types, suppressing diagnostics or deleting tests. Pluvy checks each change against your committed policy and reports findings with an exit code.',
    getStarted: 'Get started',
    viewGithub: 'View on GitHub',
    copy: 'Copy',
    copied: 'Copied',
  },
  principles: {
    titleA: 'A gate,',
    titleB: 'not an editor.',
    items: [
      { number: '01', title: 'Read-only analysis', before: 'The gate never modifies source files or Git state, so a passing result cannot come from the gate changing the code.', code: '', after: '' },
      { number: '02', title: 'Policy in your repository', before: 'Your team commits the checks in ', code: '.pluvy/pluvy.json', after: '. Changing them is a reviewed decision, not a fix.' },
      { number: '03', title: 'More than formatting', before: 'Types, suppressions, deleted tests, architecture, ownership, unused code and function size in Python, Go, Java, JavaScript and TypeScript.', code: '', after: '' },
    ],
  },
  workflow: {
    titleA: 'One policy.',
    titleB: 'Three audit scopes.',
    scopes: [
      '--all',
      '--base <commit>',
      '--staged',
    ],
    guide: 'Read the run guide',
    policy: 'POLICY',
    run: 'RUN',
    exitCodes: 'Exit codes',
    items: [
      { code: '0', description: 'Pass, or warnings only' },
      { code: '1', description: 'Error findings' },
      { code: '2', description: 'Configuration, encoding, filesystem or Git failure' },
    ],
  },
  final: {
    titleA: 'Put a gate after',
    titleB: 'every agent task.',
    connectAgent: 'Connect your agent',
    explore: 'Explore the example policy',
  },
};

export type LandingContent = typeof englishLanding;

export const landingContent: Record<Language, LandingContent> = {
  en: englishLanding,
  'zh-CN': {
    hero: {
      lead: 'Agent 写的代码，',
      emphasis: '交给门禁检查。',
      description: 'Agent 可能放宽类型、压掉诊断或删掉测试，让任务看起来已经完成。Pluvy 按仓库中提交的策略检查每次改动，报告检查结果和退出码。',
      getStarted: '开始使用',
      viewGithub: '查看 GitHub',
      copy: '复制',
      copied: '已复制',
    },
    principles: {
      titleA: '是门禁，',
      titleB: '不是编辑器。',
      items: [
        { number: '01', title: '只读分析', before: '门禁不修改源文件，也不修改 Git 状态。通过的结果不可能来自门禁改动代码。', code: '', after: '' },
        { number: '02', title: '策略由仓库管理', before: '检查规则由团队提交在 ', code: '.pluvy/pluvy.json', after: ' 中。修改规则需要单独评审，不能当作修复。' },
        { number: '03', title: '不止格式检查', before: '覆盖 Python、Go、Java、JavaScript 和 TypeScript 中的类型、诊断抑制、测试删除、架构、职责归属、未使用代码和函数规模。', code: '', after: '' },
      ],
    },
    workflow: {
      titleA: '一套策略。',
      titleB: '三种审计范围。',
      scopes: [
        '--all',
        '--base <commit>',
        '--staged',
      ],
      guide: '查看运行指南',
      policy: '策略',
      run: '运行',
      exitCodes: '退出码',
      items: [
        { code: '0', description: '通过，或只有警告' },
        { code: '1', description: '存在错误级检查结果' },
        { code: '2', description: '配置、编码、文件系统或 Git 故障' },
      ],
    },
    final: {
      titleA: '在每个 Agent 任务后',
      titleB: '设一道门禁。',
      connectAgent: '接入你的 Agent',
      explore: '查看策略示例',
    },
  },
};

const englishHeader = {
  docs: 'Docs',
  documentation: 'Documentation',
  blog: 'Blog',
  releases: 'Releases',
  navigation: 'Main navigation',
  skip: 'Skip to content',
  theme: 'Switch to dark theme',
};

export const headerContent: Record<Language, typeof englishHeader> = {
  en: englishHeader,
  'zh-CN': {
    docs: '文档',
    documentation: '文档',
    blog: '博客',
    releases: '版本发布',
    navigation: '主导航',
    skip: '跳到主要内容',
    theme: '切换到深色模式',
  },
};

export function docsPath(lang: Language): string {
  return lang === 'zh-CN' ? 'zh/docs' : 'docs';
}
