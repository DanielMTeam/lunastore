document.addEventListener("DOMContentLoaded", function () {
    const config = window.DIST_CDN_CONFIG || {};
    const i18n = window.DIST_CDN_I18N || {};

    const fileInput = document.getElementById("id_file");
    const form = document.getElementById("distribution-form");
    const tokenInput = document.querySelector(
        'input[name="cdn_confirm_token"]',
    );

    const progressContainer = document.getElementById("progress-container");
    const progressBar = document.getElementById("progress-bar-fill");
    const progressText = document.getElementById("progress-text");

    if (form) {
        form.addEventListener("submit", async function (e) {
            if (fileInput && fileInput.files && fileInput.files.length > 0) {
                e.preventDefault();

                const submitBtn = form.querySelector(
                    '[type="submit"], .action_button',
                );
                const originalText = submitBtn
                    ? submitBtn.textContent || submitBtn.value
                    : i18n.saveBtn;

                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.textContent = i18n.uploading || "Загрузка...";
                }

                if (progressContainer) {
                    progressContainer.style.display = "block";
                    if (progressBar) progressBar.style.width = "0%";
                    if (progressText) progressText.textContent = "0%";
                }

                try {
                    const tokenUrl = new URL(
                        config.getTokenUrl,
                        window.location.origin,
                    );
                    tokenUrl.searchParams.append("app_id", config.appId);

                    const tokenRes = await fetch(tokenUrl, {
                        credentials: "include",
                    });
                    if (!tokenRes.ok)
                        throw new Error("Django error: " + tokenRes.status);

                    const djangoJson = await tokenRes.json();
                    const uploadToken = djangoJson.upload_token;
                    const file = fileInput.files[0];
                    const uploadUrl = new URL(config.cdnUploadUrl);
                    uploadUrl.searchParams.append("token", uploadToken);

                    const fd = new FormData();
                    fd.append("file", file);
                    fd.append("mime_type", file.type);

                    const cdnJson = await new Promise((resolve, reject) => {
                        const xhr = new XMLHttpRequest();
                        xhr.open("POST", uploadUrl.toString());

                        xhr.upload.addEventListener("progress", (event) => {
                            if (event.lengthComputable) {
                                const percentComplete = Math.round(
                                    (event.loaded / event.total) * 100,
                                );
                                if (progressBar)
                                    progressBar.style.width = `${percentComplete}%`;
                                if (progressText)
                                    progressText.textContent = `${percentComplete}%`;
                            }
                        });

                        xhr.onload = () => {
                            if (
                                xhr.status === 202 ||
                                (xhr.status >= 200 && xhr.status < 300)
                            ) {
                                try {
                                    const responseJson = JSON.parse(
                                        xhr.responseText,
                                    );
                                    resolve(responseJson);
                                } catch (e) {
                                    reject(
                                        new Error(
                                            "Некорректынй JSON от LunaSpire. Пожалуйста, обратитесь к администратору.",
                                        ),
                                    );
                                }
                            } else {
                                let errorMsg = `Ошибка LunaSpire (${xhr.status}): ${xhr.responseText}`;
                                if (xhr.status === 415)
                                    errorMsg =
                                        "Ошибка: недопустимый тип файла (415 HTTP error). Пожалуйста, обратитесь к администратору.";
                                if (xhr.status === 409)
                                    errorMsg =
                                        "Ошибка: этот токен загрузки уже использован (409 HTTP error). Пожалуйста, обновите страницу.";
                                reject(new Error(errorMsg));
                            }
                        };

                        xhr.onerror = () => {
                            reject(
                                new Error(
                                    "Ошибка сети. Пожалуйста, проверьте подключение к интернету.",
                                ),
                            );
                        };

                        xhr.send(fd);
                    });

                    if (!cdnJson.confirm_token) {
                        throw new Error("CDN did not return confirm_token");
                    }

                    if (tokenInput) tokenInput.value = cdnJson.confirm_token;
                    fileInput.value = "";

                    HTMLFormElement.prototype.submit.call(form);
                } catch (err) {
                    alert("Error: " + err.message);
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = originalText;
                    }
                    if (progressContainer)
                        progressContainer.style.display = "none";
                }
            }
        });
    }
});
