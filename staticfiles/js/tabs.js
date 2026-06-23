(function () {
  function selectTab(tabName) {
    var tabs = document.getElementsByClassName ? document.getElementsByClassName("tab") : document.getElementsByTagName("div"); // IE6 fallback

    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].className && tabs[i].className.indexOf("tab") !== -1) {
        if (tabs[i].getAttribute("data-tab") === tabName) {
          tabs[i].className = "tab active";
        } else if (tabs[i].className.indexOf("tab") !== -1) {
          tabs[i].className = "tab";
        }
      }
    }
    var contents = document.getElementsByTagName("div");
    for (var j = 0; j < contents.length; j++) {
      var id = contents[j].id || "";
      if (id.indexOf("tab-") === 0) {
        contents[j].style.display = id === "tab-" + tabName ? "block" : "none";
      }
    }
  }
  function init() {
    var tabs = document.getElementsByTagName("div");
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].className && tabs[i].className.indexOf("tab") !== -1) {
        if (tabs[i].attachEvent) {
          tabs[i].attachEvent('onclick', function () {
            selectTab(this.getAttribute("data-tab"));
          });
        } else {
          tabs[i].addEventListener('click', function () {
            selectTab(this.getAttribute("data-tab"));
          }, false);
        }
      }
    }
  }
  if (window.attachEvent) {
    window.attachEvent('onload', init);
  } else {
    window.addEventListener('load', init, false);
  }
})();