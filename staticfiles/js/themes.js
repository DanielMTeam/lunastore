/* This file runs synchronously in the head, including in legacy IE. */
(function (window, document) {
    var image = 'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")';
    var border = image + ' 30 round';

    function supportsWindows7() {
        try {
            // documentMode catches IE compatibility modes, regardless of user agent.
            if (document.documentMode && document.documentMode < 11) {
                return false;
            }
            if (window.CSS && typeof window.CSS.supports === 'function') {
                return window.CSS.supports('background-size', 'cover') &&
                    window.CSS.supports('border-image', border);
            }
            var style = document.createElement('div').style;
            if (!('backgroundSize' in style) || !('borderImage' in style)) {
                return false;
            }
            style.backgroundSize = 'cover';
            style.borderImage = border;
            return style.backgroundSize === 'cover' &&
                style.borderImage.indexOf('30') !== -1 && style.borderImage.indexOf('round') !== -1;
        } catch (e) {
            return false;
        }
    }

    var supported = supportsWindows7();
    var config = document.getElementById('site-theme-config');
    if (config && config.getAttribute('data-theme') === 'windows7' && supported) {
        var root = document.documentElement;
        var previousClassName = root.className;
        var url = config.getAttribute('data-theme-css');
        var escapedUrl = url.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
            .replace(/</g, '&lt;').replace(/>/g, '&gt;');
        root.className = previousClassName + (previousClassName ? ' ' : '') + 'theme-windows7';
        try {
            // This synchronous head script inserts a parser-created stylesheet so
            // older browsers also wait for its CSS before painting the page.
            document.write('<link rel="stylesheet" id="windows7-css" href="' + escapedUrl + '">');
            var link = document.getElementById('windows7-css');
            if (link) {
                link.onerror = function () {
                    root.className = previousClassName;
                };
            } else {
                root.className = previousClassName;
            }
        } catch (e) {
            root.className = previousClassName;
        }
    }

    function setupSettings() {
        var radio = document.getElementById('theme-windows7');
        if (!radio || !supported) {
            return;
        }
        radio.disabled = false;
        document.getElementById('windows7-supported').value = '1';
        document.getElementById('theme-unsupported').style.display = 'none';
        var fallback = document.getElementById('theme-fallback');
        if (fallback) {
            fallback.style.display = 'none';
        }
    }

    if (document.addEventListener) {
        document.addEventListener('DOMContentLoaded', setupSettings, false);
    } else if (document.attachEvent) {
        document.attachEvent('onreadystatechange', function () {
            if (document.readyState === 'complete') {
                setupSettings();
            }
        });
    }
}(window, document));
