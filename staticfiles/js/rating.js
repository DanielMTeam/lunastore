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
    currentRating = "r" + r;
    $interactiveRating.data("current-rating", currentRating);
    $interactiveRating.removeClass().addClass("rating " + currentRating).css("cursor", "pointer");
  });
  $("#rating-form").submit(function (e) {
    var val = $("#rating-input").val();
    if (!val || parseInt(val, 10) < 1 || parseInt(val, 10) > 5) {
      e.preventDefault();
      alert("Пожалуйста, поставьте оценку (1-5 звезд)");
      return false;
    }
  });
});

window.deleteReview = function (id) {
  if (confirm("Вы уверены, что хотите удалить этот отзыв?")) {
    var form = document.getElementById("delete-review-form-" + id);
    if (form) {
      form.submit();
    }
  }
};

window.deleteReviewReply = function (id) {
  if (confirm("Вы уверены, что хотите удалить ответ разработчика?")) {
    var form = document.getElementById("delete-reply-form-" + id);
    if (form) {
      form.submit();
    }
  }
};

window.toggleReplyForm = function (id) {
  var $el = $("#reply-form-" + id);
  if ($el.length) {
    $el.toggle();
    if ($el.is(":visible")) {
      $el.find("textarea").focus();
    }
  }
};

window.toggleEditReplyForm = function (id) {
  var $el = $("#edit-reply-form-" + id);
  if ($el.length) {
    $el.toggle();
    if ($el.is(":visible")) {
      $el.find("textarea").focus();
    }
  }
};

window.editReview = function (rating, text) {
  var $input = $("#rating-input");
  var $interactive = $("#interactive-rating");
  var $textarea = $("#review-text-input");
  if ($input.length) {
    $input.val(rating);
  }
  if ($interactive.length) {
    var cr = "r" + rating;
    $interactive.data("current-rating", cr);
    $interactive.removeClass().addClass("rating " + cr);
  }
  if ($textarea.length) {
    $textarea.val(text).focus();
  }
  var $form = $("#rating-form");
  if ($form.length) {
    $("html, body").animate(
      {
        scrollTop: $form.offset().top - 20
      },
      200
    );
  }
};