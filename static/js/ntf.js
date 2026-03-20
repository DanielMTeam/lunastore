(function () {
    function getOffset(el) {
        var x = 0,
            y = 0;
        while (el && !isNaN(el.offsetLeft) && !isNaN(el.offsetTop)) {
            x += el.offsetLeft;
            y += el.offsetTop;
            el = el.offsetParent;
        }
        return { left: x, top: y };
    }

    function showPopup() {
        var link = document.getElementById("login-link");
        var popup = document.getElementById("login-popup");
        if (!link || !popup) return;
        var pos = getOffset(link);

        popup.style.left = pos.left + "px";
        popup.style.top = pos.top + link.offsetHeight + 10 + "px";
        popup.style.display = "block";
    }

    function hidePopup() {
        var popup = document.getElementById("login-popup");
        if (popup) popup.style.display = "none";
    }

    function togglePopup(e) {
        if (!e) e = window.event;
        var popup = document.getElementById("login-popup");
        if (!popup) return true;

        if (popup.style.display === "block") {
            hidePopup();
        } else {
            showPopup();
        }
        if (e.preventDefault) e.preventDefault();
        else e.returnValue = false;
        return false;
    }

    function init() {
        var link = document.getElementById("login-link");
        var popup = document.getElementById("login-popup");
        var form = document.getElementById("login-form");

        if (!link || !popup) {
            return;
        }

        if (link.attachEvent) {
            link.attachEvent("onclick", togglePopup); // для IE6
        } else {
            link.addEventListener("click", togglePopup, false);
        }

        if (document.attachEvent) {
            document.attachEvent("onclick", function (e) {
                var target = e ? e.srcElement : window.event.srcElement;
                if (
                    popup.style.display === "block" &&
                    target.id !== "login-link" &&
                    !popup.contains(target)
                ) {
                    hidePopup();
                }
            });
        } else {
            document.addEventListener(
                "click",
                function (e) {
                    if (
                        popup.style.display === "block" &&
                        e.target.id !== "login-link" &&
                        !popup.contains(e.target)
                    ) {
                        hidePopup();
                    }
                },
                false,
            );
        }

        // обработчик формы входа
        if (form) {
            if (form.attachEvent) {
                form.attachEvent("onsubmit", function () {
                    return submitLogin(form);
                });
            } else {
                form.addEventListener(
                    "submit",
                    function (e) {
                        if (e.preventDefault) e.preventDefault();
                        return submitLogin(form);
                    },
                    false,
                );
            }
        }
    }

    function submitLogin(form) {
        var login = form.login.value;
        var password = form.password.value;
        alert("Логин: " + login + "\nПароль: " + password);
        hidePopup();
        return false;
    }

    if (window.attachEvent) {
        window.attachEvent("onload", init);
    } else {
        window.addEventListener("load", init, false);
    }
})();
