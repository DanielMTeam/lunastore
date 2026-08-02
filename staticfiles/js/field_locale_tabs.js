// switch language tabs for translated form fields (ie6-safe)
function switchFieldLocale(tabElement, langCode) {
  var container = tabElement.parentNode;
  while (container && (!container.className || container.className.indexOf("field-tabs") === -1)) {
    container = container.parentNode;
  }
  if (!container) {
    return;
  }
  var nodes = container.getElementsByTagName("*");
  var i;
  for (i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    if (!el.className) {
      continue;
    }
    var langAttr = null;
    if (el.getAttribute) {
      langAttr = el.getAttribute("data-lang-target") || el.getAttribute("data-lang");
    }
    if (langAttr) {
      el.className = el.className.replace(/\s*active/g, "");
      if (langAttr === langCode) {
        el.className += " active";
      }
    }
    if (el.className.indexOf("lang-field-wrapper") !== -1) {
      el.className = el.className.replace(/\s*active/g, "");
      if (el.className.indexOf("lang-" + langCode) !== -1) {
        el.className += " active";
      }
    }
  }
}