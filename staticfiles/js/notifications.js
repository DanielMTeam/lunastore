// appendMode: true - add to end (for history), false - add to beginning (for new)
function renderNotification(data, appendMode) {
    var container = document.getElementById("notifications-list-container");
    if (!container) return;

    // check status: if ViewedAt is null, then the notification is new
    var isNew = data.ViewedAt === null;

    var card = document.createElement("div");
    card.className = isNew ? "notify_card unread" : "notify_card";

    if (data.ID) {
        card.setAttribute("data-id", data.ID);
    }

    // use data.Meta
    var iconSrc = data.Meta && data.Meta.icon ? data.Meta.icon : "system.png";

    // use data.Title and data.Content
    card.innerHTML =
        '<div class="notify_ic"><img src="/static/img/ntficons/' +
        iconSrc +
        '" alt="icon"></div>' +
        '<div class="notify_body">' +
        '<div class="notify_title">' +
        data.Title +
        "</div>" +
        '<div class="notify_desc">' +
        data.Content +
        "</div>" +
        '<div class="notify_time"><small>только что</small></div>' +
        "</div>";

    if (appendMode) {
        container.appendChild(card);
        container.appendChild(document.createElement("br"));
    } else {
        container.insertBefore(
            document.createElement("br"),
            container.firstChild,
        );
        container.insertBefore(card, container.firstChild);
    }

    if (isNew && data.ID) {
        card.onclick = function () {
            markAsRead(data.ID, card);
        };
    }
}

// get initial notifications
function loadInitialNotifications(token, apiUrl) {
    var url =
        apiUrl +
        "/notifications/list?token=" +
        encodeURIComponent(token) +
        "&limit=20&page=1";
    var xhr = new XMLHttpRequest();

    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4 && xhr.status === 200) {
            try {
                var response = JSON.parse(xhr.responseText);

                // read data
                var notifications = response.data || [];
                var totalCount = response.total || 0;

                // update notification count
                var countElement = document.getElementById("notify-count-text");
                if (countElement) {
                    if (totalCount === 0) {
                        countElement.innerHTML = "Нет новых уведомлений";
                    } else {
                        countElement.innerHTML =
                            "У вас " + totalCount + " уведомлений";
                    }
                }

                // draw historical notifications
                for (var i = 0; i < notifications.length; i++) {
                    renderNotification(notifications[i], true);
                }
            } catch (e) {
                // :-)
            }
        }
    };
    xhr.send();
}

// long-polling
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
                    var data = JSON.parse(xhr.responseText);

                    // show new notification
                    renderNotification(data, false);

                    // update notification count
                    var countElement =
                        document.getElementById("notify-count-text");
                    if (
                        countElement &&
                        countElement.innerHTML !== "Загрузка уведомлений..."
                    ) {
                        var currentText = countElement.innerHTML;
                        var currentCount =
                            parseInt(currentText.replace(/\D/g, "")) || 0;
                        countElement.innerHTML =
                            "У вас " + (currentCount + 1) + " уведомлений";
                    }
                } catch (e) {}

                // reconnect
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 100);
            } else if (xhr.status === 502 || xhr.status === 504) {
                // timeout, reconnect
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 100);
            } else {
                // network or server error, wait before retrying
                setTimeout(function () {
                    subscribeToNotifications(token, apiUrl);
                }, 5000);
            }
        }
    };

    xhr.onerror = function () {
        setTimeout(function () {
            subscribeToNotifications(token, apiUrl);
        }, 5000);
    };

    xhr.send();
}

// run script
(function initNotifications() {
    var tokenMeta = document.getElementById("notify-token-meta");
    var apiMeta = document.getElementById("notify-api-meta");

    // show notifications
    if (tokenMeta && apiMeta) {
        var token = tokenMeta.getAttribute("content");
        var apiUrl = apiMeta.getAttribute("content");

        // read token and apiUrl from Django template
        if (token && apiUrl) {
            // remove trailing slash from apiUrl for correct concatenation
            if (apiUrl.charAt(apiUrl.length - 1) === "/") {
                apiUrl = apiUrl.slice(0, -1);
            }

            loadInitialNotifications(token, apiUrl);
            subscribeToNotifications(token, apiUrl);
        }
    }
})();
