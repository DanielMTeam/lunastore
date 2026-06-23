document.addEventListener("DOMContentLoaded", function () {
  var langs = ['ru', 'en', 'uk', 'be', 'kk'];
  function applyTabsToInline(inlineElement) {
    // Find changelog_ru to use as an anchor
    var anchorRow = inlineElement.querySelector('.field-changelog_ru');
    if (!anchorRow) return;

    // Ensure we don't apply twice
    if (anchorRow.parentNode.querySelector('.unfold-inline-tabs')) return;

    // Create tab container
    var tabsContainer = document.createElement('div');
    tabsContainer.className = 'unfold-inline-tabs flex gap-2 mb-4 px-3';

    // Find all lang rows
    var rows = {};
    langs.forEach(function (lang) {
      var row = inlineElement.querySelector(".field-changelog_".concat(lang));
      if (row) {
        rows[lang] = row;
        row.style.display = 'none'; // hide initially
      }
    });

    // Create tabs
    langs.forEach(function (lang, idx) {
      if (!rows[lang]) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = lang;
      btn.className = 'px-3 py-1 rounded-md text-sm font-medium transition-colors border border-transparent';
      var setInactive = function setInactive() {
        btn.classList.remove('bg-gray-800', 'text-white', 'dark:bg-gray-200', 'dark:text-gray-900');
        btn.classList.add('bg-gray-100', 'text-gray-600', 'dark:bg-gray-800', 'dark:text-gray-300', 'hover:bg-gray-200', 'dark:hover:bg-gray-700');
        rows[lang].style.display = 'none';
      };
      var setActive = function setActive() {
        btn.classList.remove('bg-gray-100', 'text-gray-600', 'dark:bg-gray-800', 'dark:text-gray-300', 'hover:bg-gray-200', 'dark:hover:bg-gray-700');
        btn.classList.add('bg-gray-800', 'text-white', 'dark:bg-gray-200', 'dark:text-gray-900');
        rows[lang].style.display = '';
      };
      if (idx === 0) {
        setActive(); // show default
      } else {
        setInactive();
      }
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        // set all to inactive
        langs.forEach(function (l) {
          var otherBtn = tabsContainer.querySelector("[data-lang=\"".concat(l, "\"]"));
          if (otherBtn) {
            otherBtn.setInactive();
          }
        });
        // set current to active
        setActive();
      });
      btn.setAttribute('data-lang', lang);
      btn.setInactive = setInactive; // save ref for click handler
      tabsContainer.appendChild(btn);
    });

    // Insert tabs above the first row
    anchorRow.parentNode.insertBefore(tabsContainer, anchorRow);
  }

  // Apply to existing inlines
  var inlines = document.querySelectorAll('.inline-related');
  inlines.forEach(applyTabsToInline);

  // Handle dynamically added inlines using MutationObserver
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType === 1 && node.classList && node.classList.contains('inline-related')) {
          applyTabsToInline(node);
        }
      });
    });
  });
  var inlineGroups = document.querySelectorAll('.inline-group');
  inlineGroups.forEach(function (group) {
    observer.observe(group, {
      childList: true,
      subtree: true
    });
  });
});