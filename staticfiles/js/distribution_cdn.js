document.addEventListener("DOMContentLoaded", function () {
    const config = window.DIST_CDN_CONFIG || {};
    const i18n = window.DIST_CDN_I18N || {};

    const fileInput = document.getElementById("id_file");
    const form = document.getElementById("distribution-form");
    const tokenInput = document.querySelector(
        'input[name="cdn_confirm_token"]',
    );

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

                    const cdnRes = await fetch(uploadUrl.toString(), {
                        method: "POST",
                        body: fd,
                        mode: "cors",
                    });

                    if (cdnRes.status !== 202 && !cdnRes.ok) {
                        const errorBody = await cdnRes.text();
                        let errorMsg = `Ошибка CDN (${cdnRes.status}): ${errorBody}`;
                        if (cdnRes.status === 415)
                            errorMsg =
                                "Ошибка: Недопустимый тип файла (415). Пожалуйста, обратитесь к администратору";
                        if (cdnRes.status === 409)
                            errorMsg =
                                "Ошибка: Этот токен загрузки уже использован (409). Пожалуйста, обновите страницу и попробуйте снова";
                        throw new Error(errorMsg);
                    }

                    const cdnJson = await cdnRes.json();

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
                }
            }
        });
    }
});
