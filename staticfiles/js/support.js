/* Progressive enhancement: ordinary forms and navigation work without JavaScript. */
(function () {
  function xhr() {
    if (window.XMLHttpRequest) return new XMLHttpRequest();
    try { return new ActiveXObject('Microsoft.XMLHTTP'); } catch (e) { return null; }
  }
  function start() {
    var root = document.getElementById('support-poll');
    if (!root) return;
    var url = root.getAttribute('data-url');
    var revision = root.getAttribute('data-revision');
    var refreshUrl = root.getAttribute('data-refresh-url');
    var notice = document.getElementById('support-updates');
    var error = document.getElementById('support-poll-error');
    var refresh = document.getElementById('support-refresh');
    var currentThread = document.getElementById('support-thread');
    if (currentThread && currentThread.getAttribute('data-scroll-latest') === '1') {
      currentThread.scrollTop = currentThread.scrollHeight;
    }
    var attachmentToggle = document.getElementById('support-attachments-toggle');
    var attachments = document.getElementById('support-attachments');
    if (attachmentToggle && attachments) {
      attachmentToggle.style.display = 'inline';
      var expanded = attachments.getAttribute('data-has-errors') === '1';
      var fileInputs = attachments.getElementsByTagName('input');
      for (var f = 0; f < fileInputs.length; f++) {
        if (fileInputs[f].type === 'file' && fileInputs[f].value) expanded = true;
      }
      attachments.style.display = expanded ? 'block' : 'none';
      attachmentToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      attachmentToggle.onclick = function () {
        var show = attachments.style.display === 'none';
        attachments.style.display = show ? 'block' : 'none';
        attachmentToggle.setAttribute('aria-expanded', show ? 'true' : 'false');
      };
      var attachmentLabel = attachmentToggle.firstChild ? attachmentToggle.firstChild.nodeValue : '';
      function updateAttachmentCount() {
        var count = 0;
        for (var n = 0; n < fileInputs.length; n++) {
          if (fileInputs[n].type === 'file' && fileInputs[n].value) count++;
        }
        if (attachmentToggle.firstChild) {
          attachmentToggle.firstChild.nodeValue = attachmentLabel + (count ? ' (' + count + ')' : '');
        }
      }
      for (var a = 0; a < fileInputs.length; a++) {
        if (fileInputs[a].type === 'file') fileInputs[a].onchange = updateAttachmentCount;
      }
      updateAttachmentCount();
    }
    function updateThread() {
      var request = xhr();
      if (!request) return;
      refresh.disabled = true;
      request.open('GET', refreshUrl, true);
      request.onreadystatechange = function () {
        if (request.readyState !== 4) return;
        refresh.disabled = false;
        if (request.status !== 200) { error.style.display = 'block'; return; }
        // Parse the server-rendered thread only; never replace the reply form or selected files.
        var container = document.createElement('div');
        container.innerHTML = request.responseText;
        var divs = container.getElementsByTagName('div');
        var thread = null;
        var newRevision = revision;
        var summary = null;
        var paragraphs = container.getElementsByTagName('p');
        for (var p = 0; p < paragraphs.length; p++) {
          if (paragraphs[p].id === 'support-ticket-summary') summary = paragraphs[p];
        }
        for (var i = 0; i < divs.length; i++) {
          if (divs[i].id === 'support-thread') thread = divs[i];
          if (divs[i].id === 'support-poll') newRevision = divs[i].getAttribute('data-revision');
        }
        if (thread) {
          var target = document.getElementById('support-thread');
          var followLatest = target.scrollHeight - target.scrollTop - target.clientHeight < 60;
          var oldScroll = target.scrollTop;
          target.innerHTML = thread.innerHTML;
          target.scrollTop = followLatest ? target.scrollHeight : oldScroll;
          revision = newRevision;
          if (summary && document.getElementById('support-ticket-summary')) {
            document.getElementById('support-ticket-summary').innerHTML = summary.innerHTML;
          }
          notice.style.display = 'none';
          error.style.display = 'none';
        } else { error.style.display = 'block'; }
      };
      request.send(null);
    }
    refresh.onclick = updateThread;
    function check() {
      if (typeof document.hidden !== 'undefined' && document.hidden) { window.setTimeout(check, 30000); return; }
      var request = xhr();
      if (!request) return;
      request.open('GET', url, true);
      request.onreadystatechange = function () {
        if (request.readyState !== 4) return;
        if (request.status === 200) {
          // The endpoint returns a single integer, avoiding a JSON polyfill or eval in IE6.
          var match = /"revision"\s*:\s*(\d+)/.exec(request.responseText);
          if (match && match[1] !== revision) notice.style.display = 'block';
          error.style.display = match ? 'none' : 'block';
        } else { error.style.display = 'block'; }
        window.setTimeout(check, 30000);
      };
      request.send(null);
    }
    window.setTimeout(check, 30000);
  }
  if (window.addEventListener) window.addEventListener('load', start, false);
  else if (window.attachEvent) window.attachEvent('onload', start);
}());
