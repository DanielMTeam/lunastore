document.addEventListener("DOMContentLoaded", function () {
    const form =
        document.getElementById("app-upload-form") ||
        document.getElementById("application_form") ||
        document.getElementById("distribution_form");
    if (!form) return;

    const config = window.cdn_config ||
        window.CDN_CONFIG || {
            uploadUrl: "https://spire.lunastore.app/cdn/upload",
            tokenBaseUrl:
                "https://api.lunastore.app/method/user/getPubUploadToken/",
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
        const iconInput = document.querySelector('input[type="file"][name="icon_file"]');
        const screenshotsInput = document.querySelector('input[type="file"][name="screenshots_files"]');
        const distInput = document.querySelector('input[type="file"][name="dist_file"]');
        const inlineDistInputs = Array.from(document.querySelectorAll('input[type="file"][name$="-dist_file"]'));

        const hasIcon = iconInput && iconInput.files && iconInput.files[0];
        const hasScreenshots =
            screenshotsInput &&
            screenshotsInput.files &&
            screenshotsInput.files.length > 0;
        const hasDist = distInput && distInput.files && distInput.files[0];
        const hasInlineDist = inlineDistInputs.some(inp => inp.files && inp.files.length > 0);

        if (!hasIcon && !hasScreenshots && !hasDist && !hasInlineDist) return;

        e.preventDefault();
        if (submitBtn) submitBtn.disabled = true;

        try {
            const uploadFile = async (file, targetContext) => {
                // get personal token for file
                let tokenUrl;
                if (targetContext === "distribution") {
                    let currentAppId = config.appId;
                    if (!currentAppId) {
                        const appSelect = document.querySelector('select[name="app"]');
                        if (appSelect) {
                            currentAppId = appSelect.value;
                        }
                    }
                    if (!currentAppId) {
                        throw new Error("Невозможно загрузить дистрибуцию: не выбрано или не сохранено приложение. Выберите приложение в списке.");
                    }
                    tokenUrl = `${config.privTokenUrl}?target=${targetContext}&app_id=${currentAppId}`;
                } else {
                    const baseUrl = config.tokenBaseUrl || config.tokenUrl;
                    tokenUrl = `${baseUrl}?target=${targetContext}`;
                }

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
                return data;
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

            // send dist
            let distIdx = -1;
            if (hasDist) {
                distIdx = tasks.length;
                tasks.push(uploadFile(distInput.files[0], "distribution"));
            }

            // send inline dists
            const inlineDistTasks = [];
            inlineDistInputs.forEach(input => {
                if (input.files && input.files[0]) {
                    inlineDistTasks.push({
                        input: input,
                        taskIdx: tasks.length
                    });
                    tasks.push(uploadFile(input.files[0], "distribution"));
                }
            });

            // waiting for result
            const results = await Promise.all(tasks);

            const cdnIconField = form.querySelector(
                'input[name="cdn_icon_path"]',
            );
            const cdnScreenshotsField = form.querySelector(
                'input[name="cdn_screenshots_data"]',
            );
            const cdnConfirmTokenField = form.querySelector(
                'input[name="cdn_confirm_token"]',
            );

            if (iconIdx !== -1 && cdnIconField)
                cdnIconField.value = results[iconIdx].filepath || "";
            if (hasScreenshots && cdnScreenshotsField) {
                const paths = results.slice(scrStartIdx, scrStartIdx + screenshotsInput.files.length).map(d => d.filepath || "");
                cdnScreenshotsField.value = JSON.stringify(paths);
            }
            if (distIdx !== -1 && cdnConfirmTokenField) {
                cdnConfirmTokenField.value = results[distIdx].confirm_token || "";
            }

            inlineDistTasks.forEach(item => {
                const prefix = item.input.name.replace('-dist_file', '');
                const inlineTokenField = form.querySelector(`input[name="${prefix}-cdn_confirm_token"]`);
                if (inlineTokenField) {
                    inlineTokenField.value = results[item.taskIdx].confirm_token || "";
                } else {
                    alert("WARNING: cdn_confirm_token field not found for " + prefix);
                }
            });

            HTMLFormElement.prototype.submit.call(form);
        } catch (err) {
            alert(i18n.error + err.message);
            if (submitBtn) submitBtn.disabled = false;
        }
    });
});
