$(document).ready(function () {
  var $interactiveRating = $("#interactive-rating");
  if ($interactiveRating.length === 0) return;
  var currentRating = $interactiveRating.data("current-rating") || "";
  $(".rate-star").hover(function () {
    var r = $(this).data("rating");
    $interactiveRating.removeClass().addClass("rating r" + r).css("cursor", "pointer");
  }, function () {
    $interactiveRating.removeClass().addClass("rating " + currentRating).css("cursor", "pointer");
  });
  $(".rate-star").click(function (e) {
    e.preventDefault();
    var r = $(this).data("rating");
    $("#rating-input").val(r);
    $("#rating-form").submit();
  });
});