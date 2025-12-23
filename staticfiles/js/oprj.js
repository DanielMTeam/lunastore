
var c = document.getElementById('oprj'),
    l = document.getElementById('oprj_list'),
    w = document.getElementById('oprj_layout');

// Показ/скрытие списка — с надёжной блокировкой всплытия
c.onclick = function () {
  // если явно показан как 'block' — скрываем, иначе показываем
  if (l.style.display === 'block') {
    l.style.display = 'none';
  } else {
    l.style.display = 'block';
  }
  // Остановить всплытие в старых IE и вернуть false
  if (window.event) window.event.cancelBubble = true;
  return false;
};

// Обработка выбора и переход по ссылке
l.onclick = function (e) {
  e = e || window.event;
  var t = e.srcElement || e.target;
  if (t && t.className === 'oprj_item') {
    // текст и ссылка
    var txt = t.innerText || t.textContent;
    var href = t.getAttribute('data-h') || '#';
    c.innerText = txt;
    l.style.display = 'none';
    // переход
    window.location.href = href;
  }
  if (window.event) window.event.cancelBubble = true;
  return false;
};

// Скрывать при клике вне блока
document.onclick = function (e) {
  e = e || window.event;
  var t = e.srcElement || e.target;
  // если клик внутри wrapper — ничего не делать
  for (var n = t; n; n = n.parentNode) {
    if (n === w) return;
  }
  l.style.display = 'none';
};