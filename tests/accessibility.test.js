const { chromium } = require('playwright');
const { injectAxe, checkA11y, getViolations } = require('axe-core');
const fs = require('fs');
const path = require('path');

describe('Accessibility Tests', () => {
  let browser;
  let page;
  const indexPath = `file://${path.join(__dirname, '../index.html')}`;

  beforeAll(async () => {
    browser = await chromium.launch();
  });

  afterAll(async () => {
    await browser.close();
  });

  beforeEach(async () => {
    page = await browser.newPage();
  });

  afterEach(async () => {
    await page.close();
  });

  test('page should not have any automatically detectable accessibility issues', async () => {
    await page.goto(indexPath);

    // Inject axe-core into the page
    await page.addScriptTag({
      path: require.resolve('axe-core')
    });

    // Run axe accessibility checks
    const results = await page.evaluate(() => {
      return new Promise((resolve) => {
        window.axe.run((err, results) => {
          if (err) throw err;
          resolve(results);
        });
      });
    });

    // Log violations for debugging
    if (results.violations.length > 0) {
      console.log('\nAccessibility Violations:');
      results.violations.forEach(violation => {
        console.log(`\n  [${violation.impact}] ${violation.id}: ${violation.description}`);
        console.log(`  Help: ${violation.helpUrl}`);
        violation.nodes.forEach(node => {
          console.log(`    - ${node.html}`);
          console.log(`      ${node.failureSummary}`);
        });
      });
    }

    expect(results.violations).toEqual([]);
  });

  test('page should have a valid document language', async () => {
    await page.goto(indexPath);
    const lang = await page.evaluate(() => document.documentElement.lang);

    // This will likely fail initially - documenting the issue
    expect(lang).toBeTruthy();
    expect(lang).toMatch(/^[a-z]{2}(-[A-Z]{2})?$/);
  });

  test('images should have descriptive alt text', async () => {
    await page.goto(indexPath);
    const images = await page.$$eval('img', imgs =>
      imgs.map(img => ({
        src: img.src,
        alt: img.alt
      }))
    );

    images.forEach(img => {
      expect(img.alt).toBeTruthy();
      // Alt text should be descriptive, not just a filename or "image"
      expect(img.alt.length).toBeGreaterThan(3);
    });
  });

  test('page should have a logical heading structure', async () => {
    await page.goto(indexPath);
    const headings = await page.$$eval('h1, h2, h3, h4, h5, h6', heads =>
      heads.map(h => ({
        level: parseInt(h.tagName.charAt(1)),
        text: h.textContent
      }))
    );

    // Check if there's at least one h1 (if there are any headings)
    if (headings.length > 0) {
      const h1Count = headings.filter(h => h.level === 1).length;
      expect(h1Count).toBeGreaterThanOrEqual(1);
    }
  });

  test('color contrast should be sufficient', async () => {
    await page.goto(indexPath);

    await page.addScriptTag({
      path: require.resolve('axe-core')
    });

    const colorContrastResults = await page.evaluate(() => {
      return new Promise((resolve) => {
        window.axe.run({ runOnly: ['color-contrast'] }, (err, results) => {
          if (err) throw err;
          resolve(results);
        });
      });
    });

    if (colorContrastResults.violations.length > 0) {
      console.log('\nColor Contrast Issues:');
      colorContrastResults.violations.forEach(violation => {
        console.log(`  ${violation.description}`);
        violation.nodes.forEach(node => {
          console.log(`    - ${node.html}`);
        });
      });
    }

    expect(colorContrastResults.violations).toEqual([]);
  });

  test('page should be keyboard navigable', async () => {
    await page.goto(indexPath);

    // Check if there are any focusable elements
    const focusableElements = await page.$$eval(
      'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
      elements => elements.length
    );

    // If there are interactive elements, they should be keyboard accessible
    if (focusableElements > 0) {
      const tabIndexes = await page.$$eval(
        'a, button, input, select, textarea',
        elements => elements.map(el => el.tabIndex)
      );

      // None should have tabindex="-1" unless intentionally hidden
      const negativeTabIndexes = tabIndexes.filter(idx => idx === -1);
      expect(negativeTabIndexes.length).toBe(0);
    }
  });

  test('page title should be descriptive', async () => {
    await page.goto(indexPath);
    const title = await page.title();

    expect(title).toBeTruthy();
    expect(title.length).toBeGreaterThan(0);
    // Title should not be generic
    expect(title).not.toBe('Untitled');
    expect(title).not.toBe('Document');
  });
});
