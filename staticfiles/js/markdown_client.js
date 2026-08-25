function alertRepl(_, p1, p2) {
  var i18n = window.MD_ALERT_I18N || {};
  var alertType = p1.toLowerCase();
  var content = p2.replace(/^&gt; ?/gm, '');

  // old browsers don't have String.prototype.trim
  content = content.replace(/^\s+|\s+$/g, '');
  var displayType = "";
  switch (alertType) {
    case "note":
      displayType = i18n.alertNote || "Note";
      break;
    case "tip":
      displayType = i18n.alertTip || "Tip";
      break;
    case "important":
      displayType = i18n.alertImportant || "Important";
      break;
    case "warning":
      displayType = i18n.alertWarning || "Warning";
      break;
    case "caution":
      displayType = i18n.alertCaution || "Caution";
      break;
    default:
      // capitalize
      displayType = alertType.charAt(0).toUpperCase() + alertType.slice(1);
      break;
  }
  return '<div class="md-alert md-alert-' + alertType + '"><strong>' + displayType + '</strong><br>' + content + '</div>';
}
function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function mdToHtml(source) {
  var output = escapeHtml(source);

  // Bold
  output = output.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');

  // Italic
  output = output.replace(/\*(.*?)\*/g, '<i>$1</i>');

  // GFM alerts
  output = output.replace(/^&gt; \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\r?\n((?:&gt;.*\r?\n?)*)/gm, alertRepl);

  // Replace newlines with <br>
  output = output.replace(/\r?\n/g, '<br>');
  return output;
}