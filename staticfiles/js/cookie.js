function setCookie(name, value, days) {
  var expires = "";
  if (days) {
    var date = new Date();
    date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

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

function cookieById(id) {
  if (document.getElementById) {
    return document.getElementById(id);
  }
  if (document.all) {
    return document.all[id];
  }
  return null;
}

function onDomReady(fn) {
  // Prefer attachEvent first: IE6-10. Never call addEventListener on old IE.
  if (document.attachEvent) {
    document.attachEvent("onreadystatechange", function () {
      if (document.readyState === "complete") {
        fn();
      }
    });
  } else if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", fn, false);
  } else {
    window.onload = fn;
  }
}

onDomReady(function () {
  var banner = cookieById("cookie-banner");
  if (banner && !getCookie("cookie_consent_accepted")) {
    banner.style.display = "block";
  }
});

function acceptCookies(e) {
  e = e || window.event;
  if (e && e.preventDefault) {
    e.preventDefault();
  } else if (e) {
    e.returnValue = false;
  }
  setCookie("cookie_consent_accepted", "true", 365);
  var banner = cookieById("cookie-banner");
  if (banner) {
    banner.style.display = "none";
  }
}

function closeCookieBanner(e) {
  e = e || window.event;
  if (e && e.preventDefault) {
    e.preventDefault();
  } else if (e) {
    e.returnValue = false;
  }
  var banner = cookieById("cookie-banner");
  if (banner) {
    banner.style.display = "none";
  }
}
