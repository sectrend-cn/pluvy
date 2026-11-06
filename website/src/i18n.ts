export type Language = 'en' | 'zh-CN';

const englishLanding = {
  hero: {
    standards: 'Engineering standards,',
    enforced: 'enforced',
    withoutRewriting: 'without rewriting',
    code: 'your code.',
    description: 'Read-only engineering checks for Python, Go, Java, JavaScript and TypeScript. Run a full audit or check only changed code.',
    getStarted: 'Get started',
    viewGithub: 'View on GitHub',
  },
  principles: {
    titleA: 'A gate,',
    titleB: 'not an editor.',
    items: [
      { number: '01', title: 'Read-only analysis', description: 'Findings never modify source files or Git state.', code: '' },
      { number: '02', title: 'Policy in your repository', description: 'Configure checks in ', code: '.pluvy/pluvy.json' },
      { number: '03', title: 'More than formatting', description: 'Check types, architecture, ownership, usage and function size.', code: '' },
    ],
  },
  workflow: {
    titleA: 'One policy.',
    titleB: 'Three audit scopes.',
    guide: 'Read the run guide',
    policy: 'POLICY',
    run: 'RUN',
    chooseScope: 'Choose one scope',
    exitCodes: 'Exit code meanings',
    items: [
      { code: '0', description: 'No error findings' },
      { code: '1', description: 'Policy violations' },
      { code: '2', description: 'Cannot conclude' },
    ],
  },
  final: {
    titleA: 'Make your engineering',
    titleB: 'policy executable.',
    readGuide: 'Read the guide',
    explore: 'Explore the example policy',
  },
};

export type LandingContent = typeof englishLanding;

export const landingContent: Record<Language, LandingContent> = {
  en: englishLanding,
  'zh-CN': {
    hero: {
      standards: '工程规范，',
      enforced: '无需修改',
      withoutRewriting: '现有代码',
      code: '即可执行。',
      description: '面向 Python、Go、Java、JavaScript 和 TypeScript 的只读工程检查。支持全量审计，也可仅检查变更代码。',
      getStarted: '开始使用',
      viewGithub: '查看 GitHub',
    },
    principles: {
      titleA: '是门禁，',
      titleB: '不是编辑器。',
      items: [
        { number: '01', title: '只读分析', description: '检查结果不会修改源文件或 Git 状态。', code: '' },
        { number: '02', title: '策略由仓库管理', description: '配置检查规则：', code: '.pluvy/pluvy.json' },
        { number: '03', title: '不止格式检查', description: '检查类型、架构、职责归属、使用情况和函数规模。', code: '' },
      ],
    },
    workflow: {
      titleA: '一套策略。',
      titleB: '三种审计范围。',
      guide: '查看运行指南',
      policy: '策略',
      run: '运行',
      chooseScope: '选择一种范围',
      exitCodes: '退出码含义',
      items: [
        { code: '0', description: '无错误项' },
        { code: '1', description: '存在策略违规' },
        { code: '2', description: '无法得出结论' },
      ],
    },
    final: {
      titleA: '让工程规范',
      titleB: '真正可执行。',
      readGuide: '阅读指南',
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
