import puppeteer from 'puppeteer-core';
import fs from 'node:fs/promises';

const url = process.argv[2] ?? 'http://127.0.0.1:8123';
const output = process.argv[3] ?? 'capture.json';
if (!process.env.CHROME_PATH) throw new Error('Set CHROME_PATH to the Chrome executable');
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH,
  headless: true,
  args: ['--enable-unsafe-swiftshader', '--no-first-run', '--no-default-browser-check'],
});
const record = {capturedAt: new Date().toISOString(), url, browser: await browser.version(), console: [], pageErrors: [], requests: [], responses: []};
try {
  const page = await browser.newPage();
  await page.setViewport({width: 1500, height: 1600, deviceScaleFactor: 1});
  let finish;
  const completed = new Promise(resolve => { finish = resolve; });
  page.on('console', message => {
    const entry = {type: message.type(), text: message.text()};
    record.console.push(entry);
    console.log(`[${entry.type}] ${entry.text}`);
    if (entry.text.includes('[repro] DONE')) finish();
  });
  page.on('pageerror', error => {
    record.pageErrors.push(String(error));
    console.log(`[pageerror] ${error}`);
  });
  page.on('request', request => record.requests.push(request.url()));
  page.on('requestfailed', request => console.log(`[requestfailed] ${request.url()} ${request.failure()?.errorText}`));
  page.on('response', response => {
    if (response.url().startsWith(url)) record.responses.push({url:response.url(), status:response.status(), headers:response.headers()});
  });
  // Observe real growth without forcing it or changing Rive's memory size.
  await page.evaluateOnNewDocument(() => {
    globalThis.__riveMemoryGrowth = [];
    const grow = WebAssembly.Memory.prototype.grow;
    WebAssembly.Memory.prototype.grow = function(delta) {
      const previous = this.buffer;
      const before = previous.byteLength;
      const result = grow.call(this, delta);
      const event = {before, after:this.buffer.byteLength, delta, detached:previous.byteLength === 0,
                     stack:new Error().stack};
      globalThis.__riveMemoryGrowth.push(event);
      console.log('[memory.grow] ' + JSON.stringify(event));
      return result;
    };
  });
  await page.goto(url, {waitUntil:'domcontentloaded', timeout:60000});
  let timeout;
  await Promise.race([completed, new Promise((_,reject) => {timeout=setTimeout(() => reject(new Error('Reproduction timed out after 120s')),120000);})]);
  clearTimeout(timeout);
  record.environment = await page.evaluate(() => ({
    crossOriginIsolated, userAgent:navigator.userAgent,
    memoryGrowth:globalThis.__riveMemoryGrowth,
    resources:performance.getEntriesByType('resource').map(r=>r.name),
  }));
  await new Promise(resolve=>setTimeout(resolve,500));
  await page.screenshot({path:output.replace(/\.json$/, '.png'), fullPage:true});
  record.complete = true;
} catch (error) {
  record.error = String(error);
  process.exitCode = 1;
} finally {
  await fs.writeFile(output, JSON.stringify(record,null,2)+'\n');
  await browser.close();
}
