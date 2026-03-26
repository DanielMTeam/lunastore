document.addEventListener("DOMContentLoaded", function () {
    const form =
        document.getElementById("app-upload-form") ||
        document.getElementById("application_form");
    if (!form) return;

    const config = window.cdn_config ||
        window.CDN_CONFIG || {
            uploadUrl: "https://spire.lunastore.app/cdn/upload",
            tokenBaseUrl:
                "https://api.lunastore.app/method/user/getPubUploadToken",
        };

    const i18n = window.luna_i18n ||
        window.LUNA_I18N || {
            uploading: "Загрузка...",
            error: "Ошибка: ",
            tokenError: "Ошибка токена",
            fileError: "Ошибка файла",
        };

    const submitBtn =
        form.querySelector('[name="_save"]') ||
        form.querySelector('[type="submit"]');

    form.addEventListener("submit", async function (e) {
        const iconInput = document.getElementById("inp_icon");
        const screenshotsInput = document.getElementById("inp_scr");

        const hasIcon = iconInput && iconInput.files && iconInput.files[0];
        const hasScreenshots =
            screenshotsInput &&
            screenshotsInput.files &&
            screenshotsInput.files.length > 0;

        if (!hasIcon && !hasScreenshots) return;

        e.preventDefault();
        if (submitBtn) submitBtn.disabled = true;

        try {
            const uploadFile = async (file, targetContext) => {
                // get personal token for file
                const baseUrl = config.tokenBaseUrl || config.tokenUrl;
                const tokenUrl = `${baseUrl}?target=${targetContext}`;
                const tokenRes = await fetch(tokenUrl, {
                    credentials: "include",
                });

                if (!tokenRes.ok)
                    throw new Error(`${i18n.tokenError} (${targetContext})`);
                const { upload_token } = await tokenRes.json();

                // send file with unique token
                const fd = new FormData();
                const finalUrl = new URL(config.uploadUrl);
                finalUrl.searchParams.append("token", upload_token);
                fd.append("file", file);
                fd.append("mime_type", file.type);

                const res = await fetch(finalUrl.toString(), {
                    method: "POST",
                    body: fd,
                });

                if (res.status !== 202 && !res.ok) {
                    let errMsg = i18n.fileError;
                    if (res.status === 415)
                        errMsg = "Недопустимый формат файла (415).";
                    if (res.status === 409)
                        errMsg = "Токен уже использован (409).";
                    throw new Error(errMsg);
                }
                const data = await res.json();
                return data.filepath || "";
            };

            const tasks = [];
            let iconIdx = -1;

            // send app icons
            if (hasIcon) {
                iconIdx = tasks.length;
                tasks.push(uploadFile(iconInput.files[0], "icon"));
            }

            let scrStartIdx = tasks.length;

            // send screenshots
            if (hasScreenshots) {
                Array.from(screenshotsInput.files).forEach((f) =>
                    tasks.push(uploadFile(f, "screenshot")),
                );
            }

            // waiting for result
            const results = await Promise.all(tasks);

            const cdnIconField = form.querySelector(
                'input[name="cdn_icon_path"]',
            );
            const cdnScreenshotsField = form.querySelector(
                'input[name="cdn_screenshots_data"]',
            );

            if (iconIdx !== -1 && cdnIconField)
                cdnIconField.value = results[iconIdx];
            if (hasScreenshots && cdnScreenshotsField) {
                cdnScreenshotsField.value = JSON.stringify(
                    results.slice(scrStartIdx),
                );
            }

            HTMLFormElement.prototype.submit.call(form);
        } catch (err) {
            alert(i18n.error + err.message);
            if (submitBtn) submitBtn.disabled = false;
        }
    });
});
