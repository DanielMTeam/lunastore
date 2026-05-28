function setCookie(name, value, days) {
  var expires = "";
  if (days) {
    var date = new Date();
    date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

// get cookie
function getCookie(name) {
  var nameEQ = name + "=";
  var ca = document.cookie.split(";");
  for (var i = 0; i < ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == " ") c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
}

// there is cookie?
if (navigator.userAgent.indexOf("MSIE ") === -1) {
  if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", function () {
      if (!getCookie("cookie_consent_accepted")) {
        var banner = document.getElementById("cookie-banner");
        if (banner) banner.style.display = "block";
      }
    });
  }
}
function acceptCookies(e) {
  e.preventDefault();
  setCookie("cookie_consent_accepted", "true", 365);
  document.getElementById("cookie-banner").style.display = "none";
}
function closeCookieBanner(e) {
  e.preventDefault();
  document.getElementById("cookie-banner").style.display = "none";
}
function initThemeToggle() {
  if (!window.addEventListener) {
    return;
  }
  var links = document.getElementsByTagName("a");
  for (var i = 0; i < links.length; i++) {
    var href = links[i].getAttribute("href");
    if (href && href.indexOf("/theme_switch.php") !== -1) {
      links[i].onclick = function (e) {
        var event = e || window.event;
        if (event.preventDefault) {
          event.preventDefault();
        } else {
          event.returnValue = false;
        }
        var currentHref = this.getAttribute("href");
        var isTurningOn = currentHref.indexOf("payload=on") !== -1;
        var div = null;
        var children = this.getElementsByTagName("div");
        for (var j = 0; j < children.length; j++) {
          if (children[j].className === "thmsw") {
            div = children[j];
            break;
          }
        }
        if (isTurningOn) {
          setCookie("dark_theme", "on", 365);
          this.setAttribute("href", "/theme_switch.php?payload=off");
          this.setAttribute("alt", "Выключить тёмную тему");
          if (div) div.id = "dark";
          if (!document.getElementById("darkthm-css")) {
            var link = document.createElement("link");
            link.id = "darkthm-css";
            link.rel = "stylesheet";
            link.href = window.DARK_THEME_CSS_URL || "/staticfiles/css/darkthm.css";
            document.getElementsByTagName("head")[0].appendChild(link);
          }
        } else {
          setCookie("dark_theme", "", -1);
          this.setAttribute("href", "/theme_switch.php?payload=on");
          this.setAttribute("alt", "Включить тёмную тему");
          if (div) div.id = "light";
          var darkCss = document.getElementById("darkthm-css");
          if (darkCss) {
            darkCss.parentNode.removeChild(darkCss);
          }
        }
        return false;
      };
    }
  }
}
if (window.addEventListener) {
  window.addEventListener("load", initThemeToggle, false);
} else if (window.attachEvent) {
  window.attachEvent("onload", initThemeToggle);
} else {
  var oldOnload = window.onload;
  window.onload = function () {
    if (oldOnload) oldOnload();
    initThemeToggle();
  };
}