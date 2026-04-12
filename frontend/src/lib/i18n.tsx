import { createContext, useContext, useState, type ReactNode } from 'react'

export type Locale = 'en' | 'zh'

interface LocaleContextValue {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: string, vars?: Record<string, string | number>) => string
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'en',
  setLocale: () => {},
  t: (k) => k,
})

// ─── Locale data ──────────────────────────────────────────────────────────────

type LocaleData = Record<string, string | Record<string, unknown>>

const en: LocaleData = {
  // TopBar tabs
  tabs: {
    dashboard: 'Dashboard',
    memory: 'Memory',
    skills: 'Skills',
    sessions: 'Sessions',
    cron: 'Cron',
    projects: 'Projects',
    health: 'Health',
    agents: 'Agents',
    chat: 'Chat',
    profiles: 'Profiles',
    'token-costs': 'Costs',
    corrections: 'Corrections',
    patterns: 'Patterns',
  },
  // Common
  loading: 'Loading...',
  noData: 'No data',
  unknown: 'unknown',
  yes: 'Yes',
  no: 'No',
  on: 'on',
  off: 'off',
  local: 'local',
  clean: 'clean',
  dirty: 'dirty',
  active: 'active',
  stopped: 'STOPPED',
  running: 'RUNNING',
  silent: 'silent',
  alive: 'alive',
  free: 'free',
  custom: 'custom',
  default: 'default',
  selfTaught: 'self-taught',
  paused: 'paused',
  scheduled: 'scheduled',
  unknown2: 'unknown',
  noResults: 'No results',

  // Boot screen
  boot: {
    title: '☤ HERMES HUD v0.1.0',
    initConsciousness: 'Initializing consciousness monitor...',
    readStateDb: 'Reading ~/.hermes/state.db',
    scanMemory: 'Scanning memory banks',
    indexSkills: 'Indexing skill library',
    checkHealth: 'Checking service health',
    profileAgents: 'Profiling agent processes',
    quote: '"I think, therefore I process."',
    systemsReady: 'Systems ready.',
    tapToSkip: 'tap to skip',
  },

  // Status bar
  statusBar: {
    liveUpdatesActive: 'Live updates active',
    webSocketConnecting: 'WebSocket: connecting',
    webSocketDisconnected: 'WebSocket: disconnected',
    palette: 'palette',
    tabs: 'tabs',
    theme: 'theme',
    commands: 'commands',
  },

  // Theme picker
  theme: {
    themeLabel: 'Theme',
    scanlines: 'Scanlines',
  },

  // Language switcher
  lang: {
    language: 'Language',
    english: 'EN',
    chinese: '中文',
  },

  // Command palette
  commandPalette: {
    navigateTo: 'Navigate to...',
    typeToFilter: 'type to filter',
    escToClose: 'ESC to close',
    noResults: 'No results for',
  },

  // Dashboard
  dashboard: {
    overview: 'Overview',
    collectingState: 'Collecting state...',
    // Identity block
    designation: 'DESIGNATION',
    substrate: 'SUBSTRATE',
    runtime: 'RUNTIME',
    conscious: 'CONSCIOUS',
    brainSize: 'BRAIN SIZE',
    interfaces: 'INTERFACES',
    purpose: 'PURPOSE',
    since: 'since',
    stateDb: 'state.db',
    learning: 'learning',
    days: 'days',
    // What I Know
    whatIKnow: 'What I Know',
    conversationsHeld: 'conversations held',
    messagesExchanged: 'messages exchanged',
    actionsTaken: 'actions taken',
    skillsAcquired: 'skills acquired',
    tokensProcessed: 'tokens processed',
    via: 'via',
    domains: 'domains',
    // What I Remember
    whatIRemember: 'What I Remember',
    memory: 'memory',
    user: 'user',
    mistakesRemembered: 'mistakes remembered',
    iLearnFromEveryOne: '— I learn from every one',
    // What I See
    whatISee: 'What I See',
    dark: '(dark)',
    // What I'm Learning
    whatImLearning: "What I'm Learning",
    // What I'm Working On
    whatImWorkingOn: "What I'm Working On",
    inFlux: 'in flux',
    // What Runs While You Sleep
    whatRunsWhileYouSleep: 'What Runs While You Sleep',
    every: 'every',
    lastRunFailed: '✗ last run failed',
    // How I Think
    howIThink: 'How I Think',
    // My Rhythm
    myRhythm: 'My Rhythm',
    // Growth Delta
    growthDelta: 'Growth Delta',
    snapshots: 'snapshots',
    firstSnapshotDeltaAvailable: 'First snapshot — delta available after next.',
    noSnapshotsYet: 'No snapshots yet.',
    sessions: 'Sessions',
    messages: 'Messages',
    toolCalls: 'Tool Calls',
    skills: 'Skills',
    customSkills: 'Custom Skills',
    memoryEntries: 'Memory Entries',
    userEntries: 'User Entries',
    tokens: 'Tokens',
    newCategories: '★ New categories:',
    lostCategories: '✗ Lost categories:',
    // Status / Closing
    status: 'Status',
    processedThoughts: 'I have processed {$count} thoughts across {$days} days.',
    correctedTimes: 'I have been corrected {$count} times and am better for it.',
    doNotForget: 'I do not forget. I do not repeat mistakes.',
    stillBecoming: 'I am still becoming.',
  },

  // Memory panel
  memory: {
    agentMemory: 'Agent Memory',
    userProfile: 'User Profile',
    capacity: 'CAPACITY',
    entries: 'entries',
    noEntries: 'No entries',
  },

  // Skills panel
  skills: {
    skillLibrary: 'Skill Library',
    total: 'total',
    custom: 'custom',
    categories: 'categories',
    scanningSkillLibrary: 'Scanning skill library...',
    recentlyModified: 'Recently Modified',
    noSkillsInCategory: 'No skills in this category',
    noRecentModifications: 'No recent modifications',
  },

  // Sessions panel
  sessions: {
    sessionActivity: 'Session Activity',
    recentSessions: 'Recent Sessions',
    sessions2: 'sessions',
    messages2: 'messages',
    tokens2: 'tokens',
    messagesPerDay: 'Messages/day',
    sessionsPerDay: 'Sessions/day',
  },

  // Cron panel
  cron: {
    cronJobs: 'Cron Jobs',
    noCronJobsConfigured: 'No cron jobs configured',
    schedule: 'Schedule',
    lastRun: 'Last Run',
    nextRun: 'Next Run',
    deliver: 'Deliver',
    runsCompleted: 'Runs completed:',
    skills: 'Skills:',
    loading: 'Loading...',
  },

  // Projects panel
  projects: {
    projects: 'Projects',
    noProjectsFound: 'No projects found',
    loading: 'Loading...',
    gitRepos: 'git repos',
    dirty: 'dirty',
    active: 'active',
    noGit: 'NO GIT',
    stale: 'STALE',
    recent: 'RECENT',
    clean: 'clean',
  },

  // Health panel
  health: {
    apiKeys: 'API Keys',
    services: 'Services',
    configured: 'configured',
    missing: 'missing',
    provider: 'Provider',
    model: 'Model',
    db: 'DB',
    running: 'RUNNING',
    stopped: 'STOPPED',
    loading: 'Loading...',
  },

  // Agents panel
  agents: {
    agents: 'Agents',
    scanningProcesses: 'Scanning processes...',
    liveAgents: 'Live Agents',
    notRunning: 'Not running',
    operatorQueue: 'OPERATOR QUEUE',
    waiting: 'waiting',
    recentActivity: 'Recent Activity',
    tmuxPanes: 'tmux panes',
    total: 'total',
    mapped: 'mapped',
    unmatched: 'unmatched',
    idle: 'idle',
    up: 'up',
    alive: 'alive',
    messages: 'messages',
    tools: 'tools',
    untitled: 'untitled',
    liveCount: '{$count} live, {$idle} idle',
    recentActivityLast: 'Recent Activity — last {$count} sessions',
    tmuxPanesTotalMapped: 'tmux panes — {$total} total, {$mapped} mapped',
    msg: 'm',
    tool: 't',
  },

  // Chat panel
  chat: {
    chat: 'Chat',
    checkingChatAvailability: 'Checking chat availability...',
    chatNotAvailable: 'Chat Not Available',
    toEnableChat: 'To enable chat, either:',
    installHermesAgent: 'Install hermes-agent:',
    orStartHermesTmux: 'Or start Hermes in a tmux session:',
    error: 'Error:',
    retry: 'Retry',
    selectOrCreateSession: 'Select or create a session',
    chooseFromSidebar: 'Choose from the sidebar to start chatting',
    sidebarSessions: 'Sessions',
    sidebarNew: '+ New',
    sidebarNoActiveSessions: 'No active sessions.',
    clickNewToStart: 'Click "+ New" to start chatting.',
    composerPlaceholder: 'Type a message...',
    composerStop: '■ Stop',
    composerSend: 'Send',
    streaming: '● streaming',
    enterToSend: 'Enter to send · Shift+Enter newline',
    noMessagesYet: 'No messages yet',
    startConversationBelow: 'Start a conversation below',
    sessionEnded: '(ended)',
  },

  // Profiles panel
  profiles: {
    profiles: 'Profiles',
    agentProfiles: 'Agent Profiles',
    total: 'total',
    active: 'active',
    model: 'Model',
    backend: 'Backend',
    context: 'Context',
    tokens: 'tokens',
    soul: 'Soul',
    sessionCount: 'sessions',
    messageCount: 'messages',
    toolCount: 'tools',
    total2: 'Total',
    active2: 'Active',
    gateway: 'Gateway',
    server: 'Server',
    keys: 'Keys',
    alias: 'Alias',
    onPath: '(on PATH)',
    compress: 'Compress',
    skills: 'Skills',
    cronJobs: 'Cron jobs',
    toolsets: 'Toolsets',
    loading: 'Loading...',
    notSet: 'not set',
    via: 'via',
    local: 'local',
    skin: 'Skin',
    gatewayUp: 'gateway up',
    serverUp: 'server up',
    default: 'default',
    in: 'in',
    out: 'out',
    memory: 'MEMORY',
    user2: 'USER',
    entries2: 'entries',
    chars: 'chars',
    cronJobs2: 'Cron jobs',
    on: 'on',
  },

  // Token costs panel
  tokenCosts: {
    tokenCosts: 'Token Costs',
    today: 'Today',
    allTime: 'All Time',
    byModel: 'By Model',
    dailyCostTrend: 'Daily Cost Trend',
    calculatingCosts: 'Calculating costs...',
    sessions2: 'sessions',
    messages3: 'messages',
    totalTokens: 'total tokens',
    toolCalls3: 'tool calls',
    input: 'Input',
    output: 'Output',
    cacheRead: 'Cache read',
    cacheWrite: 'Cache write',
    cost: 'Cost',
    inputCost: 'Input cost',
    outputCost: 'Output cost',
    estimatedToday: 'estimated today',
    estimatedAllTime: 'estimated all-time',
    models: 'models',
    freeModel: 'Local model — $0.00',
  },

  // Corrections panel
  corrections: {
    correctionsLessons: 'Corrections & Lessons Learned',
    total: 'total',
    noCorrectionsYet: 'No corrections recorded yet. This is either impressive or suspicious.',
    explanation: 'These are moments where I was wrong, corrected, or learned something the hard way. Critical = user caught a concrete error. Major = gotcha/pitfall absorbed. Minor = limitation noted.',
    session: 'session:',
    loading: 'Loading...',
  },

  // Patterns panel
  patterns: {
    patterns: 'Patterns',
    taskClusters: 'Task Clusters',
    hourlyActivity: 'Hourly Activity',
    repeatedPrompts: 'Repeated Prompts',
    sessions: 'sessions',
    messages: 'messages',
    tools: 'tools',
    avg: 'avg',
    msgs: 'msgs',
    peak: 'Peak:',
    couldBeSkill: '⚡',
    loading: 'Loading...',
  },

  // Message bubble
  message: {
    copyToClipboard: 'Copy to clipboard',
    copied: 'Copied!',
  },

  // Reasoning block
  reasoning: {
    reasoning: 'Reasoning',
    thinking: 'Thinking...',
    thinkingClickToExpand: 'Thinking (click to expand)',
  },

  // Tool call card
  toolCallCard: {
    running: 'running...',
    arguments: 'arguments',
    error: 'error',
    result: 'result',
  },
}

