(function () {
  function getOffset(el) {
    var x = 0, y = 0;
    while (el && !isNaN(el.offsetLeft) && !isNaN(el.offsetTop)) {
      x += el.offsetLeft;
      y += el.offsetTop;
      el = el.offsetParent;
    }
    return { left: x, top: y };
  }

  function showPopup() {
    var link = document.getElementById('login-link');
    var popup = document.getElementById('login-popup');
    var pos = getOffset(link);

    popup.style.left = pos.left + "px";
    popup.style.top = (pos.top + link.offsetHeight + 10) + "px";
    popup.style.display = "block";
  }

  function hidePopup() {
    var popup = document.getElementById('login-popup');
    popup.style.display = "none";
  }

  function togglePopup(e) {
    if (!e) e = window.event;
    var popup = document.getElementById('login-popup');
    if (popup.style.display === "block") {
      hidePopup();
    } else {
      showPopup();
    }
    if (e.preventDefault) e.preventDefault(); else e.returnValue = false;
    return false;
  }

  function init() {
    var link = document.getElementById('login-link');
    if (link.attachEvent) {
      link.attachEvent('onclick', togglePopup); // для IE6
    } else {
      link.addEventListener('click', togglePopup, false);
    }

    // скрыть при клике вне окна
    if (document.attachEvent) {
      document.attachEvent('onclick', function (e) {
        var target = e ? e.srcElement : window.event.srcElement;
        var popup = document.getElementById('login-popup');
        if (popup.style.display === "block" && target.id !== "login-link" && !popup.contains(target)) {
          hidePopup();
        }
      });
    } else {
      document.addEventListener('click', function (e) {
        var popup = document.getElementById('login-popup');
        if (popup.style.display === "block" && e.target.id !== "login-link" && !popup.contains(e.target)) {
          hidePopup();
        }
      }, false);
    }

    // обработчик формы входа
    var form = document.getElementById('login-form');
    if (form.attachEvent) {
      form.attachEvent('onsubmit', function () { return submitLogin(form); });
    } else {
      form.addEventListener('submit', function (e) {
        if (e.preventDefault) e.preventDefault();
        return submitLogin(form);
      }, false);
    }
  }

  function submitLogin(form) {
    var login = form.login.value;
    var password = form.password.value;

    var csrf_token = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
    var url = '/login.php';
    var error_div = document.getElementById('login-form-errors');

    if (error_div) error_div.innerHTML = '';

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token
      },
      body: JSON.stringify
      (
        {'username': login, 
        'password': password}
      )
    }
    ).then(response => response.json().then(data => ({ok: response.ok, data}))) 
    .then(result => {
      if (result.ok) {
      hidePopup();
      window.location.reload();
    } else {
      if (error_div) {
        error_div.innerHTML = '<p>${result.data.errors}</p>';
      } 
      else {
        alert(result.data.errors);
      } 
    }}).catch(error => {
      console.error('Login request failed:', error);
      if (error_div) {
        error_div.innerHTML = '<p>Произошла ошибка при отправке запроса.</p>';
    }});
    // тут можно отправить на сервер (через XMLHttpRequest)
    // а пока просто показываем alert
    //alert("Логин: " + login + "\nПароль: " + password);

    //hidePopup();
    //return false; // не отправлять форму по умолчанию
  }

  if (window.attachEvent) {
    window.attachEvent('onload', init);
  } else {
    window.addEventListener('load', init, false);
  }
})();