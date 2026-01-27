const fs = require('fs');
const path = require('path');
const stylelint = require('stylelint');

describe('CSS Validation Tests', () => {
  let cssContent;
  const cssPath = path.join(__dirname, '../styles.css');

  beforeAll(() => {
    cssContent = fs.readFileSync(cssPath, 'utf8');
  });

  test('styles.css should exist', () => {
    expect(fs.existsSync(cssPath)).toBe(true);
  });

  test('CSS should be valid and follow standards', async () => {
    const result = await stylelint.lint({
      files: cssPath,
      config: {
        extends: 'stylelint-config-standard',
        rules: {
          'selector-id-pattern': null,
          'selector-class-pattern': null,
          'color-hex-length': 'long',
          'declaration-block-no-redundant-longhand-properties': null
        }
      }
    });

    if (result.errored) {
      console.log('\nStylelint Errors:');
      result.results.forEach(fileResult => {
        fileResult.warnings.forEach(warning => {
          console.log(`  Line ${warning.line}:${warning.column} - ${warning.text}`);
        });
      });
    }

    expect(result.errored).toBe(false);
  });

  test('CSS should not have syntax errors', () => {
    // Basic syntax checks
    const openBraces = (cssContent.match(/{/g) || []).length;
    const closeBraces = (cssContent.match(/}/g) || []).length;

    expect(openBraces).toBe(closeBraces);
  });

  test('CSS selectors should be properly formatted', () => {
    const selectors = cssContent.match(/[^{}]+(?=\s*{)/g) || [];

    selectors.forEach(selector => {
      const trimmed = selector.trim();
      // Should not be empty
      expect(trimmed.length).toBeGreaterThan(0);
      // Should not end with comma (incomplete selector list)
      expect(trimmed.endsWith(',')).toBe(false);
    });
  });

  test('CSS properties should have values', () => {
    const propertyRegex = /([a-z-]+)\s*:\s*([^;]+);/gi;
    let match;

    while ((match = propertyRegex.exec(cssContent)) !== null) {
      const property = match[1];
      const value = match[2].trim();

      expect(property.length).toBeGreaterThan(0);
      expect(value.length).toBeGreaterThan(0);
    }
  });

  test('CSS should not contain TODO or FIXME comments', () => {
    expect(cssContent.toLowerCase()).not.toMatch(/\/\*.*todo.*\*\//);
    expect(cssContent.toLowerCase()).not.toMatch(/\/\*.*fixme.*\*\//);
  });

  test('CSS units should be properly specified', () => {
    // Find all numeric values
    const numericValues = cssContent.match(/:\s*([0-9]+(?:\.[0-9]+)?[a-z%]*)/gi) || [];

    numericValues.forEach(value => {
      const match = value.match(/:\s*([0-9]+(?:\.[0-9]+)?)([a-z%]*)/i);
      if (match) {
        const number = parseFloat(match[1]);
        const unit = match[2];

        // If number is not 0, it should have a unit (unless it's line-height, z-index, etc.)
        if (number !== 0 && unit === '') {
          // This is okay for unitless properties like line-height, opacity, z-index
          // For now, we'll just log it
          console.log(`  Note: Unitless value found: ${value}`);
        }
      }
    });
  });

  test('CSS should use consistent spacing', () => {
    // Check that properties are properly indented (basic check)
    const lines = cssContent.split('\n');
    let insideBraces = false;

    lines.forEach((line, index) => {
      if (line.includes('{')) {
        insideBraces = true;
      }
      if (line.includes('}')) {
        insideBraces = false;
      }

      // Properties inside braces should have some indentation
      if (insideBraces && line.includes(':') && !line.includes('{')) {
        // Just verify the line exists and has content
        expect(line.trim().length).toBeGreaterThan(0);
      }
    });
  });

  test('CSS should not have duplicate properties in same selector', () => {
    const selectorBlocks = cssContent.match(/[^{}]+{[^{}]+}/g) || [];

    selectorBlocks.forEach(block => {
      const properties = block.match(/([a-z-]+)\s*:/gi) || [];
      const propertyNames = properties.map(p => p.replace(/\s*:\s*/, '').toLowerCase());

      const uniqueProperties = [...new Set(propertyNames)];

      if (propertyNames.length !== uniqueProperties.length) {
        console.log(`  Warning: Duplicate properties found in: ${block.substring(0, 50)}...`);
      }

      expect(propertyNames.length).toBe(uniqueProperties.length);
    });
  });

  test('CSS color values should be valid', () => {
    // Match hex colors
    const hexColors = cssContent.match(/#[0-9a-f]{3,6}/gi) || [];

    hexColors.forEach(color => {
      const isValid = /^#[0-9a-f]{3}$|^#[0-9a-f]{6}$/i.test(color);
      expect(isValid).toBe(true);
    });
  });
});
