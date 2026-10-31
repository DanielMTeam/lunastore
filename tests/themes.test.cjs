const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('staticfiles/js/themes.js', 'utf8');

function browser({ supports = true, documentMode, legacy = false, style = {}, theme = 'windows7', className = '', writeFails = false, url = '/windows7.css' } = {}) {
    const links = [];
    const elements = {
        'site-theme-config': { getAttribute: name => ({ 'data-theme': theme, 'data-theme-css': url })[name] },
        'theme-windows7': { disabled: true },
        'windows7-supported': { value: '' },
        'theme-unsupported': { style: {} },
        'theme-fallback': { style: {} }
    };
    const document = {
        documentMode,
        documentElement: { className },
        getElementById: id => elements[id],
        createElement: tag => tag === 'div' ? { style } : {},
        write: markup => {
            if (writeFails) throw Error('Insertion failed');
            const link = { markup, classAtInsertion: document.documentElement.className };
            elements['windows7-css'] = link;
            links.push(link);
        },
        addEventListener: (name, callback) => callback()
    };
    const window = legacy ? {} : { CSS: { supports: () => supports } };
    vm.runInNewContext(source, { window, document });
    return { links, elements, document };
}

test('supported browser loads Windows 7 and enables selection', () => {
    const result = browser();
    assert.equal(result.links.length, 1);
    assert.match(result.links[0].markup, /href="\/windows7.css"/);
    assert.equal(result.elements['theme-windows7'].disabled, false);
    assert.equal(result.elements['windows7-supported'].value, '1');
    assert.equal(result.document.documentElement.className, 'theme-windows7');
    assert.equal(result.links[0].classAtInsertion, 'theme-windows7');
});

test('unsupported browser never loads saved Windows 7', () => {
    const result = browser({ supports: false });
    assert.equal(result.links.length, 0);
    assert.equal(result.elements['theme-windows7'].disabled, true);
    assert.equal(result.elements['windows7-supported'].value, '');
});

test('IE6 without CSS.supports stays on the base theme', () => {
    const result = browser({ legacy: true });
    assert.equal(result.links.length, 0);
    assert.equal(result.elements['theme-windows7'].disabled, true);
});

test('IE compatibility mode is blocked even if feature detection claims support', () => {
    assert.equal(browser({ documentMode: 7 }).links.length, 0);
});

test('IE11 style assignment fallback can enable Windows 7', () => {
    assert.equal(browser({ legacy: true, documentMode: 11, style: { backgroundSize: '', borderImage: '' } }).links.length, 1);
});

test('partial CSS support does not enable the theme', () => {
    const style = { backgroundSize: '' };
    Object.defineProperty(style, 'borderImage', { get: () => '', set: () => {} });
    assert.equal(browser({ legacy: true, style }).links.length, 0);
});

test('classic themes never load the Windows 7 stylesheet', () => {
    for (const theme of ['classic_light', 'classic_dark']) {
        assert.equal(browser({ theme }).links.length, 0);
    }
});

test('feature detection exceptions fall back safely', () => {
    const style = {};
    Object.defineProperty(style, 'backgroundSize', { get: () => '', set: () => { throw Error('unsupported'); } });
    style.borderImage = '';
    assert.equal(browser({ legacy: true, style }).links.length, 0);
});

test('failed stylesheet restores the base theme and existing classes', () => {
    const result = browser({ className: 'existing-class' });
    assert.equal(result.document.documentElement.className, 'existing-class theme-windows7');
    result.links[0].onerror();
    assert.equal(result.document.documentElement.className, 'existing-class');
});

test('failed stylesheet insertion safely restores the base theme', () => {
    const result = browser({ className: 'existing-class', writeFails: true });
    assert.equal(result.document.documentElement.className, 'existing-class');
    assert.equal(result.links.length, 0);
});

test('stylesheet URL is escaped as an HTML attribute', () => {
    const result = browser({ url: '/theme.css?x=1&value="<tag>"' });
    assert.match(result.links[0].markup, /x=1&amp;value=&quot;&lt;tag&gt;&quot;/);
});
