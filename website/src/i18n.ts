export type Language = 'en' | 'zh-CN';

const englishLanding = {
  hero: {
    lead: 'Agent-written code,',
    emphasis: 'checked by Pluvy.',
    description: 'Agents can make a task look done by loosening types, suppressing diagnostics, or deleting tests. Pluvy checks every change in Python, Go, Java, JavaScript, and TypeScript against your committed policy—blocking shortcuts before commit or merge.',
    getStarted: 'Get started',
    viewGithub: 'View on GitHub',
    install: 'Install with uv',
    copy: 'Copy',
    copied: 'Copied',
  },
  principles: {
    titleA: 'Shortcuts that pass CI',
    titleB: 'without doing the work.',
    items: [
      { number: '01', title: 'Ineffective tests', before: 'Assertions that restate a literal, tests with nothing to assert, deleted test files, and quietly dropped assertions.', code: '', after: '' },
      { number: '02', title: 'Contracts erased in silence', before: 'Broad markers like ', code: 'Any', after: ', unchecked casts, swallowed exceptions, and missing data hidden behind literal defaults.' },
      { number: '03', title: 'Architecture that drifts', before: 'Forbidden imports, misplaced modules, and unowned files—checked against owners and boundaries declared in ', code: '.pluvy/pluvy.json', after: ' and reviewed like code.' },
    ],
  },
  workflow: {
    titleA: 'Hold new changes to the policy.',
    titleB: 'Clear old debt on your schedule.',
    scopes: [
      { flag: '--base <commit>', use: 'Only what the change touches, so existing debt never blocks new work.' },
      { flag: '--all', use: 'Every selected file, including existing debt.' },
      { flag: '--staged', use: 'Staged changes, before you commit.' },
    ],
    trust: 'Safe in CI, hooks and agent sessions: Pluvy reports findings and never edits your code.',
    guide: 'Read the run guide',
    policy: 'POLICY',
    run: 'RUN',
  },
  final: {
    titleA: 'Put a gate after',
    titleB: 'every agent task.',
    connectAgent: 'Connect your agent',
  },
};

export type LandingContent = typeof englishLanding;

export const landingContent: Record<Language, LandingContent> = {
  en: englishLanding,
  'zh-CN': {
    hero: {
      lead: 'Agent 写的代码，',
      emphasis: '交给 Pluvy 检查。',
      description: 'Agent 可能放宽类型、压制告警或删掉测试，让任务看起来已经完成。Pluvy 按仓库内提交的策略检查 Python、Go、Java、JavaScript 和 TypeScript 改动，在提交或合并前拦下这些捷径。',
      getStarted: '开始使用',
      viewGithub: '查看 GitHub',
      install: '使用 uv 安装',
      copy: '复制',
      copied: '已复制',
    },
    principles: {
      titleA: '能过 CI，',
      titleB: '却没把活干完的捷径。',
      items: [
        { number: '01', title: '无效的测试', before: '断言恒为真、没有断言的测试、被删掉的测试文件，以及悄悄减少的断言。', code: '', after: '' },
        { number: '02', title: '被悄悄擦掉的契约', before: '像 ', code: 'Any', after: ' 这样的宽泛类型、未经校验的断言转换、捕获后吞掉的异常，以及用字面量默认值掩盖的缺失数据。' },
        { number: '03', title: '逐渐走样的架构', before: '违反依赖方向、放错位置的模块和缺少归属的文件——对照 ', code: '.pluvy/pluvy.json', after: ' 中声明的归属与边界检查，并像代码一样评审。' },
      ],
    },
    workflow: {
      titleA: '新改动按策略把关，',
      titleB: '存量问题按节奏清理。',
      scopes: [
        { flag: '--base <commit>', use: '只检查改动涉及的部分，存量问题不阻塞新工作。' },
        { flag: '--all', use: '检查所有选中文件，暴露存量问题。' },
        { flag: '--staged', use: '提交前检查暂存区。' },
      ],
      trust: '可以放心跑在 CI、hook 和 Agent 会话里：Pluvy 只报告问题，从不改动你的代码。',
      guide: '查看运行指南',
      policy: '策略',
      run: '运行',
    },
    final: {
      titleA: '在每个 Agent 任务后',
      titleB: '设一道门禁。',
      connectAgent: '接入你的 Agent',
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

export function basePath(): string {
  const base = import.meta.env.BASE_URL;
  return base.endsWith('/') ? base : `${base}/`;
}
