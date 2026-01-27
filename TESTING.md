# Testing Documentation

This document describes the test coverage and testing strategy for the hello-world GitHub Pages site.

## Test Coverage Overview

We have implemented comprehensive testing across four key areas:

### 1. HTML Validation Tests (`tests/html.test.js`)

**Purpose:** Ensures HTML is well-formed, valid HTML5, and follows best practices.

**What is tested:**
- Valid HTML5 document structure
- Proper DOCTYPE declaration
- Presence of required tags (html, head, body, title)
- Charset definition
- All opening tags have matching closing tags
- Images have alt attributes
- HTML tag has lang attribute for accessibility

**How to run:**
```bash
npm run test:html
```

### 2. Accessibility Tests (`tests/accessibility.test.js`)

**Purpose:** Ensures the site is accessible to all users, including those with disabilities.

**What is tested:**
- No automatically detectable accessibility violations (using axe-core)
- Valid document language attribute
- Descriptive alt text for images (not just filenames)
- Logical heading structure (when headings are present)
- Sufficient color contrast ratios (WCAG 2.1 AA standards)
- Keyboard navigation support
- Descriptive page title

**Standards:** WCAG 2.1 AA compliance

**How to run:**
```bash
npm run test:a11y
```

### 3. Link and Resource Checking Tests (`tests/links.test.js`)

**Purpose:** Verifies all external resources are accessible and links are not broken.

**What is tested:**
- External images are accessible (HTTP 200-399 response)
- External stylesheets are accessible
- Local CSS file exists and is linked correctly
- External anchor links are accessible (when present)
- No absolute file:// paths in resource references
- Image alt attributes are not empty

**How to run:**
```bash
npm run test:links
```

**Note:** These tests make actual HTTP requests and may take longer to run.

### 4. CSS Validation Tests (`tests/css.test.js`)

**Purpose:** Ensures CSS is valid, follows best practices, and maintains consistency.

**What is tested:**
- CSS file exists
- Valid CSS syntax (using stylelint)
- Matching braces
- Properly formatted selectors
- All properties have values
- No TODO or FIXME comments in production code
- Proper unit specifications
- Consistent spacing and indentation
- No duplicate properties in the same selector
- Valid color values (hex format)

**Standards:** Based on stylelint-config-standard

**How to run:**
```bash
npm run test:css
```

## Running Tests

### Prerequisites

Install dependencies first:
```bash
npm install
```

This will install:
- Jest (test framework)
- html-validate (HTML validation)
- axe-core & Playwright (accessibility testing)
- stylelint (CSS validation)

### Run All Tests

```bash
npm test              # Run offline tests only (HTML + CSS)
npm run test:offline  # Same as above, explicit
npm run test:all      # Run ALL tests including network-dependent ones
```

**Note:** The default `npm test` command runs only offline tests (HTML and CSS validation) for faster feedback and CI/CD compatibility in restricted environments.

### Run Specific Test Suites

```bash
npm run test:html        # HTML validation only
npm run test:a11y        # Accessibility only
npm run test:links       # Link checking only
npm run test:css         # CSS validation only
```

### Run Tests in Watch Mode

```bash
npm run test:watch
```

### Generate Coverage Report

```bash
npm run test:coverage
```

## Test Results Interpretation

### HTML Validation
- **Green**: All HTML is valid and well-formed
- **Red**: Syntax errors, missing closing tags, or invalid HTML detected

### Accessibility
- **Green**: No accessibility violations, meets WCAG 2.1 AA standards
- **Red**: Accessibility issues detected (details logged to console with fix recommendations)

### Links
- **Green**: All external resources are accessible
- **Red**: Broken links or inaccessible resources (check network connection)

### CSS
- **Green**: CSS is valid and follows best practices
- **Red**: Syntax errors or style violations detected

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: '18'
      - run: npm install
      - run: npm test
```

## Test Maintenance

### When to Update Tests

1. **Adding new HTML elements**: Update `html.test.js` to validate new structure
2. **Adding interactive features**: Extend `accessibility.test.js` for keyboard navigation
3. **Adding external resources**: Update `links.test.js` to check new URLs
4. **Modifying styles**: Ensure `css.test.js` covers new CSS rules

### Known Limitations

- **Link tests**: Require internet connectivity; may fail if external sites are down
- **Accessibility tests**: Launch a headless browser (requires system resources)
- **CSS validation**: Some intentional styles may trigger warnings (can be configured in `.stylelintrc.json`)

## Testing Philosophy

Our testing strategy prioritizes:

1. **Correctness**: HTML must be valid and well-formed
2. **Accessibility**: Site must be usable by everyone
3. **Reliability**: External resources must be accessible
4. **Maintainability**: CSS must be clean and consistent

## Issues Fixed by Tests

The test suite has already caught and helped fix:

1. **Malformed HTML tag** (line 17): `<p>git_change<p>` → `<p>git_change</p>`
2. **Missing lang attribute**: Added `lang="en"` to `<html>` tag
3. **Poor alt text**: Improved from "octocat-gif" to descriptive text
4. **Accessibility compliance**: Ensured WCAG 2.1 AA standards

## Further Reading

- [html-validate documentation](https://html-validate.org/)
- [axe-core rules](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [stylelint rules](https://stylelint.io/user-guide/rules/list)
