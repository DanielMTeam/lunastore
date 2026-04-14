function getQueryParam(param) {
    var search = window.location.search.substring(1);
    var vars = search.split("&");
    for (var i = 0; i < vars.length; i++) {
        var pair = vars[i].split("=");
        if (decodeURIComponent(pair[0]) === param) {
            return decodeURIComponent(pair[1]);
        }
    }
    return null;
}

// set limit and read page from URL
var LIMIT = 10;
var currentPage = parseInt(getQueryParam("page")) || 1;

var textNoNew =
    window.PAGE_NOTIFICATIONS_NO_NEW || "У вас нет новых уведомлений";
var textNewCount =
    window.PAGE_NOTIFICATIONS_NEW_COUNT ||
    "У вас <b>{count}</b> новых уведомлений";

// function for update count text
function updateCountText(count) {
    var countElement = document.getElementById("notify-count-text");
    if (!countElement) return;

    if (count === 0) {
        // take from window or default
        countElement.innerHTML =
            window.PAGE_NOTIFICATIONS_NO_NEW || "У вас нет новых уведомлений";
    } else {
        // choose plural form based on count
        var pluralText = ngettext(
            "PAGE_NOTIFICATIONS_COUNT_SINGLE",
            "PAGE_NOTIFICATIONS_COUNT_PLURAL",
            count,
        );

        countElement.innerHTML = interpolate(
            pluralText,
            { counter: count },
            true,
        );
    }
}

// draw notification
function renderNotification(data, isHistory) {
    var isNew = data.ViewedAt === null;
    var meta = data.Meta || {};

    var containerId = isNew ? "list-new" : "list-old";
    var container = document.getElementById(containerId);
    if (!container) return;

    var card = document.createElement("div");
    card.className = "notify_card";
    card.setAttribute("data-id", data.ID);

    var type = meta.type || "normal";
    if (type === "critical" || type === "important") {
        card.id = "ntf_i";
    } else if (isNew) {
        card.id = "ntf_unread";
    }

    var iconSrc = meta.icon || "system.png";
    var iconPath =
        iconSrc.indexOf("/") !== -1
            ? iconSrc
            : "/staticfiles/img/ntficons/" + iconSrc;

    var inner =
        '<div class="notify_ic"><img src="' +
        iconPath +
        '" alt="icon"></div>' +
        '<div class="notify_body">' +
        '<div class="notify_title">' +
        data.Title +
        "</div>" +
        '<div class="notify_desc">' +
        data.Content +
        "</div>";

    if (meta.action_url) {
        var actionText = meta.action_text || "Перейти »";
        inner +=
            '<a href="' +
            meta.action_url +
            '" class="notify_action">' +
            actionText +
            "</a>";
    }

    var timeStr = "только что";
    if (!isNew && data.CreatedAt) {
        var d = new Date(data.CreatedAt * 1000);
        timeStr =
            d.toLocaleDateString() +
            ", " +
            d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    inner +=
        '<div class="notify_time"><small>' + timeStr + "</small></div></div>";
    card.innerHTML = inner;

    // paste card
    if (isHistory) {
        container.appendChild(card);
        container.appendChild(document.createElement("br"));
    } else {
        container.insertBefore(
            document.createElement("br"),
            container.firstChild,
        );
        container.insertBefore(card, container.firstChild);
    }

    if (isNew) {
        card.onclick = function (e) {
            if (e.target.tagName.toLowerCase() === "a") return;

            card.id = "";
            if (typeof markAsRead === "function") {
                markAsRead(data.ID, card);
            }
            card.onclick = null;

            var oldContainer = document.getElementById("list-old");
            if (oldContainer) {
                var newBr = document.createElement("br");
                oldContainer.insertBefore(card, oldContainer.firstChild);
                oldContainer.insertBefore(newBr, oldContainer.firstChild);
            }
        };
    }
}

// load initial notifications
function loadInitialNotifications(token, apiUrl) {
    var url =
        apiUrl +
        "/notifications/list?token=" +
        encodeURIComponent(token) +
        "&limit=" +
        LIMIT +
        "&page=" +
        currentPage;
    var xhr = new XMLHttpRequest();

    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4 && xhr.status === 200) {
            try {
                var response = JSON.parse(xhr.responseText);
                var notifications = response.data || [];

                var unreadTotal = response.total_unread || 0;

                for (var i = 0; i < notifications.length; i++) {
                    renderNotification(notifications[i], true);
                }

                // update local text
                updateCountText(unreadTotal);
            } catch (e) {}
        }
    };
    xhr.send();
}

// long-polling stream
function subscribeToNotifications(token, apiUrl) {
    var url =
        apiUrl +
        "/notifications/stream?token=" +
        encodeURIComponent(token) +
        "&wait=30s";
    var xhr = new XMLHttpRequest();

    xhr.open("GET", url, true);

    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                try {
                    var responseData = JSON.parse(xhr.responseText);

                    // take notification from payload
                    var notification = responseData.payload;

                    if (notification) {
                        // draw only if we are on the first page
                        if (currentPage === 1) {
                            renderNotification(notification, false);
                        }
                        // update text
                        var countElement =
                            document.getElementById("notify-count-text");
                        if (countElement) {
                            // take current count from text and increment
                            var currentCount =
                                parseInt(
                                    countElement.innerText.replace(/\D/g, ""),
                                ) || 0;
                            updateCountText(currentCount + 1);
                        }

                        // update number
                        if (typeof window.updateGlobalCountUI === "function") {
                            var sidebarEl = document.getElementById(
                                "global-unread-count",
                            );
                            var currentSide = sidebarEl
                                ? parseInt(
                                      sidebarEl.innerText.replace(/\D/g, ""),
                                  ) || 0
                                : 0;
                            window.updateGlobalCountUI(currentSide + 1);
                        }
                    }
                } catch (e) {}

                // reconnect
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 2000);
            } else if (xhr.status === 429) {
                // protection from server ban (Too Many Requests)
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 15000);
            } else if (xhr.status === 502 || xhr.status === 504) {
                // timeout, reconnect
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 2000);
            } else {
                // server error
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 5000);
            }
        }
    };

    xhr.onerror = function () {
        setTimeout(function () {
            subscribeToNotifications(token, apiUrl);
        }, 9000);
    };

    xhr.send();
}

// run
(function initNotifications() {
    var tokenMeta = document.getElementById("notify-token-meta");
    var apiMeta = document.getElementById("notify-api-meta");

    if (tokenMeta && apiMeta) {
        var token = tokenMeta.getAttribute("content");
        var apiUrl = apiMeta.getAttribute("content");

        if (token && apiUrl) {
            if (apiUrl.charAt(apiUrl.length - 1) === "/") {
                apiUrl = apiUrl.slice(0, -1);
            }

            // load initial notifications
            loadInitialNotifications(token, apiUrl);

            // listen stream only at first page
            if (currentPage === 1) {
                subscribeToNotifications(token, apiUrl);
            }
        }
    }
})();
