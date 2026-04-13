// appendMode: true - add to end (for history), false - add to beginning (for new)
function renderNotification(data, isHistory) {
    // check status and choose the container
    var isNew = data.ViewedAt === null;
    var meta = data.Meta || {};

    // choose the container based on the status
    var containerId = isNew ? "list-new" : "list-old";
    var container = document.getElementById(containerId);
    if (!container) return;

    var card = document.createElement("div");
    card.className = "notify_card";
    card.setAttribute("data-id", data.ID);

    // set the card ID based on the type and status
    var type = meta.type || "normal";
    if (type === "critical" || type === "important") {
        card.id = "ntf_i";
    } else if (isNew) {
        card.id = "ntf_unread";
    }

    // format the icon path
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

    // if there is an action URL, add a link to it
    if (meta.action_url) {
        var actionText = meta.action_text || "Перейти »";
        inner +=
            '<a href="' +
            meta.action_url +
            '" class="notify_action">' +
            actionText +
            "</a>";
    }

    // format the time string
    var timeStr = "только что";
    if (!isNew && data.CreatedAt) {
        var d = new Date(data.CreatedAt * 1000);
        // format the date and time
        timeStr =
            d.toLocaleDateString() +
            ", " +
            d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    inner +=
        '<div class="notify_time"><small>' + timeStr + "</small></div></div>";
    card.innerHTML = inner;

    if (isHistory) {
        // add to end
        container.appendChild(card);
        container.appendChild(document.createElement("br"));
    } else {
        // add to top (new from stream)
        container.insertBefore(
            document.createElement("br"),
            container.firstChild,
        );
        container.insertBefore(card, container.firstChild);
    }

    // make the notification clickable
    if (isNew) {
        card.onclick = function (e) {
            // ignore click if the user clicked on the "Go to" button
            if (e.target.tagName.toLowerCase() === "a") return;

            // visually mark the notification as read
            card.id = "";

            // put-request to mark the notification as read
            if (typeof markAsRead === "function") {
                markAsRead(data.ID, card);
            }

            card.onclick = null;

            var oldContainer = document.getElementById("list-old");
            if (oldContainer) {
                oldContainer.insertBefore(card, oldContainer.firstChild);
                oldContainer.insertBefore(br, oldContainer.firstChild);
            }
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
                var notifications = response.data || [];
                var unreadTotal = 0;

                for (var i = 0; i < notifications.length; i++) {
                    if (notifications[i].ViewedAt === null) {
                        unreadTotal++;
                    }
                    renderNotification(notifications[i], true);
                }

                var countElement = document.getElementById("notify-count-text");
                if (countElement) {
                    if (unreadTotal === 0) {
                        countElement.innerHTML = "У вас нет новых уведомлений";
                    } else {
                        countElement.innerHTML =
                            "У вас <b>" +
                            unreadTotal +
                            "</b> новых уведомлений";
                    }
                }
            } catch (e) {}
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
