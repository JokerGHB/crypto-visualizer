/**
 * 端到端验证脚本。
 *
 * 目的不是替代单元测试，而是证实「真实浏览器里点得动、算得对、看得见」：
 * 页面能渲染、参数能改、轨迹能算、单步能走、S 盒能查、练习能判分、登录能存历史。
 *
 * 运行：node e2e/verify.mjs
 * 前置：后端 :8000、前端 :5173 均已启动。
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const WEB = 'http://localhost:5173';
const SHOT_DIR = 'e2e/screenshots';
mkdirSync(SHOT_DIR, { recursive: true });

const results = [];
let failed = 0;

function record(name, ok, detail = '') {
  results.push({ name, ok, detail });
  if (!ok) {
    failed += 1;
  }
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' :: ' + detail : ''}`);
}

// 使用系统已安装的 Chrome，避免下载 Playwright 自带浏览器（内网环境常下载失败）
const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const consoleErrors = [];
page.on('console', (msg) => {
  if (msg.type() === 'error') {
    consoleErrors.push(msg.text());
  }
});
page.on('pageerror', (err) => consoleErrors.push(String(err)));

try {
  // ---------- 1. 首页 ----------
  await page.goto(WEB, { waitUntil: 'networkidle' });
  const h1 = await page.locator('h1').first().textContent();
  record('首页标题渲染', Boolean(h1 && h1.includes('密码学')), h1 ?? '空');
  await page.screenshot({ path: `${SHOT_DIR}/01-home.png`, fullPage: true });

  // ---------- 2. 可视化页：默认轨迹 ----------
  await page.goto(`${WEB}/playground`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.state-matrix', { timeout: 15000 });

  const matrices = await page.locator('.state-matrix').count();
  record('双状态矩阵渲染', matrices >= 2, `找到 ${matrices} 个`);

  const cells = await page.locator('.cell').count();
  record('每矩阵 16 格', cells >= 32, `共 ${cells} 格`);

  // 校验密文与标准向量一致
  const output = await page.locator('.kv .v.strong').first().textContent();
  record(
    'FIPS-197 密文正确',
    output?.trim() === '3925841d02dc09fbdc118597196a0b32',
    output?.trim() ?? '空',
  );

  const stepTotal = await page.locator('.step-badge').textContent();
  record('AES-128 共 40 步', stepTotal?.includes('40'), stepTotal?.trim() ?? '空');

  await page.screenshot({ path: `${SHOT_DIR}/02-playground.png`, fullPage: true });

  // ---------- 3. 单步与跳转 ----------
  const firstOp = await page.locator('.step-head .card-title').textContent();
  await page.locator('button', { hasText: '下一步' }).first().click();
  await page.waitForTimeout(300);
  const secondOp = await page.locator('.step-head .card-title').textContent();
  record('单步执行改变当前步骤', firstOp !== secondOp, `${firstOp?.trim()} -> ${secondOp?.trim()}`);

  const stepText = await page.locator('.step-badge').textContent();
  record('单步后步号递增', stepText?.includes('2 /'), stepText?.trim() ?? '空');

  // 跳轮（select 顺序：0=算法 1=模式 2=速度 3=跳轮）
  await page.locator('select').nth(3).selectOption('5');
  await page.waitForTimeout(400);
  const roundText = await page.locator('.step-head .card-title').textContent();
  record('跳转到第 5 轮', roundText?.includes('第 5 轮'), roundText?.trim() ?? '空');

  // ---------- 4. 单元格点击显示字节来历 ----------
  await page.locator('.cell').first().click();
  await page.waitForTimeout(300);
  const detailVisible = await page.locator('.cell-detail').isVisible();
  record('点击单元格显示字节来历', detailVisible);

  // ---------- 5. 参数调节：AES-256 ----------
  await page.goto(`${WEB}/playground`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.state-matrix');
  await page.locator('select').first().selectOption('256');
  const keyInput = page.locator('input.mono').nth(1);
  await keyInput.fill('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f');
  await page.locator('input.mono').nth(0).fill('00112233445566778899aabbccddeeff');
  await page.locator('button', { hasText: '生成轨迹' }).click();
  await page.waitForTimeout(1200);
  const total256 = await page.locator('.step-badge').textContent();
  record('AES-256 共 56 步', total256?.includes('56'), total256?.trim() ?? '空');

  const out256 = await page.locator('.kv .v.strong').first().textContent();
  record(
    'AES-256 密文正确',
    out256?.trim() === '8ea2b7ca516745bfeafc49904b496089',
    out256?.trim() ?? '空',
  );

  await page.screenshot({ path: `${SHOT_DIR}/03-aes256.png`, fullPage: true });

  // ---------- 6. 解密验证 ----------
  // 解密要把上一轮得到的密文作为输入，而不是明文
  const cipherText = '8ea2b7ca516745bfeafc49904b496089';
  await page.locator('select').nth(1).selectOption('decrypt');
  await page.locator('input.mono').nth(0).fill(cipherText);
  await page.locator('button', { hasText: '生成轨迹' }).click();
  await page.waitForTimeout(1500);
  const decOut = await page.locator('.kv .v.strong').first().textContent();
  record(
    '解密还原明文',
    decOut?.trim() === '00112233445566778899aabbccddeeff',
    decOut?.trim() ?? '空',
  );

  // ---------- 7. S 盒页 ----------
  await page.goto(`${WEB}/sbox`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.sbox-table');
  const sboxCells = await page.locator('.sbox-table td').count();
  record('S 盒 256 格', sboxCells === 256, `共 ${sboxCells} 格`);

  // sbox[0x19] 应为 d4
  const targetCell = page.locator('.sbox-table tbody tr').nth(1).locator('td').nth(9);
  const cellValue = await targetCell.textContent();
  record('sbox[0x19] = d4', cellValue?.trim() === 'd4', cellValue?.trim() ?? '空');

  await page.locator('.search').fill('d4');
  await page.waitForTimeout(300);
  const matchCount = await page.locator('.sbox-table td.match').count();
  record('按值反查命中', matchCount >= 1, `命中 ${matchCount} 格`);
  await page.screenshot({ path: `${SHOT_DIR}/04-sbox.png`, fullPage: true });

  // ---------- 8. 登录与历史记录 ----------
  const username = `e2e_${Date.now()}`;
  await page.goto(`${WEB}/login`, { waitUntil: 'networkidle' });
  await page.locator('.link', { hasText: '去注册' }).click();
  await page.locator('input[autocomplete="username"]').fill(username);
  const pwInputs = page.locator('input[type="password"]');
  await pwInputs.nth(0).fill('e2epass123');
  await pwInputs.nth(1).fill('e2epass123');
  await page.locator('button', { hasText: '注册并登录' }).click();
  await page.waitForTimeout(2000);

  const loggedIn = await page.locator('.username').isVisible();
  record('注册并登录成功', loggedIn, username);

  // 生成一次轨迹以产生历史（等轨迹真正算完再离开，否则不会写库）
  await page.goto(`${WEB}/playground`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.state-matrix', { timeout: 15000 });
  await page.waitForTimeout(1500);
  const savedOut = await page.locator('.kv .v.strong').first().textContent();
  record('登录后能生成轨迹', Boolean(savedOut && savedOut.trim().length === 32), savedOut?.trim() ?? '空');

  await page.goto(`${WEB}/history`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  const rows = await page.locator('.row').count();
  record('历史记录已保存', rows >= 1, `${rows} 条`);

  if (rows >= 1) {
    await page.locator('.row button', { hasText: '回放' }).first().click();
    await page.waitForTimeout(1500);
    const replayNote = await page.locator('.note').isVisible();
    record('历史回放进入只读模式', replayNote);
    const replaySteps = await page.locator('.step-badge').textContent();
    record('回放保持 40 步', replaySteps?.includes('40'), replaySteps?.trim() ?? '空');
  }

  // ---------- 9. 练习模式 ----------
  await page.goto(`${WEB}/exercise`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const prompt = await page.locator('.prompt').textContent();
  record('练习出题成功', Boolean(prompt && prompt.length > 5), prompt?.slice(0, 30) ?? '空');

  const optionCount = await page.locator('.option').count();
  record('步骤识别四选一', optionCount === 4, `${optionCount} 个选项`);

  await page.locator('.option').first().click();
  await page.locator('button', { hasText: '提交答案' }).click();
  await page.waitForTimeout(1200);
  const verdict = await page.locator('.verdict').textContent();
  record('练习判分返回结果', Boolean(verdict), verdict?.trim() ?? '空');
  await page.screenshot({ path: `${SHOT_DIR}/05-exercise.png`, fullPage: true });

  // ---------- 10. AI 辅导（在线或降级都必须出内容） ----------
  await page.goto(`${WEB}/playground`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const aiTextarea = page.locator('.composer textarea');
  await aiTextarea.fill('这一步为什么要把 19 变成 d4？');
  await page.locator('button', { hasText: '发送' }).click();

  // 真实 AI 首字节可能 10~45 秒，轮询等待而非固定 sleep
  let aiReply = '';
  for (let i = 0; i < 45; i += 1) {
    await page.waitForTimeout(2000);
    const n = await page.locator('.bubble.assistant').count();
    if (n === 0) {
      continue;
    }
    const text = await page.locator('.bubble.assistant .content').first().textContent();
    if (text && text.trim() && !text.includes('思考中')) {
      aiReply = text;
      break;
    }
  }

  const bubbles = await page.locator('.bubble.assistant').count();
  record(
    'AI 面板返回内容',
    bubbles >= 1 && Boolean(aiReply),
    aiReply?.slice(0, 50) ?? '超时未返回',
  );
  // 降级也是合法路径，但需能区分，便于确认密钥是否真的生效
  record(
    'AI 走在线回答（非降级）',
    Boolean(aiReply) && !aiReply.includes('离线'),
    aiReply.includes('离线') ? '走了降级路径' : '在线',
  );
  await page.screenshot({ path: `${SHOT_DIR}/06-ai.png`, fullPage: true });

  // ---------- 11. 控制台无错误 ----------
  const realErrors = consoleErrors.filter(
    (e) => !e.includes('favicon') && !e.includes('Download the Vue Devtools'),
  );
  record('浏览器控制台无报错', realErrors.length === 0, realErrors.slice(0, 3).join(' | '));
} catch (err) {
  record('脚本执行异常', false, String(err));
  await page.screenshot({ path: `${SHOT_DIR}/ERROR.png`, fullPage: true });
} finally {
  await browser.close();
}

console.log(`\n===== 结果：${results.length - failed}/${results.length} 通过 =====`);
process.exit(failed > 0 ? 1 : 0);