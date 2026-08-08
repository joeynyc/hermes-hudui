const assert = require('node:assert/strict')
const { chromium } = require('playwright')

// Standalone Playwright smoke test for the CC Cost tab.
// Requires `playwright` available to Node, or run through the Codex
// Playwright skill runner.
const HUD_URL = process.env.HUD_URL || 'http://localhost:5173'

async function main() {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

    await page.addInitScript(() => {
      sessionStorage.setItem('hud-booted', 'true')
      localStorage.setItem('hermes-hudui-lang', 'en')
    })

    // Supply mock cc-costs data so the tab renders its panels.
    const mockData = {
      today: {
        date: '2026-07-30',
        session_count: 3,
        message_count: 42,
        tool_call_count: 12,
        input_tokens: 500_000,
        output_tokens: 50_000,
        cache_read_tokens: 200_000,
        cache_write_tokens: 10_000,
        total_tokens: 550_000,
        estimated_cost_usd: 2.50,
        billed_cost_usd: 2.50,
        cache_savings_usd: 0.60,
      },
      all_time: {
        session_count: 120,
        message_count: 3200,
        tool_call_count: 850,
        input_tokens: 12_000_000,
        output_tokens: 1_200_000,
        cache_read_tokens: 5_000_000,
        cache_write_tokens: 200_000,
        total_tokens: 13_200_000,
        estimated_cost_usd: 45.30,
        billed_cost_usd: 45.30,
        cache_savings_usd: 12.00,
        actual_coverage_pct: 75,
      },
      by_model: [
        {
          model: 'claude-sonnet-4-6',
          matched_pricing: 'claude-sonnet-4-6',
          session_count: 100,
          message_count: 2800,
          tool_call_count: 750,
          input_tokens: 10_000_000,
          output_tokens: 1_000_000,
          cache_read_tokens: 4_000_000,
          cache_write_tokens: 150_000,
          estimated_cost_usd: 38.00,
          actual_cost_usd: 42.00,
          actual_delta_usd: 4.00,
          actual_delta_pct: 10.5,
          billed_cost_usd: 42.00,
          cache_savings_usd: 10.00,
        },
        {
          model: 'claude-haiku-3-5',
          matched_pricing: 'claude-haiku-3-5',
          session_count: 20,
          message_count: 400,
          tool_call_count: 100,
          input_tokens: 2_000_000,
          output_tokens: 200_000,
          estimated_cost_usd: 2.40,
          billed_cost_usd: 2.40,
          cache_savings_usd: 0.50,
        },
      ],
      daily_trend: [
        { date: '2026-07-24', cost: 5.00, billed_cost_usd: 5.00, tokens: 1_800_000, sessions: 15 },
        { date: '2026-07-25', cost: 6.50, billed_cost_usd: 6.50, tokens: 2_000_000, sessions: 18 },
        { date: '2026-07-26', cost: 4.20, billed_cost_usd: 4.20, tokens: 1_500_000, sessions: 14 },
        { date: '2026-07-27', cost: 7.80, billed_cost_usd: 7.80, tokens: 2_200_000, sessions: 20 },
        { date: '2026-07-28', cost: 8.10, billed_cost_usd: 8.10, tokens: 2_400_000, sessions: 22 },
        { date: '2026-07-29', cost: 5.50, billed_cost_usd: 5.50, tokens: 1_900_000, sessions: 16 },
        { date: '2026-07-30', cost: 2.50, billed_cost_usd: 2.50, tokens: 550_000, sessions: 3 },
      ],
      top_sessions: [
        {
          id: 'session-abc-1',
          project: 'test-user/myproject',
          date: '2026-07-28',
          model: 'claude-sonnet-4-6',
          message_count: 120,
          tool_call_count: 35,
          input_tokens: 500_000,
          output_tokens: 50_000,
          total_tokens: 550_000,
          estimated_cost_usd: 3.50,
          billed_cost_usd: 3.50,
        },
        {
          id: 'session-abc-2',
          project: 'test-user/otherproject',
          date: '2026-07-27',
          model: 'claude-sonnet-4-6',
          message_count: 80,
          tool_call_count: 20,
          input_tokens: 300_000,
          output_tokens: 30_000,
          total_tokens: 330_000,
          estimated_cost_usd: 2.10,
          billed_cost_usd: 2.10,
        },
      ],
      trend_summary: {
        recent_7d_cost_usd: 39.60,
        previous_7d_cost_usd: 32.00,
        delta_usd: 7.60,
        delta_pct: 23.8,
        direction: 'up',
      },
      pricing_table: {},
      by_project: [],
    }

    await page.route('**/*', async (route, request) => {
      // Only intercept our cc-costs endpoint; let everything else through.
    })

    // Intercept before navigating.
    await page.route('**/api/cc-costs', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockData),
      })
    })

    // Let other API endpoints pass through to the dev server (or fail silently
    // if no server is running — the cc-costs panel doesn't depend on them).
    await page.route('**/api/**', async route => {
      if (route.request().url().includes('/api/cc-costs')) return
      // Return empty to avoid blocking other panels.
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{}',
      })
    })

    await page.goto(HUD_URL, { waitUntil: 'domcontentloaded' })

    // Click the CC Cost tab.
    const ccTab = page.getByRole('button', { name: /CC Cost/i })
    await ccTab.waitFor({ state: 'visible', timeout: 5000 })
    await ccTab.click()

    // Wait for the panels to render.
    await page.waitForTimeout(1000)

    // ── Assertions ──────────────────────────────────────

    // CC Today panel shows cost.
    const todayCost = page.locator('text=$2.50').first()
    await todayCost.waitFor({ state: 'visible', timeout: 5000 })
    assert.ok(await todayCost.isVisible(), 'Today cost $2.50 should be visible')

    // CC Total panel.
    const allTimeCost = page.locator('text=$45.30').first()
    assert.ok(await allTimeCost.isVisible(), 'All-time cost $45.30 should be visible')

    // 7-Day Trend panel.
    const trendChange = page.locator('text=+$7.60').first()
    assert.ok(await trendChange.isVisible(), 'Trend delta +$7.60 should be visible')

    // By Model section.
    const modelSection = page.locator('text=By Model').first()
    assert.ok(await modelSection.isVisible(), 'By Model section should be visible')
    const sonnetModel = page.locator('text=claude-sonnet-4-6').first()
    assert.ok(await sonnetModel.isVisible(), 'claude-sonnet-4-6 model card should be visible')

    // Top CC Sessions.
    const topSessions = page.locator('text=Top CC Sessions').first()
    assert.ok(await topSessions.isVisible(), 'Top CC Sessions section should be visible')
    const sessionProject = page.locator('text=test-user/myproject').first()
    assert.ok(await sessionProject.isVisible(), 'Top session project should be visible')

    // CC Daily Cost Trend.
    const dailyTrend = page.locator('text=CC Daily Cost Trend').first()
    assert.ok(await dailyTrend.isVisible(), 'Daily Cost Trend section should be visible')

    console.log('✅ CC Costs tab smoke test passed')
  } finally {
    await browser.close()
  }
}

main().catch(err => {
  console.error('❌ CC Costs tab smoke test failed:', err)
  process.exit(1)
})
