function insertTag(btn, openTag, closeTag) {
  var elem = btn.parentNode.nextElementSibling;
  elem.focus();
  if (typeof document.selection !== 'undefined') {
    // IE support
    var sel = document.selection.createRange();
    sel.text = openTag + sel.text + closeTag;
    sel.select();
  } else if (typeof elem.selectionStart !== 'undefined') {
    // Standard support
    var startPos = elem.selectionStart;
    var endPos = elem.selectionEnd;
    var selectedText = elem.value.substring(startPos, endPos);
    elem.value = elem.value.substring(0, startPos) + openTag + selectedText + closeTag + elem.value.substring(endPos, elem.value.length);
    if (selectedText.length == 0) {
      elem.selectionStart = startPos + openTag.length;
      elem.selectionEnd = startPos + openTag.length;
    } else {
      elem.selectionStart = startPos + openTag.length;
      elem.selectionEnd = endPos + openTag.length;
    }
  } else {
    elem.value += openTag + closeTag;
  }
}