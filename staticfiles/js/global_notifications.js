// global notification handler for authenticated users
// requires: django javascript-catalog loaded before this script

window.updateCountUI = function (count) {
  var el = document.getElementById("global-unread-count");
  if (el) {
    if (count > 0) {
      el.innerHTML = "(" + count + ")";
      el.style.display = "inline";
    } else {
      el.style.display = "none";
    }
  }
};
function loadNotificationLang() {
  var allTranslations = django.catalog;
  var keys = Object.keys(allTranslations);
  var notifications = {};
  for (var i = 0; i < keys.length; i++) {
    if (keys[i].indexOf('NOTIF_') === 0) {
      notifications[keys[i]] = django.gettext(keys[i]);
    }
  }
  window.notifs = notifications;
}
function playBalloonSnd() {
  var soundUrl = "/staticfiles/snd/balloon.mp3";
  if (window.Audio || typeof Audio !== "undefined") {
    try {
      var modernAudio = new Audio(soundUrl);
      modernAudio.play();
    } catch (e) {
      if (typeof console !== "undefined" && console.error) {
        console.error(e);
      }
    }
  } else {
    var container = document.getElementById('audio-placeholder');
    if (!container) {
      container = document.createElement('div');
      container.id = 'audio-placeholder';
      container.style.display = 'none';
      document.body.appendChild(container);
    }
    container.innerHTML = '<embed src="' + soundUrl + '" ' + 'autostart="true" ' + 'hidden="true" ' + 'loop="false" ' + 'mastersound>';
  }
}
function createNotification(title, message) {
  var container = document.getElementById('notifications');
  if (!container) return;
  var i18n = window.NOTIFY_I18N || {};
  var balloon = document.createElement('div');
  balloon.className = 'balloon';
  var li = document.createElement('li');
  li.className = 'balloon_img';
  balloon.appendChild(li);
  var bTitle = document.createElement('div');
  bTitle.className = 'balloon_title';
  bTitle.innerHTML = i18n.toastNew || "New notification";
  balloon.appendChild(bTitle);
  var nTitle = document.createElement('div');
  nTitle.className = 'notify_title';
  nTitle.innerHTML = window.notifs[title] || title;
  balloon.appendChild(nTitle);
  var bText = document.createElement('div');
  bText.className = 'balloon_text';
  bText.innerHTML = window.notifs[message] || message;
  balloon.appendChild(bText);
  var closeLink = document.createElement('a');
  closeLink.href = '#';
  closeLink.className = 'balloon_link';
  closeLink.innerHTML = i18n.toastClose || "Close";
  closeLink.onclick = function () {
    container.removeChild(balloon);
    return false;
  };
  var viewLink = document.createElement('a');
  viewLink.href = '/notifications.php';
  viewLink.className = 'balloon_link';
  viewLink.innerHTML = i18n.toastView || "View";
  balloon.appendChild(closeLink);
  balloon.appendChild(document.createTextNode(' | '));
  balloon.appendChild(viewLink);
  container.appendChild(balloon);
  playBalloonSnd();
}
function fetchUnreadCount() {
  var tokenEl = document.getElementById("global-notify-token");
  var apiEl = document.getElementById("global-api-url");
  if (!tokenEl || !apiEl) return;
  var token = tokenEl.getAttribute("content");
  var apiUrl = apiEl.getAttribute("content");
  if (apiUrl.indexOf('http') !== 0) apiUrl = 'http://' + apiUrl;
  var xhr = new XMLHttpRequest();
  // back limit=1
  xhr.open("GET", apiUrl + "/notifications/list?token=" + encodeURIComponent(token) + "&limit=1", true);
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4 && xhr.status === 200) {
      try {
        var response = JSON.parse(xhr.responseText);
        var unreadCount = response.total_unread || 0;
        window.updateCountUI(unreadCount);
      } catch (e) {}
    }
  };
  xhr.send();
}
function incrementUnreadCount() {
  var el = document.getElementById("global-unread-count");
  if (el) {
    var current_count = Number(el.innerHTML.replace("(", "").replace(")", ""));
    if (current_count > 0) {
      el.innerHTML = "(" + (current_count + 1) + ")";
      el.style.display = "inline";
    } else {
      el.style.display = "none";
    }
  }
}

// live update via stream (longpull)
function subscribeToGlobalStream() {
  var tokenEl = document.getElementById("global-notify-token");
  var apiEl = document.getElementById("global-api-url");
  if (!tokenEl || !apiEl) return;
  var token = tokenEl.getAttribute("content");
  var apiUrl = apiEl.getAttribute("content");
  if (apiUrl.indexOf('http') !== 0) apiUrl = 'http://' + apiUrl;
  var xhr = new XMLHttpRequest();
  xhr.open("GET", apiUrl + "/notifications/stream?token=" + encodeURIComponent(token) + "&wait=20s", true);
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        var data = eval('(' + xhr.response + ')');
        createNotification(data.payload.Title, data.payload.Content);
        incrementUnreadCount();
        subscribeToGlobalStream();
      } else if (xhr.status === 204 || xhr.status === 429 || xhr.status === 0) {
        setTimeout(subscribeToGlobalStream, 3000);
      } else {
        if (typeof console !== "undefined" && console.error) {
          console.error("subscribeToGlobalStream | Unexpected status:", xhr.status, xhr.responseText);
        }
      }
    }
  };
  xhr.send();
}
(function () {
  loadNotificationLang();
  if (window.location.pathname.indexOf('notifications') === -1) {
    fetchUnreadCount();
    subscribeToGlobalStream();
  }
})();