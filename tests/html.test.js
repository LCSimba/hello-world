const { HtmlValidate } = require('html-validate');
const fs = require('fs');
const path = require('path');

describe('HTML Validation Tests', () => {
  let htmlvalidate;
  let htmlContent;

  beforeAll(() => {
    htmlvalidate = new HtmlValidate({
      extends: ['html-validate:recommended'],
      rules: {
        'close-order': 'error',
        'void-style': ['error', { style: 'selfclose' }],
        'no-trailing-whitespace': 'off'
      }
    });
    htmlContent = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  });

  test('index.html should be valid HTML5', () => {
    const htmlPath = path.join(__dirname, '../index.html');
    const report = htmlvalidate.validateFile(htmlPath);

    // Count total errors
    let errorCount = 0;
    if (report.results && report.results.length > 0) {
      report.results.forEach(result => {
        if (result.errorCount) {
          errorCount += result.errorCount;
        }
        if (result.messages && errorCount > 0) {
          result.messages.forEach(msg => {
            if (msg.severity === 2) { // severity 2 is error
              console.log(`  Line ${msg.line}:${msg.column} - ${msg.message}`);
            }
          });
        }
      });
    }

    expect(errorCount).toBe(0);
  });

  test('index.html should have proper DOCTYPE', () => {
    expect(htmlContent).toMatch(/<!DOCTYPE html>/i);
  });

  test('index.html should have html, head, and body tags', () => {
    expect(htmlContent).toMatch(/<html/i);
    expect(htmlContent).toMatch(/<head>/i);
    expect(htmlContent).toMatch(/<body>/i);
  });

  test('index.html should have a title tag', () => {
    expect(htmlContent).toMatch(/<title>.*<\/title>/i);
  });

  test('index.html should have charset defined', () => {
    expect(htmlContent).toMatch(/charset/i);
  });

  test('all opening tags should have matching closing tags', () => {
    const openingTags = htmlContent.match(/<([a-z]+)(?:\s|>)/gi) || [];
    const closingTags = htmlContent.match(/<\/([a-z]+)>/gi) || [];

    const openingTagNames = openingTags
      .map(tag => tag.match(/<([a-z]+)/i)?.[1]?.toLowerCase())
      .filter(tag => !['img', 'meta', 'link', 'br', 'hr', 'input'].includes(tag));

    const closingTagNames = closingTags
      .map(tag => tag.match(/<\/([a-z]+)/i)?.[1]?.toLowerCase());

    openingTagNames.forEach(tagName => {
      const openCount = openingTagNames.filter(t => t === tagName).length;
      const closeCount = closingTagNames.filter(t => t === tagName).length;

      expect(closeCount).toBe(openCount);
    });
  });

  test('img tags should have alt attributes', () => {
    const imgTags = htmlContent.match(/<img[^>]*>/gi) || [];
    imgTags.forEach(img => {
      expect(img).toMatch(/alt=/i);
    });
  });

  test('html tag should have lang attribute', () => {
    const htmlTag = htmlContent.match(/<html[^>]*>/i)?.[0];
    if (htmlTag) {
      // This will fail initially - documenting the issue
      expect(htmlTag).toMatch(/lang=/i);
    }
  });
});
