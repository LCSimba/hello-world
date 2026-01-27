const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

describe('Link and Resource Checking Tests', () => {
  let htmlContent;

  beforeAll(() => {
    htmlContent = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  });

  // Helper function to check if a URL is accessible
  const checkUrl = (url) => {
    return new Promise((resolve, reject) => {
      const protocol = url.startsWith('https') ? https : http;
      const request = protocol.get(url, { timeout: 10000 }, (res) => {
        resolve({
          url,
          status: res.statusCode,
          ok: res.statusCode >= 200 && res.statusCode < 400
        });
      });

      request.on('error', (err) => {
        reject({
          url,
          error: err.message
        });
      });

      request.on('timeout', () => {
        request.destroy();
        reject({
          url,
          error: 'Request timeout'
        });
      });
    });
  };

  test('external image resources should be accessible', async () => {
    // Extract image sources from HTML
    const imgRegex = /<img[^>]+src=["']([^"']+)["']/gi;
    const images = [];
    let match;

    while ((match = imgRegex.exec(htmlContent)) !== null) {
      const src = match[1];
      // Only check external URLs
      if (src.startsWith('http://') || src.startsWith('https://')) {
        images.push(src);
      }
    }

    console.log(`\nChecking ${images.length} external image(s)...`);

    for (const img of images) {
      console.log(`  Checking: ${img}`);
      try {
        const result = await checkUrl(img);
        console.log(`    Status: ${result.status}`);
        expect(result.ok).toBe(true);
      } catch (error) {
        console.error(`    Error: ${error.error}`);
        throw new Error(`Failed to load image: ${img} - ${error.error}`);
      }
    }
  });

  test('external stylesheet resources should be accessible', async () => {
    // Extract link href from HTML
    const linkRegex = /<link[^>]+href=["']([^"']+)["'][^>]*>/gi;
    const links = [];
    let match;

    while ((match = linkRegex.exec(htmlContent)) !== null) {
      const href = match[1];
      // Only check external URLs
      if (href.startsWith('http://') || href.startsWith('https://')) {
        links.push(href);
      }
    }

    console.log(`\nChecking ${links.length} external stylesheet(s)...`);

    for (const link of links) {
      console.log(`  Checking: ${link}`);
      try {
        const result = await checkUrl(link);
        console.log(`    Status: ${result.status}`);
        expect(result.ok).toBe(true);
      } catch (error) {
        console.error(`    Error: ${error.error}`);
        throw new Error(`Failed to load stylesheet: ${link} - ${error.error}`);
      }
    }
  });

  test('local CSS file should exist', () => {
    const cssPath = path.join(__dirname, '../styles.css');
    expect(fs.existsSync(cssPath)).toBe(true);
  });

  test('local CSS file should be linked correctly in HTML', () => {
    expect(htmlContent).toMatch(/href=["']styles\.css["']/i);
  });

  test('external links (anchor tags) should be accessible', async () => {
    // Extract anchor hrefs from HTML
    const anchorRegex = /<a[^>]+href=["']([^"']+)["'][^>]*>/gi;
    const anchors = [];
    let match;

    while ((match = anchorRegex.exec(htmlContent)) !== null) {
      const href = match[1];
      // Only check external URLs (http/https)
      if (href.startsWith('http://') || href.startsWith('https://')) {
        anchors.push(href);
      }
    }

    if (anchors.length === 0) {
      console.log('\nNo external links found in HTML');
      return;
    }

    console.log(`\nChecking ${anchors.length} external link(s)...`);

    for (const anchor of anchors) {
      console.log(`  Checking: ${anchor}`);
      try {
        const result = await checkUrl(anchor);
        console.log(`    Status: ${result.status}`);
        expect(result.ok).toBe(true);
      } catch (error) {
        console.error(`    Error: ${error.error}`);
        throw new Error(`Failed to load link: ${anchor} - ${error.error}`);
      }
    }
  });

  test('all local resource references should use relative paths', () => {
    // Check that local resources don't use absolute file:// paths
    expect(htmlContent).not.toMatch(/file:\/\//);
  });

  test('image alt attributes should not be empty', () => {
    const imgRegex = /<img[^>]+>/gi;
    const images = htmlContent.match(imgRegex) || [];

    images.forEach(img => {
      const altMatch = img.match(/alt=["']([^"']*)["']/i);
      if (altMatch) {
        expect(altMatch[1].length).toBeGreaterThan(0);
      }
    });
  });
});
