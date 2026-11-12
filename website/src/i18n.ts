export type Language = 'en' | 'zh-CN';

const englishLanding = {
  hero: {
    lead: 'Agent-written code,',
    emphasis: 'checked by Pluvy.',
    description: 'Agents can make a task look done by loosening types, suppressing diagnostics or deleting tests. Pluvy checks each change against your committed policy and reports findings with an exit code.',
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
      { number: '01', title: 'Ineffective tests', before: 'Assertions that restate a literal, tests with nothing to assert, deleted test files and quietly dropped assertions.', code: '', after: '' },
      { number: '02', title: 'Contracts erased in silence', before: '', code: 'Any', after: ', casts and unchecked assertions, exceptions caught and swallowed, missing data hidden behind literal defaults.' },
      { number: '03', title: 'Architecture that drifts', before: 'Forbidden dependency directions, misplaced modules and files without an owner, all declared in ', code: '.pluvy/pluvy.json', after: ' and reviewed like code.' },
    ],
  },
  workflow: {
    titleA: 'Hold new changes to the policy.',
    titleB: 'Clear old debt on your schedule.',
    scopes: [
      { flag: '--base <commit>', use: 'Only what the change touches, so existing debt never blocks new work.' },
      { flag: '--all', use: 'The full reading of every selected file.' },
      { flag: '--staged', use: 'The index, before you commit.' },
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
      description: 'Agent 可能放宽类型、压掉诊断或删掉测试，让任务看起来已经完成。Pluvy 按仓库中提交的策略检查每次改动，报告检查结果和退出码。',
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
        { number: '02', title: '被悄悄擦掉的契约', before: '', code: 'Any', after: '、类型转换与未经检查的断言，被捕获后吞掉的异常，用字面量默认值掩盖的缺失数据。' },
        { number: '03', title: '逐渐走样的架构', before: '违反依赖方向、放错位置的模块和没有归属的文件。这些规则都声明在 ', code: '.pluvy/pluvy.json', after: ' 中，像代码一样评审。' },
      ],
    },
    workflow: {
      titleA: '新改动按策略把关，',
      titleB: '存量问题按节奏清理。',
      scopes: [
        { flag: '--base <commit>', use: '只检查改动涉及的部分，存量问题不阻塞新工作。' },
        { flag: '--all', use: '对所有选中文件的全量读数。' },
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

export function docsPath(lang: Language): string {
  return lang === 'zh-CN' ? 'zh/docs' : 'docs';
}

export function basePath(): string {
  const base = import.meta.env.BASE_URL;
  return base.endsWith('/') ? base : `${base}/`;
}
