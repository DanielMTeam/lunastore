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
    var isNew =
        data.ViewedAt === null ||
        data.ViewedAt === undefined ||
        data.ViewedAt === 0;
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

    var notif_title = window.notifs[data.Title] || data.Title
    var notif_content = window.notifs[data.Content] || data.Content

    var inner =
        '<div class="notify_ic"><img src="' +
        iconPath +
        '" alt="icon"></div>' +
        '<div class="notify_body">' +
        '<div class="notify_title">' +
        notif_title +
        "</div>" +
        '<div class="notify_desc">' +
        notif_content +
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

    var timeStr = ngettext("PAGE_NOTIFICATIONS_NOW");
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
}

function markAllAsRead(ids, token, apiUrl) {
    var url =
        apiUrl.replace(/\/$/, "") +
        "/notifications/read-mark?token=" +
        encodeURIComponent(token);

    ids.forEach(function (id) {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", url, true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify({ id: id }));
    });
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
                var newIds = [];

                for (var i = 0; i < notifications.length; i++) {
                    var item = notifications[i];
                    renderNotification(item, true);

                    // if ViewedAt is null or undefined or 0, mark as new
                    if (
                        item.ViewedAt === null ||
                        item.ViewedAt === undefined ||
                        item.ViewedAt === 0
                    ) {
                        newIds.push(item.ID);
                    }
                }

                // send signal to mark all as read
                if (newIds.length > 0) {
                    markAllAsRead(newIds, token, apiUrl);

                    // immediately reset counters, as the list is before the eyes
                    setTimeout(function () {
                        updateCountText(0);
                        if (typeof window.updateGlobalCountUI === "function") {
                            window.updateGlobalCountUI(0);
                        }
                    }, 500);
                } else {
                    updateCountText(response.total_unread || 0);
                }
            } catch (e) {
                console.error("Ошибка парсинга:", e);
            }
        }
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
        }
    }
})();