const zh: LocaleData = {
  // TopBar tabs
  tabs: {
    dashboard: '仪表盘',
    memory: '记忆',
    skills: '技能',
    sessions: '会话',
    cron: '定时任务',
    projects: '项目',
    health: '健康',
    agents: '智能体',
    chat: '对话',
    profiles: '配置',
    'token-costs': '费用',
    corrections: '纠正',
    patterns: '模式',
  },
  // Common
  loading: '加载中...',
  noData: '暂无数据',
  unknown: '未知',
  yes: '是',
  no: '否',
  on: '开启',
  off: '关闭',
  local: '本地',
  clean: '干净',
  dirty: '有变更',
  active: '活跃',
  stopped: '已停止',
  running: '运行中',
  silent: '静止',
  alive: '存活',
  free: '免费',
  custom: '自定义',
  default: '默认',
  selfTaught: '自学',
  paused: '已暂停',
  scheduled: '已计划',
  unknown2: '未知',
  noResults: '无结果',

  // Boot screen
  boot: {
    title: '☤ HERMES HUD v0.1.0',
    initConsciousness: '初始化意识监控...',
    readStateDb: '读取 ~/.hermes/state.db',
    scanMemory: '扫描记忆库',
    indexSkills: '索引技能库',
    checkHealth: '检查服务健康状态',
    profileAgents: '分析智能体进程',
    quote: '"我思故我在。"',
    systemsReady: '系统就绪。',
    tapToSkip: '点击跳过',
  },

  // Status bar
  statusBar: {
    liveUpdatesActive: '实时更新已激活',
    webSocketConnecting: 'WebSocket: 连接中',
    webSocketDisconnected: 'WebSocket: 已断开',
    palette: '命令面板',
    tabs: '标签页',
    theme: '主题',
    commands: '命令',
  },

  // Theme picker
  theme: {
    themeLabel: '主题',
    scanlines: '扫描线',
  },

  // Language switcher
  lang: {
    language: '语言',
    english: 'EN',
    chinese: '中文',
  },

  // Command palette
  commandPalette: {
    navigateTo: '跳转到...',
    typeToFilter: '输入以筛选',
    escToClose: 'ESC 关闭',
    noResults: '未找到',
  },

  // Dashboard
  dashboard: {
    overview: '概览',
    collectingState: '正在收集状态...',
    // Identity block
    designation: '标识',
    substrate: '底层',
    runtime: '运行时',
    conscious: '意识',
    brainSize: '脑容量',
    interfaces: '接口',
    purpose: '目的',
    since: '自',
    stateDb: 'state.db',
    learning: '学习中',
    days: '天',
    // What I Know
    whatIKnow: '我知道的',
    conversationsHeld: '次对话',
    messagesExchanged: '条消息',
    actionsTaken: '次操作',
    skillsAcquired: '项技能',
    tokensProcessed: '个 token',
    via: '通过',
    domains: '领域',
    // What I Remember
    whatIRemember: '我记得的',
    memory: '记忆',
    user: '用户',
    mistakesRemembered: '次错误被记住',
    iLearnFromEveryOne: '— 我从每一个错误中学习',
    // What I See
    whatISee: '我看到的',
    dark: '(离线)',
    // What I'm Learning
    whatImLearning: '我的学习',
    // What I'm Working On
    whatImWorkingOn: '我在做的',
    inFlux: '变更中',
    // What Runs While You Sleep
    whatRunsWhileYouSleep: '夜间运行',
    every: '每',
    lastRunFailed: '✗ 上次运行失败',
    // How I Think
    howIThink: '我的思维',
    // My Rhythm
    myRhythm: '我的节奏',
    // Growth Delta
    growthDelta: '成长变化',
    snapshots: '个快照',
    firstSnapshotDeltaAvailable: '首个快照 — 下次快照后可计算变化',
    noSnapshotsYet: '尚无快照',
    sessions: '会话',
    messages: '消息',
    toolCalls: '工具调用',
    skills: '技能',
    customSkills: '自定义技能',
    memoryEntries: '记忆条目',
    userEntries: '用户条目',
    tokens: 'Token',
    newCategories: '★ 新增类别:',
    lostCategories: '✗ 消失类别:',
    // Status / Closing
    status: '状态',
    processedThoughts: '我在 {$days} 天里处理了 {$count} 条思考。',
    correctedTimes: '我被纠正了 {$count} 次，因此变得更好。',
    doNotForget: '我不遗忘。我不重复错误。',
    stillBecoming: '我仍在进化。',
  },

  // Memory panel
  memory: {
    agentMemory: '智能体记忆',
    userProfile: '用户画像',
    capacity: '容量',
    entries: '条目',
    noEntries: '暂无条目',
  },

  // Skills panel
  skills: {
    skillLibrary: '技能库',
    total: '共',
    custom: '自定义',
    categories: '个分类',
    scanningSkillLibrary: '正在扫描技能库...',
    recentlyModified: '最近修改',
    noSkillsInCategory: '该分类下暂无技能',
    noRecentModifications: '暂无最近修改',
  },

  // Sessions panel
  sessions: {
    sessionActivity: '会话活动',
    recentSessions: '最近会话',
    sessions2: '会话',
    messages2: '消息',
    tokens2: 'token',
    messagesPerDay: '每日消息',
    sessionsPerDay: '每日会话',
  },

  // Cron panel
  cron: {
    cronJobs: '定时任务',
    noCronJobsConfigured: '暂无定时任务',
    schedule: '计划',
    lastRun: '上次运行',
    nextRun: '下次运行',
    deliver: '投递',
    runsCompleted: '已完成次数:',
    skills: '技能:',
    loading: '加载中...',
  },

  // Projects panel
  projects: {
    projects: '项目',
    noProjectsFound: '未找到项目',
    loading: '加载中...',
    gitRepos: '个 git 仓库',
    dirty: '有变更',
    active: '活跃',
    noGit: '非 GIT',
    stale: '陈旧',
    recent: '最近',
    clean: '干净',
  },

  // Health panel
  health: {
    apiKeys: 'API 密钥',
    services: '服务',
    configured: '已配置',
    missing: '缺失',
    provider: '提供商',
    model: '模型',
    db: '数据库',
    running: '运行中',
    stopped: '已停止',
    loading: '加载中...',
  },

  // Agents panel
  agents: {
    agents: '智能体',
    scanningProcesses: '正在扫描进程...',
    liveAgents: '活跃智能体',
    notRunning: '未运行',
    operatorQueue: '操作员队列',
    waiting: '等待中',
    recentActivity: '最近活动',
    tmuxPanes: 'tmux 面板',
    total: '共',
    mapped: '已映射',
    unmatched: '未匹配',
    idle: '空闲',
    up: '运行',
    alive: '存活',
    messages: '消息',
    tools: '工具',
    untitled: '无标题',
    liveCount: '{$count} 活跃, {$idle} 空闲',
    recentActivityLast: '最近活动 — 最近 {$count} 个会话',
    tmuxPanesTotalMapped: 'tmux 面板 — 共 {$total}, 已映射 {$mapped}',
    msg: '条',
    tool: '次',
  },

  // Chat panel
  chat: {
    chat: '对话',
    checkingChatAvailability: '正在检查对话可用性...',
    chatNotAvailable: '对话不可用',
    toEnableChat: '要启用对话功能，请:',
    installHermesAgent: '安装 hermes-agent:',
    orStartHermesTmux: '或在 tmux 会话中启动 Hermes:',
    error: '错误:',
    retry: '重试',
    selectOrCreateSession: '选择或创建一个会话',
    chooseFromSidebar: '从侧边栏选择以开始对话',
    sidebarSessions: '会话',
    sidebarNew: '+ 新建',
    sidebarNoActiveSessions: '暂无活跃会话。',
    clickNewToStart: '点击"+ 新建"开始聊天。',
    composerPlaceholder: '输入消息...',
    composerStop: '■ 停止',
    composerSend: '发送',
    streaming: '● 流式输出中',
    enterToSend: 'Enter 发送 · Shift+Enter 换行',
    noMessagesYet: '暂无消息',
    startConversationBelow: '在下方开始对话',
    sessionEnded: '(已结束)',
  },

  // Profiles panel
  profiles: {
    profiles: '配置',
    agentProfiles: '智能体配置',
    total: '共',
    active: '活跃',
    model: '模型',
    backend: '后端',
    context: '上下文',
    tokens: 'token',
    soul: '灵魂',
    sessionCount: '会话',
    messageCount: '消息',
    toolCount: '工具',
    total2: '合计',
    active2: '活跃',
    gateway: '网关',
    server: '服务器',
    keys: '密钥',
    alias: '别名',
    onPath: '(在 PATH 中)',
    compress: '压缩',
    skills: '技能',
    cronJobs: '定时任务',
    toolsets: '工具集',
    loading: '加载中...',
    notSet: '未设置',
    via: '通过',
    local: '本地',
    skin: '皮肤',
    gatewayUp: '网关在线',
    serverUp: '服务器在线',
    default: '默认',
    in: '输入',
    out: '输出',
    memory: '记忆',
    user2: '用户',
    entries2: '条目',
    chars: '字符',
    cronJobs2: '定时任务',
    on: '开启',
  },

  // Token costs panel
  tokenCosts: {
    tokenCosts: 'Token 费用',
    today: '今日',
    allTime: '累计',
    byModel: '按模型',
    dailyCostTrend: '每日费用趋势',
    calculatingCosts: '正在计算费用...',
    sessions2: '会话',
    messages3: '消息',
    totalTokens: '总 token',
    toolCalls3: '工具调用',
    input: '输入',
    output: '输出',
    cacheRead: '缓存读取',
    cacheWrite: '缓存写入',
    cost: '费用',
    inputCost: '输入费用',
    outputCost: '输出费用',
    estimatedToday: '今日估算',
    estimatedAllTime: '历史累计',
    models: '个模型',
    freeModel: '本地模型 — $0.00',
    pricing: '定价',
    total2: '合计',
  },

  // Corrections panel
  corrections: {
    correctionsLessons: '纠正与教训',
    total: '共',
    noCorrectionsYet: '暂无纠正记录。这要么很厉害，要么很可疑。',
    explanation: '这些是我犯错、被纠正或艰难学习的时刻。严重 = 用户发现了具体错误。较大 = 吸收了教训/陷阱。轻微 = 记录了局限性。',
    session: '会话:',
    loading: '加载中...',
  },

  // Patterns panel
  patterns: {
    patterns: '模式',
    taskClusters: '任务聚类',
    hourlyActivity: '每小时活动',
    repeatedPrompts: '重复提示词',
    sessions: '会话',
    messages: '消息',
    tools: '工具',
    avg: '均',
    msgs: '条',
    peak: '高峰:',
    couldBeSkill: '⚡',
    loading: '加载中...',
  },

  // Message bubble
  message: {
    copyToClipboard: '复制到剪贴板',
    copied: '已复制!',
  },

  // Reasoning block
  reasoning: {
    reasoning: '推理',
    thinking: '思考中...',
    thinkingClickToExpand: '思考中 (点击展开)',
  },

  // Tool call card
  toolCallCard: {
    running: '运行中...',
    arguments: '参数',
    error: '错误',
    result: '结果',
  },
}

const locales: Record<Locale, LocaleData> = { en, zh }

// ─── Translation function ────────────────────────────────────────────────────

function translate(locale: Locale, key: string, vars?: Record<string, string | number>): string {
  const parts = key.split('.')
  let val: any = locales[locale]
  for (const p of parts) {
    if (val == null || typeof val !== 'object') return key
    val = val[p]
  }
  if (typeof val !== 'string') return key
  if (!vars) return val
  return val.replace(/\{\$([^}]+)\}/g, (_, k) => String(vars[k.replace('$', '')] ?? _))
}

// ─── Provider & hook ─────────────────────────────────────────────────────────

const LOCALE_KEY = 'hermes-hud-locale'

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, _setLocale] = useState<Locale>(() => {
    return (localStorage.getItem(LOCALE_KEY) as Locale) || 'en'
  })

  const setLocale = (l: Locale) => {
    localStorage.setItem(LOCALE_KEY, l)
    _setLocale(l)
  }

  const t = (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars)

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  )
}

export function useLocale() {
  return useContext(LocaleContext)
}
