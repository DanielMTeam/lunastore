(function () {
  if (typeof JSON === "undefined") {
    window.JSON = {};
  }
  if (typeof JSON.parse !== "function") {
    JSON.parse = function (text) {
      return eval("(" + text + ")");
    };
  }

  var debounceTimer = null;
  var activeRequest = null;
  var MIN_QUERY_LENGTH = 2;
  var DEBOUNCE_MS = 300;
  var hiddenSelects = [];

  function needsSelectFix() {
    if (window.opera || !document.all) {
      return false;
    }
    if (!window.XMLHttpRequest) {
      return true;
    }
    if (document.documentMode && document.documentMode < 8) {
      return true;
    }
    return false;
  }

  function hidePageSelects() {
    if (!needsSelectFix()) {
      return;
    }
    hiddenSelects = [];
    var selects = document.getElementsByTagName("select");
    var i;
    for (i = 0; i < selects.length; i++) {
      hiddenSelects.push({
        node: selects[i],
        visibility: selects[i].style.visibility
      });
      selects[i].style.visibility = "hidden";
    }
  }

  function restorePageSelects() {
    var i;
    for (i = 0; i < hiddenSelects.length; i++) {
      hiddenSelects[i].node.style.visibility = hiddenSelects[i].visibility;
    }
    hiddenSelects = [];
  }

  function getIframeShim(dropdown) {
    var wrap = dropdown.parentNode;
    if (!wrap) {
      return null;
    }
    var nodes = wrap.getElementsByTagName("iframe");
    var i;
    for (i = 0; i < nodes.length; i++) {
      if (nodes[i].className && nodes[i].className.indexOf("search_suggest_shim") !== -1) {
        return nodes[i];
      }
    }
    var shim = document.createElement("iframe");
    shim.className = "search_suggest_shim";
    shim.setAttribute("frameborder", "0");
    shim.setAttribute("tabindex", "-1");
    shim.setAttribute("src", "javascript:false;");
    wrap.insertBefore(shim, dropdown);
    return shim;
  }

  function syncIframeShim(dropdown) {
    if (!needsSelectFix() || !dropdown) {
      return;
    }
    var shim = getIframeShim(dropdown);
    if (!shim) {
      return;
    }
    shim.style.left = dropdown.style.left || "0";
    shim.style.top = dropdown.style.top || "100%";
    shim.style.width = dropdown.offsetWidth + "px";
    shim.style.height = dropdown.offsetHeight + "px";
    shim.style.display = "block";
  }

  function getOffsetWithinWrap(element, wrap) {
    var left = 0;
    var top = 0;
    var node = element;
    while (node && node !== wrap) {
      left += node.offsetLeft || 0;
      top += node.offsetTop || 0;
      node = node.parentNode;
    }
    return { left: left, top: top };
  }

  function getSuggestWidth(input, wrap) {
    var width = input.offsetWidth || 0;
    var node = input.nextSibling;
    while (node) {
      if (node.nodeType === 1) {
        if (node.className && node.className.indexOf("search_suggest_dropdown") !== -1) {
          break;
        }
        if (
          node.tagName &&
          (node.tagName.toLowerCase() === "button" || node.tagName.toLowerCase() === "input")
        ) {
          width += (node.offsetWidth || 0) + 2;
        }
      }
      node = node.nextSibling;
    }
    if (wrap && wrap.className && wrap.className.indexOf("searchbar") !== -1) {
      return Math.max(width, 260);
    }
    return width;
  }

  function positionSuggestDropdown(input, dropdown) {
    if (!needsSelectFix() || !input || !dropdown) {
      return;
    }
    var wrap = getSuggestWrap(input);
    if (!wrap) {
      return;
    }
    var pos = getOffsetWithinWrap(input, wrap);
    dropdown.style.left = pos.left + "px";
    dropdown.style.top = pos.top + (input.offsetHeight || 22) + "px";
    dropdown.style.width = getSuggestWidth(input, wrap) + "px";
  }

  function resetSuggestDropdown(dropdown) {
    if (!dropdown) {
      return;
    }
    dropdown.style.left = "";
    dropdown.style.top = "";
    dropdown.style.width = "";
  }

  function setSuggestOpen(input, open) {
    var wrap = getSuggestWrap(input);
    if (!wrap) {
      return;
    }
    if (open) {
      if (wrap.className.indexOf("search_suggest_open") === -1) {
        wrap.className += " search_suggest_open";
      }
    } else {
      wrap.className = wrap.className.replace(/\s*search_suggest_open/g, "");
    }
  }

  function hideIframeShim(dropdown) {
    if (!dropdown) {
      return;
    }
    var wrap = dropdown.parentNode;
    if (!wrap) {
      return;
    }
    var nodes = wrap.getElementsByTagName("iframe");
    var i;
    for (i = 0; i < nodes.length; i++) {
      if (nodes[i].className && nodes[i].className.indexOf("search_suggest_shim") !== -1) {
        nodes[i].style.display = "none";
      }
    }
  }

  function escapeHtml(text) {
    if (!text) {
      return "";
    }
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function createXHR() {
    if (window.XMLHttpRequest) {
      return new XMLHttpRequest();
    }
    try {
      return new ActiveXObject("Microsoft.XMLHTTP");
    } catch (e) {
      return null;
    }
  }

  function getSuggestWrap(input) {
    var node = input;
    while (node) {
      if (node.className && node.className.indexOf("search_suggest_wrap") !== -1) {
        return node;
      }
      node = node.parentNode;
    }
    return input.parentNode;
  }

  function getDropdown(input) {
    var wrap = getSuggestWrap(input);
    if (!wrap) {
      return null;
    }
    var dropdown = wrap.getElementsByTagName("div");
    for (var i = 0; i < dropdown.length; i++) {
      if (dropdown[i].className && dropdown[i].className.indexOf("search_suggest_dropdown") !== -1) {
        return dropdown[i];
      }
    }
    return null;
  }

  function hideDropdown(input) {
    var dropdown = getDropdown(input);
    if (dropdown) {
      dropdown.style.display = "none";
      dropdown.innerHTML = "";
      resetSuggestDropdown(dropdown);
      hideIframeShim(dropdown);
    }
    setSuggestOpen(input, false);
    restorePageSelects();
  }

  function renderSection(title, items, renderItem) {
    if (!items || !items.length) {
      return "";
    }
    var html = '<div class="search_suggest_section">';
    html += '<div class="search_suggest_section_title">' + escapeHtml(title) + "</div>";
    for (var i = 0; i < items.length; i++) {
      html += renderItem(items[i]);
    }
    html += "</div>";
    return html;
  }

  function renderSuggestItem(url, icon, label) {
    var fallbackIcon = "/staticfiles/img/noavatar_64.jpg";
    return (
      '<a class="search_suggest_item" href="' +
      escapeHtml(url) +
      '">' +
      '<img src="' +
      escapeHtml(icon || fallbackIcon) +
      '" width="24" height="24" alt="" class="search_suggest_icon png-fix">' +
      '<span class="search_suggest_text">' +
      escapeHtml(label) +
      "</span></a>"
    );
  }

  function renderAppItem(item) {
    return renderSuggestItem(item.url, item.icon_url, item.title);
  }

  function renderUserItem(item) {
    return renderSuggestItem(item.url, item.avatar_url, item.username);
  }

  function showSuggestions(input, data) {
    var dropdown = getDropdown(input);
    if (!dropdown) {
      return;
    }

    var searchType = window.SEARCH_SUGGEST_TYPE || "all";
    var appsLabel = window.SEARCH_SUGGEST_LABEL_APPS || "Applications";
    var usersLabel = window.SEARCH_SUGGEST_LABEL_USERS || "Users";
    var html = "";

    if (searchType === "all" || searchType === "apps") {
      html += renderSection(appsLabel, data.apps, renderAppItem);
    }
    if (searchType === "all" || searchType === "users") {
      html += renderSection(usersLabel, data.users, renderUserItem);
    }

    if (!html) {
      hideDropdown(input);
      return;
    }

    dropdown.innerHTML = html;
    dropdown.style.display = "block";
    setSuggestOpen(input, true);
    positionSuggestDropdown(input, dropdown);
    hidePageSelects();
    syncIframeShim(dropdown);

    if (window.DD_belatedPNG) {
      DD_belatedPNG.fix(".search_suggest_icon");
    }
  }

  function fetchSuggestions(input) {
    var query = input.value.replace(/^\s+|\s+$/g, "");
    if (query.length < MIN_QUERY_LENGTH) {
      hideDropdown(input);
      return;
    }

    var suggestUrl = window.SEARCH_SUGGEST_URL || "/search.php?mode=suggest";
    var searchType = window.SEARCH_SUGGEST_TYPE || "all";
    var sep = suggestUrl.indexOf("?") === -1 ? "?" : "&";
    var url =
      suggestUrl +
      sep +
      "q=" +
      encodeURIComponent(query) +
      "&type=" +
      encodeURIComponent(searchType) +
      "&limit=8";

    if (activeRequest) {
      try {
        activeRequest.onreadystatechange = null;
        activeRequest.abort();
      } catch (ignore) {}
    }

    var xhr = createXHR();
    if (!xhr) {
      return;
    }
    activeRequest = xhr;

    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) {
        return;
      }
      activeRequest = null;
      if (xhr.status !== 200) {
        hideDropdown(input);
        return;
      }
      try {
        var data = JSON.parse(xhr.responseText);
        showSuggestions(input, data);
      } catch (e) {
        hideDropdown(input);
      }
    };
    xhr.send(null);
  }

  function scheduleFetch(input) {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(function () {
      fetchSuggestions(input);
    }, DEBOUNCE_MS);
  }

  function bindInput(input) {
    if (!input || input.getAttribute("data-suggest-bound") === "1") {
      return;
    }
    input.setAttribute("data-suggest-bound", "1");

    if (input.attachEvent) {
      input.attachEvent("onkeyup", function () {
        scheduleFetch(input);
      });
      input.attachEvent("onkeydown", function (evt) {
        evt = evt || window.event;
        if (evt.keyCode === 27) {
          hideDropdown(input);
        }
      });
      input.attachEvent("onblur", function () {
        setTimeout(function () {
          hideDropdown(input);
        }, 200);
      });
    } else {
      input.addEventListener("keyup", function () {
        scheduleFetch(input);
      });
      input.addEventListener("keydown", function (evt) {
        if (evt.keyCode === 27) {
          hideDropdown(input);
        }
      });
      input.addEventListener("blur", function () {
        setTimeout(function () {
          hideDropdown(input);
        }, 200);
      });
    }
  }

  function initSearchSuggest() {
    var inputs = document.getElementsByTagName("input");
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].className && inputs[i].className.indexOf("search_suggest_input") !== -1) {
        bindInput(inputs[i]);
      }
    }
  }

  if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", initSearchSuggest);
  } else if (document.attachEvent) {
    document.attachEvent("onreadystatechange", function () {
      if (document.readyState === "complete") {
        initSearchSuggest();
      }
    });
  } else {
    window.onload = initSearchSuggest;
  }
})();
