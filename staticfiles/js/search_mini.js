function doSearch() {
  var q = document.getElementById("q").value.toLowerCase();
  var cards = document.getElementsByTagName("div");
  for (var i=0;i<cards.length;i++) {
    if(cards[i].className=="card") {
      var text = cards[i].innerText || cards[i].textContent;
      if(text.toLowerCase().indexOf(q)!=-1) {
        cards[i].style.display="block";
      } else {
        cards[i].style.display="none";
      }
    }
  }
}