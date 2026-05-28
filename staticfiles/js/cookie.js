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