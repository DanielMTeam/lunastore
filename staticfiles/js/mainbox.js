/* 
    Данный черновой файл написан с использованием ИИ, поскольку я не умею работать с JS 
    Честность - превыше всего!

*/

function showDialog() {
  var dlg = document.getElementById("dialog");
  var scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
  var scrollLeft = document.documentElement.scrollLeft || document.body.scrollLeft;
  dlg.style.left = scrollLeft + 120 + "px";
  dlg.style.top = scrollTop + 120 + "px";
  dlg.style.display = "block";
}
function hideDialog() {
  document.getElementById("dialog").style.display = "none";
}